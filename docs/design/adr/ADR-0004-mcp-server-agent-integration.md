# ADR-0004: MCP Server para Integración con Agentes de IA

---
id: ADR-0004
status: superseded
superseded_note: "Migración a TypeScript/Bun (Feb 2026). MCP server reimplementado en src/mcp.ts usando @modelcontextprotocol/sdk (TS). 7 tools (kdd_search, kdd_find_spec, kdd_related, kdd_impact, kdd_read_section, kdd_list, kdd_stats). Sin CLI fallback ni FastMCP."
date: 2025-02-07
deciders: [leopoldo, claude]
consulted: []
informed: []
related_dc: DC-012
supersedes: null
superseded_by: null
---

## Contexto

Los agentes de codificación (Claude Code, Cursor, Windsurf) buscan información en codebases y documentación usando herramientas **sintácticas** (Grep, Glob, Read). Estas herramientas son ineficientes para búsquedas conceptuales ("cómo funciona la autenticación"), donde el agente necesita múltiples rondas de prueba y error.

KB-Engine dispone de un `RetrievalPipeline` que resuelve este problema con búsqueda semántica, devolviendo `DocumentReference` con URLs directas (`file://path#anchor`). El reto es exponer esta capacidad a los agentes de forma eficiente.

### Análisis de rendimiento

El cuello de botella en la interacción agente-herramienta **no es el protocolo** sino los **inference round-trips**: cada tool call requiere un pase completo de inferencia del modelo (~1-3 segundos). Según [Anthropic Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use):

- **Programmatic Tool Calling** elimina 19+ inference passes en workflows complejos (37% menos tokens)
- **Tool Use Examples** mejoran la precisión de invocación de 72% a 90% (evitando retries)
- El overhead de MCP (stdio JSON-RPC) es despreciable frente al coste de inferencia

Se evaluaron 4 opciones en DC-012:
- A: CLI Agent-Friendly via Bash (bajo esfuerzo, pero startup lento y sin Programmatic Tool Calling)
- B: MCP Server puro (descubrimiento nativo, pero sin fallback CLI)
- C: Enfoque híbrido por fases (CLI primero, MCP después)
- D: MCP Server con CLI como fallback (una implementación, dos interfaces)

## Decisión

**Implementamos un MCP Server usando el Python SDK (`mcp` + `FastMCP`) que expone 3 tools semánticos, con un CLI fallback para testing y agentes sin soporte MCP.**

### Arquitectura

```
Agente (Claude Code / Cursor / Windsurf)
    │
    │ stdio (MCP JSON-RPC)
    │
    ▼
┌──────────────────────────────────────────────────┐
│  kb-engine MCP Server                            │
│  src/kb_engine/mcp_server.py                     │
│  (FastMCP, proceso persistente)                  │
├──────────────────────────────────────────────────┤
│                                                  │
│  kdd_search ──→ RetrievalService.search()        │
│  kdd_related ──→ GraphRepository.traverse()      │
│  kdd_list ────→ TraceabilityRepository.list()    │
│                                                  │
│  Embedding model cargado en memoria (lazy init)  │
│                                                  │
├──────────────────────────────────────────────────┤
│  CLI fallback: python -m kb_engine.mcp_server    │
│  --cli search "query"                            │
└──────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  Servicios y repositorios existentes             │
│  RetrievalPipeline / RetrievalService            │
│  RepositoryFactory → SQLite + ChromaDB + Graph   │
└──────────────────────────────────────────────────┘
```

### Tools MCP

#### 1. `kdd_search` — Búsqueda semántica

