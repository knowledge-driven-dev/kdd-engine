# KDD Engine (TypeScript/Bun)

Motor de retrieval para especificaciones KDD. Indexa artefactos de dominio (entidades, eventos, reglas, comandos, queries, casos de uso) y ofrece búsqueda híbrida (semántica + grafo + lexical) para agentes de IA.

> **Paquete**: `src/` | **CLI**: `bun run src/cli.ts` | **MCP**: `bun run src/mcp.ts`

---

## Arquitectura

Módulos funcionales con inyección de dependencias via `container.ts`:

```
src/
├── domain/              # Tipos, enums, reglas puras (sin I/O)
├── application/         # Commands (write) + Queries (read) + Extractors
├── infra/               # Adapters: filesystem, graphology, vector store, embeddings
├── cli.ts               # Entry point CLI (citty)
├── mcp.ts               # Entry point MCP server
└── container.ts         # DI — ensambla stores desde .kdd-index/
```

### Flujo de dependencias

```
cli.ts / mcp.ts ──▶ application/ ──▶ domain/
                         │
                         ▼
                     infra/    (implementa stores en memoria)
```

El dominio es puro (sin I/O). Los módulos de infra cargan `.kdd-index/` a stores en memoria.

### Stores en memoria

| Store | Implementación | Responsabilidad |
|-------|---------------|-----------------|
| `GraphStore` | graphology (directed multigraph) | Nodos, edges, BFS, reverse BFS, text search |
| `VectorStore` | Brute-force Float64Array cosine | Búsqueda semántica por similitud |
| `ArtifactWriter` | Bun.write() + JSON | Escritura de `.kdd-index/` artifacts |
| `ArtifactLoader` | Bun.file() + Bun.Glob | Lectura de `.kdd-index/` artifacts |
| Embedding model | `@huggingface/transformers` | Genera embeddings `all-mpnet-base-v2` (768 dims) |

---

## Index Levels (Capacidad Progresiva)

```
L1 ─────────────────────────────────────────── Siempre disponible
  Grafo de nodos/edges extraídos de front-matter + wiki-links
  graphology en memoria
  Búsqueda: grafo + lexical

L2 ────────────────────────── @huggingface/transformers
  Todo L1 + embeddings vectoriales (768 dims, all-mpnet-base-v2)
  Brute-force cosine en memoria
  Búsqueda: híbrida (semántica + grafo + lexical)
```

---

## Artifact Store (`.kdd-index/`)

El índice se persiste como ficheros JSON en disco. No requiere base de datos:

```
.kdd-index/
├── manifest.json          # IndexManifest: version, stats, git_commit, level
├── nodes/
│   ├── entity/
│   │   ├── KDDDocument.json   # GraphNode serializado
│   │   └── GraphEdge.json
│   ├── command/
│   │   └── CMD-001.json
│   └── ...                # Un directorio por KDDKind
├── edges/
│   └── edges.jsonl        # GraphEdge stream (append-only JSONL)
└── embeddings/
    ├── entity/
    │   └── KDDDocument.json   # Lista de Embedding objects
    └── ...
```

Al arrancar un query, `createContainer()` lee los artifacts de disco y los carga en los stores en memoria (graphology + VectorStore).

---

## CQRS: Commands

### CMD-001 — IndexDocument

Procesa un único fichero de spec:

1. Lee fichero, extrae front-matter (`gray-matter`)
2. Routea documento via `routeDocument()` (kind + validación de ubicación)
3. Parsea secciones Markdown (`parseMarkdownSections()`)
4. Extrae `GraphNode` + `GraphEdge[]` con extractor específico del kind
5. Valida dependencias de capa (`isLayerViolation()`)
6. (L2) Chunking por párrafos + embeddings (`chunkDocument()`)
7. Escribe artifacts en `ArtifactWriter`

---

## CQRS: Queries

### QRY-003 — HybridSearch (query principal)

Búsqueda híbrida con fusión de scores. Es el query por defecto para agentes.

**Fases:**
1. **Semantic** (L2): encode query → brute-force cosine similarity
2. **Lexical**: text search sobre campos indexados en GraphStore
3. **Graph expansion**: BFS desde nodos encontrados, profundidad configurable
4. **Fusion scoring**: ponderación `semantic(0.6) + graph(0.3) + lexical(0.1)` + bonus multi-source

**Degradación elegante:** sin embeddings (L1) solo usa grafo + lexical con warning.

### QRY-001 — GraphQuery

Traversal puro del grafo desde un nodo raíz, con profundidad y filtro de kinds.

### QRY-002 — SemanticQuery

Búsqueda puramente vectorial (solo L2).

### QRY-004 — ImpactQuery

Análisis de impacto: dado un nodo, encuentra todos los nodos afectados (reverse BFS por edges incoming).

### QRY-005 — CoverageQuery

Validación de gobernanza: verifica que artefactos relacionados requeridos existan.
Ejemplo: una Entity debería tener Events, BusinessRules y UseCases asociados.

### QRY-006 — ViolationsQuery

