# KB-Engine

Sistema de retrieval de conocimiento para agentes de IA. Indexa documentación estructurada (KDD) y devuelve **referencias** a documentos relevantes, no contenido.

## Concepto

KB-Engine actúa como un "bibliotecario": cuando un agente pregunta algo, responde con URLs y anclas a los documentos relevantes (`file://path/to/doc.md#seccion`), permitiendo que el agente decida qué leer.

```
┌─────────────┐     query      ┌─────────────┐     referencias     ┌─────────────┐
│   Agente    │ ─────────────▶ │  KB-Engine  │ ──────────────────▶ │  Agente lee │
│     IA      │                │ (retrieval) │                     │  documentos │
└─────────────┘                └─────────────┘                     └─────────────┘
```

## Arquitectura

### Dual Stack

| Componente | Local (P2P) | Servidor |
|------------|-------------|----------|
| **Trazabilidad** | SQLite | PostgreSQL |
| **Vectores** | ChromaDB | Qdrant |
| **Grafos** | FalkorDBLite | Neo4j |
| **Embeddings** | sentence-transformers | OpenAI |

### Modelo Distribuido

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Desarrollador 1 │     │  Desarrollador 2 │     │  Desarrollador N │
│  (indexa local)  │     │  (indexa local)  │     │  (indexa local)  │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                         ┌──────────────────┐
                         │  Servidor Central │
                         │  (merge + search) │
                         └──────────────────┘
```

Cada desarrollador indexa localmente con embeddings deterministas. El servidor central hace merge y ofrece búsqueda unificada.

## Características

- **Chunking semántico KDD**: Estrategias específicas para entidades, casos de uso, reglas, procesos
- **Soporte ES/EN**: Detecta patrones en español e inglés
- **Grafo de conocimiento**: Entidades, conceptos, eventos y sus relaciones (FalkorDB/Neo4j)
- **Smart Ingestion**: Pipeline inteligente con detección de tipo de documento
- **CLI**: Interfaz principal via `kb` command

## Quick Start

### Requisitos

- Python 3.11+ (recomendado 3.12)
- (Opcional) Docker para modo servidor

### Instalación (Modo Local)

```bash
# Clonar
git clone https://github.com/leored/kb-engine.git
cd kb-engine

# Crear entorno virtual con Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -e ".[dev]"

# Verificar instalación
pytest tests/ -v
```

El primer `kb index` descargará el modelo de embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, ~120MB).
Los datos locales se almacenan en `~/.kb-engine/` (SQLite, ChromaDB, FalkorDB).

### Instalación (Modo Servidor)

```bash
# Instalar con dependencias de servidor
pip install -e ".[dev,server]"

# Copiar configuración
cp .env.example .env
# Editar .env con tus credenciales

# Levantar servicios (PostgreSQL, Qdrant, Neo4j)
docker compose -f docker/docker-compose.yml up -d

# Ejecutar migraciones
alembic -c migrations/alembic.ini upgrade head
```

### Instalación MCP (para agentes)

```bash
# Instalar con dependencias MCP
pip install -e ".[mcp]"

# Iniciar servidor MCP
kb-mcp
```

El servidor MCP expone las herramientas `kdd_search`, `kdd_related` y `kdd_list` para
que agentes de IA consulten la base de conocimiento.

### Uso (CLI)

```bash
# Indexar documentos
kb index ./docs/domain/

# Buscar
kb search "¿cómo se registra un usuario?"

# Buscar en modo híbrido (vectores + grafo)
kb search "registro de usuario" --mode hybrid

# Ver estado del índice
kb status

# Sincronizar incrementalmente (solo archivos cambiados desde un commit)
kb sync --since abc1234
```

### Administración del grafo (`kb graph`)

Comandos para explorar, inspeccionar y administrar el grafo de conocimiento (FalkorDB).
Todos soportan `--json` para salida estructurada.

```bash
# Estadísticas del grafo
kb graph stats

# Listar nodos (opcionalmente filtrar por tipo)
kb graph ls
kb graph ls --type entity

