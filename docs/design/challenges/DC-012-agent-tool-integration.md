# DC-012: Integración de Herramientas para Agentes de IA

---
id: DC-012
status: decided
priority: alta
created: 2025-02-07
updated: 2025-02-07
owner: leopoldo
adrs: [ADR-0004]
---

## 1. Contexto

Los agentes de codificación (Claude Code, Cursor, Windsurf, etc.) buscan información en el codebase y documentación usando herramientas de búsqueda **sintáctica**: `Grep` (regex en contenido), `Glob` (patrones de ficheros), `Read` (lectura de ficheros), y `Bash` (comandos shell). Estas herramientas funcionan bien para búsquedas exactas ("encuentra la clase `AuthService`"), pero son ineficientes para búsquedas conceptuales ("cómo funciona la autenticación"), ya que el agente debe adivinar nombres de ficheros y patrones grep, a menudo realizando múltiples rondas de prueba y error.

KDD-Engine ya dispone de un sistema de retrieval semántico que resuelve exactamente este problema: búsqueda vectorial sobre chunks de documentación, con resolución de URLs (`DocumentReference`) que apuntan al fichero y sección exacta. El reto es **exponer esta capacidad a los agentes de IA** de la forma más eficiente y natural posible.

### Cómo buscan los agentes hoy

| Herramienta | Propósito | Limitación |
|------------|-----------|------------|
| **Glob** | Buscar ficheros por patrón (`**/*.py`) | Solo nombres, sin contenido |
| **Grep** | Buscar contenido por regex | Solo match exacto/regex, sin semántica |
| **Read** | Leer fichero completo o parcial | Debe saber qué fichero leer |
| **Bash** | Ejecutar comandos (`find`, `git log`) | Textual, sin contexto semántico |
| **Task/Explore** | Exploración multi-paso | Encadena las herramientas anteriores, lento |

### Gap identificado

Cuando un agente necesita encontrar "cómo funciona X" en la documentación:
1. Intenta `Grep("autenticación")` → solo encuentra menciones literales
2. Intenta `Glob("**/auth*.md")` → depende de naming conventions
3. Lee ficheros candidatos con `Read` → múltiples round-trips
4. Puede repetir 3-5 ciclos hasta encontrar lo relevante

Con búsqueda semántica: una sola llamada devuelve los chunks más relevantes con URLs directas.

### Cuello de botella real: inference round-trips, no protocolo

Cada tool call (sea Grep, Read, o una herramienta MCP) requiere un **pase completo de inferencia** del modelo. El overhead del protocolo MCP (stdio JSON-RPC) es despreciable (microsegundos) comparado con el coste de inferencia (~1-3 segundos por round-trip). El factor limitante es el **número de llamadas**, no la velocidad de cada una.