Detecta violaciones de dependencia entre capas (`BR-LAYER-001`):
- Capa inferior no debe referenciar capa superior
- `00-requirements` está exenta
- Retorna: lista de violaciones, tasa de violación, total de edges analizados

---

## Entidades de Dominio

### KDDDocument

Representación parseada de un fichero de spec. Contiene:
- `id`, `kind`, `layer`, `source_path`, `source_hash`
- `front_matter` (Record), `sections` (Section[]), `wiki_links`

### GraphNode

Nodo del grafo, producido al indexar un KDDDocument:
- ID: `"{Prefix}:{DocumentId}"` (ej. `"Entity:KDDDocument"`, `"CMD:CMD-001"`)
- `indexed_fields`: campos extraídos por el extractor específico del kind

### GraphEdge

Relación tipada y dirigida entre nodos:
- 17 edge types: `WIKI_LINK`, `ENTITY_RULE`, `UC_EXECUTES_CMD`, `UC_APPLIES_RULE`, `EMITS`, etc.

### Embedding

Vector semántico generado desde un chunk de texto:
- ID: `"{document_id}:{section_heading}:{chunk_index}"`
- Modelo: `all-mpnet-base-v2` (768 dimensiones)

### IndexManifest

Metadatos del índice en `manifest.json`: version, nivel, stats, git commit, dominios.

---

## 16 KDDKind Types

Cada kind tiene un extractor dedicado en `application/extractors/kinds/`:

| Kind | Layer | Ejemplo de ID |
|------|-------|---------------|
| `entity` | 01-domain | `Entity:KDDDocument` |
| `event` | 01-domain | `Event:EVT-KDDDocument-Indexed` |
| `business-rule` | 01-domain | `BR:BR-INDEX-001` |
| `business-policy` | 02-behavior | `BP:BP-CREDITO-001` |
| `cross-policy` | 02-behavior | `XP:XP-CREDITOS-001` |
| `command` | 02-behavior | `CMD:CMD-001` |
| `query` | 02-behavior | `QRY:QRY-003` |
| `process` | 02-behavior | `PROC:PROC-001` |
| `use-case` | 02-behavior | `UC:UC-001` |
| `ui-view` | 03-experience | `UIView:UI-Dashboard` |
| `ui-component` | 03-experience | `UIComponent:UI-Button` |
| `requirement` | 04-verification | `REQ:REQ-001` |
| `objective` | 00-requirements | `OBJ:OBJ-001` |
| `prd` | 00-requirements | `PRD:PRD-KBEngine` |
| `adr` | 00-requirements | `ADR:ADR-0001` |
| `glossary` | 01-domain | `Glossary:GlossaryName` |

---

## CLI

```bash
# Indexar specs (full reindex)
bun run src/cli.ts index specs/
bun run src/cli.ts index specs/ --level L1     # solo grafo
bun run src/cli.ts index specs/ --domain core  # multi-domain

# Buscar (híbrido: semántica + grafo + lexical)
bun run src/cli.ts search --index-path .kdd-index "registro de usuario"
bun run src/cli.ts search --index-path .kdd-index "pedido" --kind entity,command
bun run src/cli.ts search --index-path .kdd-index "auth" --min-score 0.5 -n 5

# Búsqueda semántica pura
bun run src/cli.ts semantic --index-path .kdd-index "retrieval query"

# Explorar grafo
bun run src/cli.ts graph --index-path .kdd-index Entity:KDDDocument
bun run src/cli.ts graph --index-path .kdd-index Entity:KDDDocument --depth 3

# Análisis de impacto
bun run src/cli.ts impact --index-path .kdd-index Entity:KDDDocument

# Cobertura de gobernanza
bun run src/cli.ts coverage --index-path .kdd-index Entity:KDDDocument

# Violaciones de capa
bun run src/cli.ts violations --index-path .kdd-index
```

---

## MCP Server

7 tools expuestos via `@modelcontextprotocol/sdk`:

| Tool | Implementación |
|------|---------------|
| `kdd_search` | `hybridSearch()` — búsqueda con filtros |
| `kdd_find_spec` | `hybridSearch()` con limit=5 (convenience) |
| `kdd_related` | `graphQuery()` — BFS desde nodo |
| `kdd_impact` | `impactQuery()` — reverse BFS |
| `kdd_read_section` | `Bun.file()` — lee .md + anchor |
| `kdd_list` | graph store iteration — filtra por kind/domain |
| `kdd_stats` | manifest stats + counts |

---

## Business Rules (funciones puras)

Implementadas en `domain/rules.ts`, sin I/O ni side-effects:

| Regla | Función | Descripción |
|-------|---------|-------------|
| BR-DOCUMENT-001 | `routeDocument()` | Determina KDDKind desde front-matter |
| BR-EMBEDDING-001 | `embeddableSections()` | Secciones embeddables por kind |
| BR-INDEX-001 | `detectIndexLevel()` | Nivel de índice según recursos |
| BR-LAYER-001 | `isLayerViolation()` | Valida dependencias entre capas |

---

*Última actualización: Febrero 2026 (migración a TypeScript/Bun)*