```python
@mcp.tool(
    examples=[
        {
            "query": "how does authentication work",
            "limit": 3,
        },
        {
            "query": "validation rules for user input",
            "chunk_types": ["RULE", "PROCESS"],
            "domains": ["security"],
        },
    ]
)
async def kdd_search(
    query: str,
    limit: int = 5,
    chunk_types: list[str] | None = None,
    domains: list[str] | None = None,
    tags: list[str] | None = None,
    score_threshold: float | None = None,
) -> str:
    """Search indexed documentation using semantic similarity.

    Returns document references with file:// URLs and section anchors.
    Use the Read tool to access the content at the returned URLs.

    Prefer this over Grep when searching for concepts, processes, or
    relationships rather than exact text matches.

    Args:
        query: Natural language search query (e.g. "how does auth work")
        limit: Maximum number of results to return (default: 5)
        chunk_types: Filter by chunk type: ENTITY, USE_CASE, RULE, PROCESS, DEFAULT
        domains: Filter by project/domain name
        tags: Filter by document tags
        score_threshold: Minimum similarity score (0.0-1.0)
    """
```

**Output format** (JSON compacto):
```json
{
  "results": [
    {
      "url": "file:///path/to/auth.md#authentication-flow",
      "title": "Authentication System",
      "section": "Authentication Flow",
      "score": 0.87,
      "snippet": "El flujo de autenticación usa OAuth2 con tokens JWT...",
      "type": "PROCESS",
      "domain": "security"
    }
  ],
  "count": 3,
  "time_ms": 245
}
```

**Reutiliza**: `RetrievalService.search()` → `RetrievalPipeline._vector_search()` → `DocumentReference`

#### 2. `kdd_related` — Exploración de grafo

```python
@mcp.tool(
    examples=[
        {
            "entity": "AuthenticationService",
            "depth": 2,
        },
        {
            "entity": "RF-AUTH-001",
            "edge_types": ["IMPLEMENTS", "DEPENDS_ON"],
        },
    ]
)
async def kdd_related(
    entity: str,
    depth: int = 1,
    edge_types: list[str] | None = None,
    limit: int = 20,
) -> str:
    """Find entities related to the given entity in the knowledge graph.

    Useful for understanding dependencies, relationships, and context
    around a specific component, requirement, or concept.

    Args:
        entity: Name of the entity to explore (e.g. "AuthService", "RF-001")
        depth: How many hops to traverse (default: 1, max: 3)
        edge_types: Filter by relationship: IMPLEMENTS, DEPENDS_ON, REFERENCES, etc.
        limit: Maximum related entities to return
    """
```

**Output format**:
```json
{
  "entity": "AuthenticationService",
  "type": "ENTITY",
  "related": [
    {
      "name": "TokenValidator",
      "type": "ENTITY",
      "relation": "DEPENDS_ON",
      "direction": "outgoing",
      "source_url": "file:///path/to/auth.md#token-validation"
    },
    {
      "name": "RF-AUTH-001",
      "type": "USE_CASE",
      "relation": "IMPLEMENTS",
      "direction": "outgoing",
      "source_url": "file:///path/to/requirements.md#rf-auth-001"
    }
  ],
  "count": 2
}
```

**Reutiliza**: `GraphRepository.traverse()` + `TraceabilityRepository.get_document()`

#### 3. `kdd_list` — Inventario del índice

```python
@mcp.tool(
    examples=[
        {"domain": "security"},
        {"kind": "requirement", "limit": 10},
    ]
)
async def kdd_list(
    kind: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> str:
    """List indexed documents with metadata.

    Quick inventory of what documentation is available in the knowledge base.
    Like 'ls' but for the semantic index.

    Args:
        kind: Filter by document kind from frontmatter (e.g. "requirement", "entity")
        domain: Filter by project/domain name
        status: Filter by index status: INDEXED, PENDING, FAILED
        limit: Maximum documents to return (default: 20)
    """
```

**Output format**:
```json
{
  "documents": [
    {
      "path": "docs/requirements/auth.md",
      "title": "Authentication Requirements",
      "kind": "requirement",
      "domain": "security",
      "status": "INDEXED",
      "chunks": 12,
      "entities": 5,
      "indexed_at": "2025-02-07T10:30:00Z"
    }
  ],
  "total": 47
}
```

**Reutiliza**: `TraceabilityRepository.list_documents()`

### Principios de diseño de los tools

1. **Devolver URLs, no contenido**: Alineado con la arquitectura `DocumentReference`. El agente recibe `file:///path#anchor` y usa `Read` para acceder al contenido. Mantiene las respuestas pequeñas (<4KB).