# Inspeccionar un nodo: vecindario + proveniencia
kb graph inspect entity:User
kb graph inspect entity:User -d 3    # profundidad personalizada

# Verificar alcanzabilidad entre dos nodos
kb graph path entity:User entity:Order
kb graph path entity:User entity:Order --max-depth 3

# Nodos extraídos de un documento
kb graph impact doc-1

# Documentos que contribuyeron a un nodo
kb graph provenance entity:User

# Consulta Cypher directa
kb graph cypher "MATCH (n) RETURN labels(n)[0] as type, count(n) as cnt"

# Eliminar un nodo (pide confirmación, -f para omitirla)
kb graph delete entity:Obsolete
kb graph delete entity:Obsolete -f

# Calidad del grafo
kb graph orphans           # entidades stub sin documento primario
kb graph completeness      # estado de completitud por entidad
kb graph completeness -s stub
```

## Estructura del Proyecto

```
kb-engine/
├── src/kb_engine/
│   ├── core/           # Modelos de dominio e interfaces
│   ├── smart/          # Pipeline de ingesta inteligente (FalkorDB)
│   │   ├── parsers/    # Detectores y parsers KDD
│   │   ├── chunking/   # Chunking jerárquico con contexto
│   │   ├── extraction/ # Extracción de entidades para grafo
│   │   ├── stores/     # FalkorDBGraphStore
│   │   ├── schemas/    # Esquemas de templates KDD
│   │   └── pipelines/  # EntityIngestionPipeline
│   ├── repositories/   # Implementaciones de storage
│   ├── chunking/       # Estrategias de chunking clásicas
│   ├── extraction/     # Pipeline de extracción legacy
│   ├── embedding/      # Configuración de embeddings
│   ├── pipelines/      # Pipelines de indexación/retrieval
│   ├── services/       # Lógica de negocio
│   ├── api/            # REST API (FastAPI)
│   ├── cli.py          # Comandos CLI (Click)
│   └── mcp_server.py   # Servidor MCP para agentes
├── tests/
│   ├── unit/
│   └── integration/
└── docs/design/        # ADRs y documentos de diseño
```

## Documentos KDD Soportados

| Tipo | Descripción |
|------|-------------|
| `entity` | Entidades de dominio (Usuario, Producto, etc.) |
| `use-case` | Casos de uso del sistema |
| `rule` | Reglas de negocio |
| `process` | Procesos y flujos |
| `event` | Eventos de dominio |
| `glossary` | Términos y definiciones |

## API

```bash
# Health check
GET /health

# Búsqueda (devuelve referencias)
POST /api/v1/retrieval/search
{
  "query": "registro de usuario",
  "top_k": 5
}

# Indexar documento
POST /api/v1/indexing/documents

# Listar documentos
GET /api/v1/indexing/documents
```

## Tests

```bash
# Todos los tests
pytest tests/ -v

# Solo unitarios
pytest tests/unit/ -v

# Solo integración
pytest tests/integration/ -v

# Con coverage
pytest tests/ --cov=kb_engine
```

## Configuración

Variables de entorno (`.env`). Ver `.env.example` para la lista completa.

```bash
# --- Perfil ---
KB_PROFILE=local          # "local" (defecto) o "server"

# --- Rutas locales (perfil local) ---
SQLITE_PATH=~/.kb-engine/kb.db
CHROMA_PATH=~/.kb-engine/chroma
FALKORDB_PATH=~/.kb-engine/graph.db

# --- Embeddings ---
EMBEDDING_PROVIDER=local  # "local" (sentence-transformers) o "openai"
LOCAL_EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
OPENAI_API_KEY=sk-...     # solo si EMBEDDING_PROVIDER=openai

# --- Perfil servidor ---
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/kb_engine
QDRANT_HOST=localhost
QDRANT_PORT=6333
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=changeme
```

## Roadmap

- [x] Stack local con SQLite + ChromaDB
- [x] Smart ingestion pipeline con FalkorDB
- [x] CLI completo (`kb index/search/sync/status/graph`)
- [x] Integración MCP para agentes
- [ ] Sincronización P2P con servidor

## Licencia

MIT