Referencia: [Anthropic - Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

### Capacidades existentes en kdd-engine

| Componente | Estado | Relevancia |
|-----------|--------|------------|
| `RetrievalPipeline.search()` | Implementado | Búsqueda vectorial con filtros |
| `RetrievalService.search()` | Implementado | Capa de servicio sobre pipeline |
| `DocumentReference` | Implementado | URLs con `file://path#anchor` |
| `SearchFilters` | Implementado | Filtros por dominio, tags, chunk_type, fecha |
| `kb search` (CLI) | Implementado | Comando Click, output texto |
| Graph search | Placeholder | `_graph_search()` devuelve `[]` |
| Traceability listing | Implementado | `list_documents()`, `get_chunk()` |

## 2. Requisitos y Restricciones

### 2.1 Requisitos Funcionales

- [ ] RF1: Búsqueda semántica accesible como herramienta del agente (natural language → resultados relevantes)
- [ ] RF2: Output estructurado con URLs directas a fichero+sección para que el agente use `Read`
- [ ] RF3: Filtrado por tipo de chunk, dominio, tags (parámetros opcionales)
- [ ] RF4: Exploración de entidades relacionadas vía grafo de conocimiento
- [ ] RF5: Listado de documentos indexados con metadatos
- [ ] RF6: Formato de salida optimizado para consumo por agentes (mínimo ruido, máxima información)
- [ ] RF7: Compatible con Programmatic Tool Calling (encadenamiento sin round-trips intermedios)

### 2.2 Requisitos No Funcionales

- [ ] RNF1: Latencia de búsqueda < 2 segundos (incluyendo embedding de query)
- [ ] RNF2: Output < 4KB por llamada (evitar polución del contexto del modelo)
- [ ] RNF3: Descubrimiento natural por el agente (sin configuración manual compleja)
- [ ] RNF4: Zero-dependency adicional en el entorno del usuario para Fase 1
- [ ] RNF5: Tool descriptions claras para que el agente use los parámetros correctamente en el primer intento

### 2.3 Restricciones

- Debe reutilizar `RetrievalPipeline`, `RetrievalService` y repositorios existentes (wrapper, no reimplementación)
- Los resultados devuelven `DocumentReference` con URLs, no contenido crudo
- El agente debe poder usar su propia herramienta `Read` para acceder al contenido tras recibir la URL
- Compatible con el modelo de profiles (local/server)

## 3. Opciones Consideradas

### Opción A: CLI Agent-Friendly (Bash Tool)

**Descripción**: Optimizar el CLI existente (`kb`) con output JSON estructurado y nuevos subcomandos. El agente lo invoca via su herramienta `Bash` existente.

```bash
# Búsqueda semántica
kb search "cómo funciona la autenticación" --format json --limit 5

# Entidades relacionadas
kb related AuthService --depth 2 --format json

# Listado filtrado
kb list --kind requirement --status indexed --format json
```

```json
// Output de kb search --format json
{
  "query": "cómo funciona la autenticación",
  "results": [
    {
      "url": "file:///path/to/auth.md#authentication-flow",
      "title": "Authentication System",
      "section": "Authentication Flow",
      "score": 0.87,
      "snippet": "El flujo de autenticación usa OAuth2 con tokens JWT...",
      "chunk_type": "PROCESS",
      "domain": "security"
    }
  ],
  "count": 5,
  "time_ms": 342
}
```

**Integración con el agente**: Se documenta en `CLAUDE.md` del proyecto:
```markdown
## Herramientas de búsqueda semántica
Este proyecto tiene un índice semántico de documentación. Usa estos comandos antes de buscar con Grep:
- `kb search "<query>" --format json --limit 5` — Búsqueda semántica en documentación
- `kb related <entity> --format json` — Entidades relacionadas en el grafo
- `kb list --format json` — Inventario de documentos indexados
```

**Pros**:
- Cero dependencias nuevas — usa Bash tool que ya existe
- El CLI (`kb`) ya está implementado, solo necesita `--format json` y subcomandos nuevos
- `CLAUDE.md` es el mecanismo estándar de descubrimiento
- Funciona con cualquier agente que tenga shell access
- Implementación inmediata (días, no semanas)

**Contras**:
- El agente debe leer `CLAUDE.md` y "recordar" que existe la herramienta
- No aparece en la lista de tools del agente (menos descubrible)
- Output es texto que el agente parsea (aunque JSON es fácil)
- No compatible con Programmatic Tool Calling (no puede marcar `allowed_callers`)
- Cada invocación es un proceso nuevo (startup de Python, carga de modelos de embedding)

**Esfuerzo estimado**: Bajo

---

### Opción B: MCP Server (Protocol Nativo)

**Descripción**: Implementar un servidor MCP usando el Python SDK (`mcp` + `FastMCP`) que expone las capacidades de kdd-engine como tools nativos del agente.

```python
# src/kdd_engine/mcp_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kdd-engine")

@mcp.tool()
async def kdd_search(
    query: str,
    limit: int = 5,
    chunk_types: list[str] | None = None,
    domains: list[str] | None = None,
) -> str:
    """Search indexed documentation using semantic similarity.

    Returns document references with file URLs and section anchors.
    Use the Read tool to access the content at the returned URLs.

    Args:
        query: Natural language search query
        limit: Maximum results (default 5)
        chunk_types: Filter by type: ENTITY, USE_CASE, RULE, PROCESS, DEFAULT
        domains: Filter by domain/project name
    """
    response = await retrieval_service.search(
        query=query, limit=limit,
        filters=SearchFilters(chunk_types=chunk_types, domains=domains),
    )
    return format_references(response)

@mcp.tool()
async def kdd_related(
    entity: str,
    depth: int = 1,
) -> str:
    """Find entities related to the given entity in the knowledge graph.

    Returns connected entities with their types and relationships.
    """
    ...

@mcp.tool()
async def kdd_list(
    kind: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> str:
    """List indexed documents with metadata.

    Shows what documentation is available in the knowledge base.
    """
    ...
```

**Registro en el proyecto**:
```json
// .mcp.json (raíz del proyecto)
{
  "mcpServers": {
    "kdd-engine": {
      "command": "python",
      "args": ["-m", "kdd_engine.mcp_server"],
      "env": {
        "KB_PROFILE": "local"
      }
    }
  }
}
```

O registro manual:
```bash
claude mcp add kdd-engine -- python -m kdd_engine.mcp_server
```

**Pros**:
- Tools aparecen en la lista nativa del agente (descubrimiento automático)
- Input/output con JSON Schema (el agente conoce los parámetros disponibles)
- Compatible con Programmatic Tool Calling (`allowed_callers: ["code_execution"]`)
- Proceso persistente — no hay startup cost por llamada (embeddings cargados en memoria)
- `input_examples` mejoran la precisión de invocación (72% → 90% según Anthropic)
- Transportable a otros agentes que soporten MCP (Cursor, Windsurf, etc.)

**Contras**:
- Requiere `mcp` como dependencia nueva
- Proceso daemon en background mientras el agente trabaja
- Más código que mantener (módulo MCP server)
- Solo funciona con agentes que soporten MCP

**Esfuerzo estimado**: Medio

---

### Opción C: Enfoque Híbrido por Fases

**Descripción**: Combinar A y B en dos fases progresivas. Fase 1 entrega valor inmediato via CLI; Fase 2 añade MCP cuando se necesite encadenamiento avanzado.

#### Fase 1: CLI Agent-Friendly (inmediata)

Añadir a la CLI existente:

```python
# Extensiones al CLI existente (cli.py)

@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=5)
@click.option("--format", "-f", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.option("--chunk-type", "-c", multiple=True, help="Filter by chunk type")
@click.option("--domain", "-d", multiple=True, help="Filter by domain")
def search(query, limit, output_format, chunk_type, domain):
    """Search the knowledge base."""
    # ... existing logic + json output format
```

Crear `CLAUDE.md` con instrucciones de uso:

```markdown
## Semantic Search Tools

This project has a semantic search index. Before doing multiple grep rounds, try:

### Search documentation
`kb search "<natural language query>" --format json --limit 5`

### Check what's indexed
`kb status`
```

**Entrega**: CLI mejorado + `CLAUDE.md` → el agente puede usarlo inmediatamente.

#### Fase 2: MCP Server (cuando se necesite)

Trigger para Fase 2: cuando se observe que los agentes necesitan:
- Encadenar búsquedas (search → related → read) sin round-trips intermedios
- Filtrado complejo que es difícil expresar en flags CLI
- Integración con múltiples IDEs/agentes simultáneamente

```python
# src/kdd_engine/mcp_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kdd-engine", instructions="""
KDD-Engine provides semantic search over indexed project documentation.
Use kdd_search before falling back to Grep for conceptual queries.
Results return file URLs - use Read to access the content.
""")

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
) -> str:
    """Search indexed documentation using semantic similarity.

    Returns document references with file:// URLs and section anchors.
    Use the Read tool to access the content at the returned URLs.

    Prefer this over Grep when searching for concepts, processes, or
    relationships rather than exact text matches.
    """
    ...

@mcp.tool()
async def kdd_related(entity: str, depth: int = 1) -> str:
    """Find entities related to the given entity in the knowledge graph.

    Useful for understanding dependencies, relationships, and context
    around a specific component, requirement, or concept.
    """
    ...

@mcp.tool()
async def kdd_list(
    kind: str | None = None,
    domain: str | None = None,
    limit: int = 20,
) -> str:
    """List indexed documents with metadata.

    Quick inventory of what documentation is available in the knowledge base.
    Like 'ls' but for the semantic index.
    """
    ...
```

**Compatibilidad con Programmatic Tool Calling**:
```python
# Los tools se marcan como seguros para ejecución programática
@mcp.tool(allowed_callers=["code_execution_20250825"])
async def kdd_search(...):
    ...
```

Esto permite que Claude escriba código que encadena búsquedas:
```python
# Claude genera este código en un solo paso
results = kdd_search("authentication flow")
for r in results[:3]:
    related = kdd_related(r["entity"])
# Solo el resultado final entra al contexto
return {"auth_docs": results, "related_entities": related}
```

**Pros**:
- Fase 1 entrega valor inmediato con esfuerzo mínimo
- Fase 2 se construye sobre Fase 1 (reutiliza la misma lógica)
- Decisión de MCP se toma con datos reales de uso
- CLI funciona para cualquier agente; MCP añade optimización
- Ambas fases reutilizan `RetrievalPipeline` y `RetrievalService`

**Contras**:
- Dos interfaces que mantener a largo plazo
- CLAUDE.md es menos descubrible que tools nativos
- Requiere disciplina para no saltarse Fase 1 directamente a Fase 2

**Esfuerzo estimado**: Bajo (Fase 1) + Medio (Fase 2)

---

### Opción D: MCP Server con CLI como Fallback

**Descripción**: Implementar MCP server directamente (sin fase CLI intermedia), pero asegurar que el server también sea invocable como CLI para testing y agentes sin MCP.

```python
# src/kdd_engine/mcp_server.py
# El server ES el CLI a la vez

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kdd-engine")

@mcp.tool()
async def kdd_search(query: str, limit: int = 5, ...) -> str:
    """..."""
    return await _do_search(query, limit, ...)

# CLI wrapper para la misma lógica
@click.command()
@click.argument("query")
def search_cli(query):
    result = asyncio.run(_do_search(query, limit=5))
    click.echo(result)

if __name__ == "__main__":
    # Si se ejecuta directamente → CLI
    # Si se invoca por MCP → server
    import sys
    if "--cli" in sys.argv:
        search_cli()
    else:
        mcp.run()
```

**Pros**:
- Una sola implementación, dos interfaces
- MCP desde el inicio (descubrimiento nativo)
- CLI disponible para testing y fallback
- Proceso persistente para MCP (sin startup cost)

**Contras**:
- Requiere `mcp` como dependencia desde el inicio
- Más complejidad inicial
- El dual-mode puede ser confuso

**Esfuerzo estimado**: Medio

## 4. Análisis Comparativo

| Criterio | Peso | A: CLI | B: MCP | C: Híbrido | D: MCP+CLI |
|----------|------|--------|--------|------------|------------|
| Esfuerzo inicial | 2 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Descubrimiento por agente | 3 | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Latencia por llamada | 3 | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Reducción de round-trips | 3 | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Compatibilidad multi-agente | 2 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Mantenibilidad | 2 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Programmatic Tool Calling | 3 | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Total ponderado** | | 28 | 47 | 38 | 50 |

### Notas sobre la puntuación

- **Latencia por llamada**: CLI (A) puntúa bajo porque cada `kb search` es un proceso nuevo (startup Python ~1-2s + carga embedding model ~1s). MCP (B, D) mantiene el proceso vivo y modelos en memoria.
- **Reducción de round-trips**: Solo MCP permite Programmatic Tool Calling donde Claude escribe código que encadena múltiples herramientas en una sola ejecución.
- **Descubrimiento**: CLI requiere que el agente lea `CLAUDE.md` primero. MCP tools aparecen automáticamente en la lista de herramientas disponibles.

## 5. Preguntas Abiertas

### Diseño de Tools

- [ ] ¿El output debe incluir snippets del contenido, o solo URLs? (trade-off: contexto inmediato vs tamaño de respuesta)
- [ ] ¿Qué tamaño máximo de snippet es útil sin contaminar el contexto del modelo? (¿120 chars? ¿300?)
- [ ] ¿Se necesita un tool `kdd_read` que devuelva el contenido completo del chunk, o basta con que el agente use `Read` en la URL?

### Performance

- [ ] ¿Cuál es el startup time actual de `kb search`? (determina si el CLI es viable sin optimizar)
- [ ] ¿El modelo de embeddings local (`sentence-transformers`) puede mantenerse en memoria en el proceso MCP?
- [ ] ¿Se necesita lazy loading del modelo de embeddings (cargar solo al primer search)?

### Integración

- [ ] ¿Qué agentes además de Claude Code se necesitan soportar? (Cursor, Windsurf, Copilot)
- [ ] ¿El `.mcp.json` debe ir en el repo de documentación o en el repo del proyecto que se documenta?
- [ ] ¿Se necesita soporte para MCP remoto (HTTP/SSE) además de stdio para el perfil `server`?

### Programmatic Tool Calling

- [ ] ¿Cuáles son los workflows de búsqueda más comunes que se beneficiarían de encadenamiento? (ej: search → related → read)
- [ ] ¿El SDK de MCP actual soporta `allowed_callers` o es feature solo de la API directa de Anthropic?

### Adopción

- [ ] ¿Se prefiere que el agente use `kdd_search` **en lugar de** o **además de** Grep/Glob?
- [ ] ¿Cómo instruir al agente para que prefiera búsqueda semántica para consultas conceptuales y Grep para búsquedas exactas?

## 6. Decisión

> **Estado**: Decidido

**Opción seleccionada**: D - MCP Server con CLI como Fallback

**Justificación**:
- El cuello de botella real no es el protocolo MCP sino los **inference round-trips** del modelo. MCP no añade latencia significativa.
- El proceso MCP persistente elimina el **startup cost** (~2-3s) que tendría el CLI en cada invocación (carga de Python + modelo de embeddings).
- La compatibilidad con **Programmatic Tool Calling** (Anthropic Advanced Tool Use) permite que el agente encadene búsquedas en un solo pase de inferencia, reduciendo drásticamente la latencia total.
- El **descubrimiento automático** de tools MCP (vs `CLAUDE.md` para CLI) asegura que el agente use la búsqueda semántica sin configuración manual.
- La opción D mantiene una **única implementación** con dos interfaces (MCP + CLI fallback), evitando duplicación de lógica.
- Compatible con **múltiples agentes** (Claude Code, Cursor, Windsurf) que adoptan MCP como estándar.

**ADRs generados**:
- [ADR-0004: MCP Server para Integración con Agentes de IA](../adr/ADR-0004-mcp-server-agent-integration.md)

## 7. Referencias

- [Anthropic - Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use) — Tool Search, Programmatic Calling, Tool Examples
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — Especificación del protocolo
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — SDK oficial con FastMCP
- [Claude Code - MCP Configuration](https://docs.anthropic.com/en/docs/claude-code/mcp) — Configuración de MCP en Claude Code
- [claude-context (Zilliz)](https://github.com/zilliztech/mcp-server-milvus) — Semantic search MCP server existente
- [CLAUDE.md Documentation](https://docs.anthropic.com/en/docs/claude-code/memory) — Mecanismo de instrucciones persistentes