2. **Snippets cortos**: Máximo 150 caracteres por snippet. Suficiente para que el agente decida si leer el documento completo, sin contaminar el contexto.

3. **Filtros opcionales**: Todos los parámetros de filtrado son opcionales. La búsqueda más simple es `kdd_search(query="...")`. Los filtros añaden precisión cuando el agente conoce el dominio.

4. **Input examples**: Cada tool incluye `examples` que demuestran invocaciones mínimas y con filtros. Según Anthropic, esto mejora la precisión de 72% a 90%.

5. **Descripciones orientadas al agente**: Las docstrings explican **cuándo** usar el tool (vs Grep/Glob), no solo qué hace.

### Registro MCP

**Opción 1 — Fichero `.mcp.json` en raíz del proyecto** (compartido con equipo):
```json
{
  "mcpServers": {
    "kb-engine": {
      "command": "python",
      "args": ["-m", "kb_engine.mcp_server"],
      "cwd": "/path/to/kb-engine",
      "env": {
        "KB_PROFILE": "local"
      }
    }
  }
}
```

**Opción 2 — Registro manual por usuario**:
```bash
claude mcp add kb-engine -- python -m kb_engine.mcp_server
```

### CLI Fallback

El mismo módulo soporta invocación directa para testing y agentes sin MCP:

```bash
# Modo MCP (default) — proceso persistente stdio
python -m kb_engine.mcp_server

# Modo CLI — ejecución única
python -m kb_engine.mcp_server --cli search "how does auth work" --limit 3
python -m kb_engine.mcp_server --cli related AuthService --depth 2
python -m kb_engine.mcp_server --cli list --domain security
```

La implementación interna es compartida: tanto MCP tools como CLI wrappers llaman a las mismas funciones `_do_search()`, `_do_related()`, `_do_list()`.

### Compatibilidad con Programmatic Tool Calling

Los tools se diseñan para ser encadenables en código:

```python
# El agente escribe este código en UN solo pase de inferencia
# (sin round-trips intermedios)
results = kdd_search("authentication flow")
auth_entities = []
for r in results["results"][:3]:
    if r.get("type") == "ENTITY":
        related = kdd_related(r["title"])
        auth_entities.extend(related["related"])

# Solo el resultado final entra al contexto del modelo
return {
    "auth_docs": results["results"],
    "auth_graph": auth_entities,
    "summary": f"Found {results['count']} docs and {len(auth_entities)} related entities"
}
```

Esto requiere que los tools:
- Devuelvan JSON parseable (no texto libre)
- Sean idempotentes (seguros para retry)
- Tengan output documentado para que el agente escriba código correcto

### Gestión de recursos

```python
# Lazy initialization del pipeline
_retrieval_service: RetrievalService | None = None
_factory: RepositoryFactory | None = None

async def _get_service() -> RetrievalService:
    """Lazy init: carga modelo de embeddings solo al primer search."""
    global _retrieval_service, _factory
    if _retrieval_service is None:
        settings = get_settings()
        _factory = RepositoryFactory(settings)
        # ... crear pipeline y servicio
        _retrieval_service = RetrievalService(pipeline=retrieval_pipeline)
    return _retrieval_service
```

- **Embedding model**: Se carga en memoria la primera vez que se invoca `kdd_search`. Permanece en memoria mientras el proceso MCP viva.
- **Conexiones DB**: SQLite y ChromaDB se abren al init, se mantienen abiertas.
- **Cleanup**: `atexit` handler para cerrar conexiones al terminar el proceso.

## Justificación

1. **Proceso persistente elimina startup cost**: Cada invocación CLI tendría ~2-3s de startup (Python + modelo de embeddings). El proceso MCP carga una vez y responde en ~200-400ms por búsqueda.

2. **Descubrimiento automático**: Los tools MCP aparecen en la lista de herramientas del agente sin que el usuario configure nada más que el registro MCP. No requiere que el agente lea `CLAUDE.md`.

3. **Programmatic Tool Calling**: Permite encadenar `search → related → list` en un solo pase de inferencia. Un workflow de 4 herramientas que tomaría ~12s con round-trips individuales se completa en ~4s.

