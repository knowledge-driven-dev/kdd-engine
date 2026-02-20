# KDD Toolkit

Motor de indexación y retrieval para especificaciones KDD (Knowledge-Driven Development). Indexa artefactos de dominio y ofrece búsqueda híbrida (semántica + grafo + lexical) para agentes de IA.

## Concepto

KDD Toolkit actúa como un "bibliotecario": cuando un agente pregunta algo, responde con nodos del grafo de conocimiento y scores de relevancia, permitiendo que el agente decida qué documentos leer.

```
┌─────────────┐     query      ┌─────────────┐     scored nodes     ┌─────────────┐
│   Agente    │ ─────────────▶ │ KDD Toolkit │ ──────────────────▶  │  Agente lee │
│     IA      │                │ (retrieval) │                      │  specs/*.md │
└─────────────┘                └─────────────┘                      └─────────────┘
```

## Stack

| Componente | Tecnología |
|------------|------------|
| **Runtime** | Bun (TypeScript) |
| **Grafo** | graphology (in-memory, cargado de `.kdd-index/`) |
| **Vectores** | Brute-force cosine similarity (in-memory) |
| **Embeddings** | `all-mpnet-base-v2` (768 dims) via `@huggingface/transformers` |
| **CLI** | citty |
| **MCP** | `@modelcontextprotocol/sdk` |

Sin bases de datos. Todo se persiste como ficheros JSON en `.kdd-index/`.

## Quick Start

### Requisitos

- [Bun](https://bun.sh/) v1.1+

### Instalación

```bash
git clone https://github.com/knowledge-driven-dev/kdd-engine.git
cd kdd-engine
bun install
```

### Indexar

```bash
# Indexar todas las specs (grafo + embeddings)
bun run src/cli.ts index specs/

# Solo grafo (sin embeddings, más rápido)
bun run src/cli.ts index specs/ --level L1
```

El primer `index` con nivel L2 descargará el modelo de embeddings (`all-mpnet-base-v2`, ~440MB). Los datos se almacenan en `.kdd-index/`.

### Buscar

```bash
# Búsqueda híbrida (semántica + grafo + lexical)
bun run src/cli.ts search --index-path .kdd-index "impact analysis"

# Filtrar por kind
bun run src/cli.ts search --index-path .kdd-index "authentication" --kind entity,command

# Sin embeddings (solo grafo + lexical)
bun run src/cli.ts search --index-path .kdd-index "pedido" --no-embeddings
```

### Explorar

```bash
# Traversal del grafo desde un nodo
bun run src/cli.ts graph --index-path .kdd-index "Entity:KDDDocument"

# Análisis de impacto (reverse BFS)
bun run src/cli.ts impact --index-path .kdd-index "Entity:KDDDocument"

# Búsqueda semántica pura
bun run src/cli.ts semantic --index-path .kdd-index "retrieval query"

# Cobertura de gobernanza
bun run src/cli.ts coverage --index-path .kdd-index "Entity:KDDDocument"

# Violaciones de dependencia entre capas
bun run src/cli.ts violations --index-path .kdd-index
```

### MCP Server (para agentes)

```bash
bun run src/mcp.ts
```

Expone 7 tools MCP: `kdd_search`, `kdd_find_spec`, `kdd_related`, `kdd_impact`, `kdd_read_section`, `kdd_list`, `kdd_stats`.

Variables de entorno opcionales:
- `KDD_INDEX_PATH` — ruta al índice (default: `.kdd-index`)
- `KDD_SPECS_PATH` — ruta a las specs (default: `specs`)

## Estructura del Proyecto

```
kdd-engine/
├── specs/                          # 52 spec files KDD (sin cambios)
├── src/
│   ├── domain/
│   │   ├── types.ts                # Enums, interfaces, modelos
│   │   └── rules.ts                # BR-DOCUMENT-001, BR-EMBEDDING-001, BR-LAYER-001
│   ├── application/
│   │   ├── extractors/
│   │   │   ├── base.ts             # Helpers: makeNodeId, buildWikiLinkEdges, etc.
│   │   │   ├── registry.ts         # ExtractorRegistry (16 extractors)
│   │   │   └── kinds/              # Un extractor por KDDKind
│   │   ├── commands/
│   │   │   └── index-document.ts   # CMD-001: read → parse → extract → embed → write
│   │   ├── queries/
│   │   │   ├── hybrid-search.ts    # QRY-003: semántica + grafo + lexical
│   │   │   ├── graph-query.ts      # QRY-001: BFS traversal
│   │   │   ├── impact-query.ts     # QRY-004: reverse BFS
│   │   │   ├── semantic-query.ts   # QRY-002: vector puro
│   │   │   ├── coverage-query.ts   # QRY-005: gobernanza
│   │   │   └── violations-query.ts # QRY-006: violaciones de capa
│   │   └── chunking.ts             # BR-EMBEDDING-001 paragraph chunking
│   ├── infra/
│   │   ├── artifact-loader.ts      # Lee .kdd-index/
│   │   ├── artifact-writer.ts      # Escribe .kdd-index/
│   │   ├── graph-store.ts          # graphology wrapper (BFS, text search)
│   │   ├── vector-store.ts         # Brute-force cosine similarity
│   │   ├── embedding-model.ts      # @huggingface/transformers wrapper
│   │   ├── markdown-parser.ts      # Frontmatter + secciones
│   │   └── wiki-links.ts           # [[Target]] extraction
│   ├── container.ts                # DI wiring
│   ├── cli.ts                      # CLI (7 subcommands)
│   └── mcp.ts                      # MCP server (7 tools)
├── tests/                          # bun:test
├── bench/                          # Benchmarks
├── docs/                           # ADRs y diseño
├── package.json
├── tsconfig.json
└── Makefile
```

## 16 KDDKind Types

Cada kind tiene un extractor dedicado en `src/application/extractors/kinds/`:

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
| `prd` | 00-requirements | `PRD:PRD-KDDEngine` |
| `adr` | 00-requirements | `ADR:ADR-0001` |
| `glossary` | 01-domain | `Glossary:GlossaryName` |

## Index Levels

| Nivel | Contenido | Búsqueda |
|-------|-----------|----------|
| **L1** | Grafo de nodos/edges (front-matter + wiki-links) | Grafo + lexical |
| **L2** | L1 + embeddings vectoriales (768 dims) | Híbrida (semántica + grafo + lexical) |

## Tests

```bash
bun test
```

## Makefile

```bash
make install     # bun install
make index       # Indexar specs/
make search q=.. # Búsqueda híbrida
make test        # bun test
make typecheck   # tsc --noEmit
make mcp         # Iniciar MCP server
make clean       # Limpiar node_modules y .kdd-index
```

## Licencia

MIT
