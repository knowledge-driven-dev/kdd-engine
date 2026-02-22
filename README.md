# kdd-engine

Semantic indexing and retrieval engine for [KDD (Knowledge-Driven Development)](https://github.com/knowledge-driven-dev/kdd) specifications. Indexes spec artifacts and provides hybrid search (semantic + graph + lexical) to feed agent context.

---

## Adoption: Enabling RAG for Your Project's Specs

Add semantic search to any project with KDD specs in 3 steps:

### Step 1 — Index your specs

```bash
# From your project root (requires kdd-engine installed)
kdd-engine index ./specs
# or: bun run /path/to/kdd-engine/packages/cli/src/cli.ts index ./specs
```

This generates `.kdd-index/` with the knowledge graph and embeddings.

> First run downloads the embedding model (~440MB). Subsequent runs are fast.

### Step 2 — Start the MCP server

```bash
kdd-engine serve
# or explicitly:
KDD_SPECS_PATH=./specs KDD_INDEX_PATH=./.kdd-index bun run /path/to/kdd-engine/packages/mcp/src/mcp.ts
```

### Step 3 — Configure Claude Code

In your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "kdd": {
      "command": "bun",
      "args": ["/path/to/kdd-engine/packages/mcp/src/mcp.ts"],
      "env": {
        "KDD_SPECS_PATH": "./specs",
        "KDD_INDEX_PATH": "./.kdd-index"
      }
    }
  }
}
```

Claude Code gains 8 MCP tools: `kdd_search`, `kdd_find_spec`, `kdd_related`, `kdd_impact`, `kdd_context`, `kdd_read_section`, `kdd_list`, `kdd_stats`.

---

## The KDD Ecosystem

```
┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────┐
│   kdd-specs     │  │   kdd-tools      │  │   kdd-engine           │
│                 │  │                  │  │                        │
│  Layer struct.  │  │  Skills, rules,  │  │  Indexes /specs and    │
│  Templates      │  │  commands and    │  │  serves semantic       │
│  kdd.md ref     │  │  validator for   │  │  search via MCP to     │
│                 │  │  Claude Code     │  │  agent context         │
└─────────────────┘  └──────────────────┘  └────────────────────────┘
```

kdd-engine is optional but recommended for projects with >20 spec files.

---

## Concepto

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
bun run packages/cli/src/cli.ts index specs/

# Solo grafo (sin embeddings, más rápido)
bun run packages/cli/src/cli.ts index specs/ --level L1
```

El primer `index` con nivel L2 descargará el modelo de embeddings (`all-mpnet-base-v2`, ~440MB). Los datos se almacenan en `.kdd-index/`.

### Buscar

```bash
# Búsqueda híbrida (semántica + grafo + lexical)
bun run packages/cli/src/cli.ts search --index-path .kdd-index "impact analysis"

# Filtrar por kind
bun run packages/cli/src/cli.ts search --index-path .kdd-index "authentication" --kind entity,command

# Sin embeddings (solo grafo + lexical)
bun run packages/cli/src/cli.ts search --index-path .kdd-index "pedido" --no-embeddings
```

### Explorar

```bash
# Traversal del grafo desde un nodo
bun run packages/cli/src/cli.ts graph --index-path .kdd-index "Entity:KDDDocument"

# Análisis de impacto (reverse BFS)
bun run packages/cli/src/cli.ts impact --index-path .kdd-index "Entity:KDDDocument"

# Búsqueda semántica pura
bun run packages/cli/src/cli.ts semantic --index-path .kdd-index "retrieval query"

# Cobertura de gobernanza
bun run packages/cli/src/cli.ts coverage --index-path .kdd-index "Entity:KDDDocument"

# Violaciones de dependencia entre capas
bun run packages/cli/src/cli.ts violations --index-path .kdd-index
```

### MCP Server (para agentes)

```bash
bun run packages/mcp/src/mcp.ts
```

Expone 8 tools MCP: `kdd_search`, `kdd_find_spec`, `kdd_related`, `kdd_impact`, `kdd_context`, `kdd_read_section`, `kdd_list`, `kdd_stats`.

Variables de entorno opcionales:
- `KDD_INDEX_PATH` — ruta al índice (default: `.kdd-index`)
- `KDD_SPECS_PATH` — ruta a las specs (default: `specs`)

## Estructura del Proyecto

Monorepo con Bun workspaces — 3 paquetes:

```
kdd-engine/
├── specs/                              # 52 spec files KDD (sin cambios)
├── packages/
│   ├── core/                           # @kdd/core — librería principal
│   │   └── src/
│   │       ├── index.ts                # Barrel export (API pública)
│   │       ├── domain/
│   │       │   ├── types.ts            # Enums, interfaces, modelos
│   │       │   └── rules.ts            # BR-DOCUMENT-001, BR-EMBEDDING-001, BR-LAYER-001
│   │       ├── application/
│   │       │   ├── extractors/         # ExtractorRegistry (16 extractors)
│   │       │   ├── commands/           # CMD-001: read → parse → extract → embed → write
│   │       │   ├── queries/            # QRY-001..008: graph, hybrid, semantic, impact, etc.
│   │       │   └── chunking.ts         # BR-EMBEDDING-001 paragraph chunking
│   │       ├── infra/
│   │       │   ├── artifact-loader.ts  # Lee .kdd-index/
│   │       │   ├── artifact-writer.ts  # Escribe .kdd-index/
│   │       │   ├── graph-store.ts      # graphology wrapper (BFS, text search)
│   │       │   ├── vector-store.ts     # Brute-force cosine similarity
│   │       │   ├── embedding-model.ts  # @huggingface/transformers wrapper
│   │       │   ├── markdown-parser.ts  # Frontmatter + secciones
│   │       │   └── wiki-links.ts       # [[Target]] extraction
│   │       └── container.ts            # DI wiring
│   ├── cli/                            # @kdd/cli — CLI (9 subcommands)
│   │   └── src/cli.ts
│   └── mcp/                            # @kdd/mcp — MCP server (8 tools)
│       └── src/mcp.ts
├── tests/                              # bun:test
├── bench/                              # Benchmarks
├── docs/                               # ADRs y diseño
├── package.json                        # Workspace root
├── tsconfig.json                       # Base config + project references
└── Makefile
```

## 16 KDDKind Types

Cada kind tiene un extractor dedicado en `packages/core/src/application/extractors/kinds/`:

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
make typecheck   # tsc --build
make mcp         # Iniciar MCP server
make clean       # Limpiar node_modules y .kdd-index
```

## Licencia

MIT