4. **Una implementación, dos interfaces**: La lógica core (`_do_search`, `_do_related`, `_do_list`) se implementa una sola vez. MCP y CLI son wrappers delgados sobre las mismas funciones.

5. **Wrapper sobre servicios existentes**: No reimplementa búsqueda — delega en `RetrievalService`, `GraphRepository` y `TraceabilityRepository` ya existentes y testeados.

6. **Estándar multi-agente**: MCP es adoptado por Claude Code, Cursor, Windsurf. Una sola implementación funciona con todos.

## Alternativas Consideradas

### Alternativa 1: CLI Agent-Friendly (solo Bash)

Optimizar `kb search --format json` para invocación via Bash tool.

**Descartada porque**:
- Startup cost de ~2-3s por invocación (proceso nuevo cada vez)
- No compatible con Programmatic Tool Calling
- Descubrimiento depende de `CLAUDE.md` (menos fiable)
- El agente parsea texto plano en vez de JSON Schema tipado

### Alternativa 2: Enfoque Híbrido por Fases

CLI primero (Fase 1), MCP después (Fase 2).

**Descartada porque**:
- El esfuerzo de Fase 1 (CLI `--format json` + `CLAUDE.md`) no se reutiliza bien en Fase 2
- Dos interfaces que mantener desde el principio
- Posponer MCP no tiene justificación técnica — el SDK `FastMCP` simplifica la implementación

### Alternativa 3: MCP Server Puro (sin CLI)

Solo MCP, sin fallback CLI.

**Descartada porque**:
- Sin CLI no hay forma fácil de testear los tools fuera del contexto MCP
- Agentes sin soporte MCP quedan excluidos
- El CLI fallback tiene coste de implementación mínimo

## Consecuencias

### Positivas

- Los agentes acceden a búsqueda semántica con la misma naturalidad que Grep o Read
- Latencia de búsqueda ~200-400ms (vs ~2-3s con CLI por startup)
- Workflows complejos (search+related+filter) en un solo pase de inferencia
- Compatible con el ecosistema creciente de agentes MCP
- CLI fallback permite testing manual y scripting

### Negativas

- Dependencia nueva: `mcp` Python SDK (~lightweight, mantenido por Anthropic)
- Proceso daemon en background mientras el agente trabaja (consume memoria)
- El modelo de embeddings permanece en memoria (~200-500MB para sentence-transformers)

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| MCP SDK cambia API (pre-1.0) | Media | Medio | FastMCP abstrae los detalles; pin version |
| Proceso MCP se queda colgado | Baja | Bajo | Claude Code gestiona lifecycle; health check |
| Embeddings en memoria consumen demasiado | Baja | Medio | Lazy loading; considerar modelo más pequeño |
| Programmatic Tool Calling no disponible en todos los agentes | Media | Bajo | Los tools funcionan individualmente también |

## Plan de Implementación

- [ ] Crear módulo `src/kb_engine/mcp_server.py` con FastMCP
- [ ] Implementar `kdd_search` delegando a `RetrievalService.search()`
- [ ] Implementar `kdd_list` delegando a `TraceabilityRepository.list_documents()`
- [ ] Implementar `kdd_related` delegando a `GraphRepository.traverse()`
- [ ] Añadir lazy initialization del pipeline y gestión de recursos
- [ ] Añadir CLI fallback (`--cli` mode)
- [ ] Añadir `input_examples` a cada tool
- [ ] Crear `.mcp.json` template para registro en proyectos
- [ ] Añadir `mcp` a dependencias opcionales (`pip install kb-engine[mcp]`)
- [ ] Tests: unitarios (mock services) + integración (MCP client → server)
- [ ] Documentar setup en README

## Referencias

- [Design Challenge DC-012](../challenges/DC-012-agent-tool-integration.md)
- [Anthropic - Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP Python SDK (FastMCP)](https://github.com/modelcontextprotocol/python-sdk)
- [Claude Code MCP Configuration](https://docs.anthropic.com/en/docs/claude-code/mcp)
