---
id: PRD-KDDEngine
kind: prd
status: draft
owner: platform-team
stakeholders: [engineering, product, qa, ai-agents]
related: [UC-001-IndexDocument, UC-004-RetrieveContext, UC-006-MergeIndex, OBJ-001-AgentRetrieval, OBJ-002-DistributedIndexing]
success_metrics:
  - "Retrieval precision ≥90% en queries de agentes sobre specs KDD"
  - "Tiempo de indexación incremental <2s por documento modificado (local)"
  - "Tiempo de retrieval P95 <300ms"
  - "Coste de indexación distribuido: ≥80% del cómputo ejecutado en local"
release_criteria:
  - "BDD features en verde para todos los kinds KDD"
  - "Indexación y retrieval funcional para ≥3 kinds (entity, command, business-rule)"
  - "Merge de índices de ≥2 desarrolladores sin conflictos"
---

# KDD Engine — KDD Retrieval Engine for Agents

## Problema / Oportunidad

Los agentes de código (Codex, Claude Code, Cursor, etc.) necesitan contexto preciso para generar, modificar y razonar sobre software. Hoy, la mayoría de sistemas RAG se centran en indexar código fuente con técnicas genéricas (chunking + embeddings), lo que produce:

- **Retrieval impreciso**: los agentes reciben fragmentos de código sin contexto funcional.
- **Pérdida de intención**: el "por qué" (reglas de negocio, decisiones, requisitos) se pierde o queda desconectado del "cómo" (código).
- **Coste centralizado**: la indexación se ejecuta en servidores costosos, escalando linealmente con el tamaño del repositorio.

KDD define una estructura de especificaciones rica, tipada y con relaciones explícitas. **KDD Engine** es el motor de indexación y retrieval diseñado específicamente para explotar esta estructura, ofreciendo a los agentes un retrieval de alta precisión donde las specs son ciudadanos de primera clase.

## Usuarios y Jobs-to-be-done

### Consumidores primarios: Agentes de IA
- **Job**: Obtener el contexto completo (specs + código + relaciones) para ejecutar tareas de desarrollo.
- **Dolor actual**: Retrieval genérico devuelve chunks irrelevantes; el agente "adivina" relaciones.

### Consumidores secundarios: Desarrolladores humanos
- **Job**: Explorar el grafo de conocimiento del proyecto, entender impacto de cambios.
- **Dolor actual**: Navegar manualmente entre specs, buscar relaciones a mano.

### Productores: Desarrolladores (humanos y agentes)
- **Job**: Mantener el índice actualizado sin esfuerzo adicional, aprovechando recursos locales.
- **Dolor actual**: No existe un pipeline de indexación integrado con el workflow de specs.

## Alcance

### En alcance (v1)
- Indexación de todos los `kinds` KDD: entity, event, business-rule, business-policy, cross-policy, command, query, process, use-case, ui-view, ui-component, requirement, objective, prd, adr.
- Soporte para estructura single-domain y multi-domain (con `[[domain::Entity]]`).
- Grafo de conocimiento tipado con nodos y relaciones extraídas deterministamente del front-matter, wiki-links `[[...]]` y estructura de cada kind.
- Búsqueda semántica sobre secciones clave de specs (embeddings).
- Búsqueda por grafo (traversal, impacto, dependencias).
- Búsqueda híbrida (semántica + grafo + lexical).
- Respeto de dependencias entre capas (04→03→02→01) en el retrieval.
- Pipeline de indexación local triggered por git hooks.
- Generación de artefactos de índice versionables en `.kdd-index/`.
- Merge de índices en servidor compartido.
- API de retrieval consumible por agentes.

### No alcance (v1)
- Indexación de código fuente (el code graph es futuro v2; v1 se centra en specs).
- UI de exploración del grafo (futuro; v1 es API-first).
- Soporte para specs fuera del estándar KDD.
- Re-ranking con LLM en servidor (v1 usa re-ranking determinista + embeddings).

## Arquitectura conceptual

```
┌──────────────────────────────────────────────────────────────┐
│                    DEVELOPER LOCAL                            │
│                                                              │
│  KDD Specs (/specs)                                          │
│  00-requirements/ 01-domain/ 02-behavior/                    │
│  03-experience/ 04-verification/ 05-architecture/            │
│       │                                                      │
│       │ git hook (pre-commit / post-commit)                  │
│       ▼                                                      │
│  ┌──────────────────────────────────────────────┐            │
│  │           Local Index Pipeline                │            │
│  │                                               │            │
│  │  ┌─────────────┐  ┌──────────────┐           │            │
│  │  │ Deterministic│  │ Semantic     │           │            │
│  │  │ Extractors   │  │ Embedder     │           │            │
│  │  │ (per kind)   │  │ (local model)│           │            │
│  │  └──────┬───────┘  └──────┬───────┘           │            │
│  │         │                 │                    │            │
│  │         ▼                 ▼                    │            │
│  │  ┌─────────────────────────────┐              │            │
│  │  │  Optional: Agent Enricher   │              │            │
│  │  │  (Claude/Codex del dev)     │              │            │
│  │  └──────────┬──────────────────┘              │            │
│  │             ▼                                  │            │
│  │  .kdd-index/                                  │            │
│  │    manifest.json                              │            │
│  │    nodes/                                     │            │
│  │    edges/                                     │            │
│  │    embeddings/                                │            │
│  │    enrichments/ (optional)                    │            │
│  └──────────────────────────────────────────────┘            │
│       │                                                      │
│       │ git push                                             │
└───────┼──────────────────────────────────────────────────────┘
        ▼
┌──────────────────────────────────────────────────────────────┐
│                    SHARED SERVER                              │
│                                                              │
│  ┌──────────────────────────────────────────────┐            │
│  │           Index Merge Engine                  │            │
│  │                                               │            │
│  │  Dev A .kdd-index/ ──┐                        │            │
│  │  Dev B .kdd-index/ ──┼──► Merged Graph + Index│            │
│  │  Dev C .kdd-index/ ──┘                        │            │
│  └──────────────────┬───────────────────────────┘            │
│                     ▼                                        │
│  ┌──────────────────────────────────────────────┐            │
│  │           Retrieval API                       │            │
│  │                                               │            │
│  │  /retrieve/search    (semántico)              │            │
│  │  /retrieve/graph     (traversal)              │            │
│  │  /retrieve/context   (híbrido)                │            │
│  │  /retrieve/impact    (análisis de impacto)    │            │
│  │  /retrieve/coverage  (gobernanza)             │            │
│  └──────────────────────────────────────────────┘            │
│                     │                                        │
│                     ▼                                        │
│            Agentes (Codex, Claude Code, etc.)                │
└──────────────────────────────────────────────────────────────┘
```

## Modelo de dominio

### Nodos del grafo (por kind KDD)

| Kind | ID Pattern | Location | Campos indexados | Embedding |
|------|-----------|----------|------------------|-----------|
| `entity` | PascalCase (filename) | `01-domain/entities/` | description, attributes, relations, invariants, state_machine | Sí (description) |
| `event` | `EVT-{Entity}-{Action}` | `01-domain/events/` | title, payload, producer, consumers | No |
| `business-rule` | `BR-{ENTITY}-NNN` | `01-domain/rules/` | declaration, when_applies, violation, examples, formalization | Sí (declaration, when_applies) |
| `business-policy` | `BP-{TOPIC}-NNN` | `02-behavior/policies/` | declaration, when_applies, parameters, violation | Sí (declaration) |
| `cross-policy` | `XP-{TOPIC}-NNN` | `02-behavior/policies/` | purpose, declaration, formalization_ears, standard_behavior | Sí (purpose, declaration) |
| `command` | `CMD-NNN` | `02-behavior/commands/` | purpose, input_params, preconditions, postconditions, errors | Sí (purpose) |
| `query` | `QRY-NNN` | `02-behavior/queries/` | purpose, input_params, output_structure, errors | Sí (purpose) |
| `process` | `PROC-NNN` | `02-behavior/processes/` | mermaid_flow, participants, steps | Sí (participants, steps) |
| `use-case` | `UC-NNN` | `02-behavior/use-cases/` | description, actors, preconditions, main_flow, alternatives, exceptions, postconditions | Sí (description, main_flow) |
| `ui-view` | `UI-{Name}` | `03-experience/views/` | description, layout, components, states, behavior | Sí (description, behavior) |
| `ui-component` | `UI-{Name}` | `03-experience/views/` | description, entities, use_cases | Sí (description) |
| `requirement` | `REQ-NNN` | `04-verification/criteria/` | description, acceptance_criteria, traceability | Sí (description) |
| `objective` | `OBJ-NNN` | `00-requirements/objectives/` | actor, objective, success_criteria | Sí (objective) |
| `prd` | libre | `00-requirements/` | problem, scope, metrics, dependencies | Sí (problem) |
| `adr` | `ADR-NNNN` | `00-requirements/decisions/` | context, decision, consequences | Sí (context, decision) |

### Relaciones del grafo (tipos de edges)

> **Convención**: MAYÚSCULAS (`SCREAMING_SNAKE_CASE`) = relaciones estructurales extraídas automáticamente por el motor. minúsculas (`snake_case`) = relaciones de negocio definidas por el autor en el contenido (e.g. `aprueba`, `revisa`).

| Relación | Origen | Destino | Extracción |
|----------|--------|---------|------------|
| `WIKI_LINK` | Any | Any | `[[Target]]` en contenido (genérica, bidireccional) |
| `DOMAIN_RELATION` | Entity | Entity | Tabla `## Relaciones` + wiki-links en tipos de atributos |
| `ENTITY_RULE` | BR | Entity | Wiki-link a entidad en `## Declaración` de un BR |
| `ENTITY_POLICY` | BP | Entity | Wiki-link a entidad en `## Declaración` de un BP |
| `EMITS` | Entity/Command | Event | Wiki-links a `EVT-*` en secciones de postcondiciones o eventos |
| `CONSUMES` | Entity/Process | Event | Wiki-links a `EVT-*` en secciones de eventos consumidos |
| `UC_APPLIES_RULE` | UC | BR/BP/XP | Wiki-links en sección `## Reglas Aplicadas` |
| `UC_EXECUTES_CMD` | UC | CMD | Wiki-links en sección `## Comandos Ejecutados` |
| `UC_STORY` | UC | OBJ | Wiki-links a `OBJ-*` en contenido del UC |
| `VIEW_TRIGGERS_UC` | UI-View | UC | Wiki-links a `UC-*` en contenido de una vista |
| `VIEW_USES_COMPONENT` | UI-View | UI-Component | Wiki-links a componentes en contenido de una vista |
| `COMPONENT_USES_ENTITY` | UI-Component | Entity | Wiki-links a entidades en contenido de un componente |
| `REQ_TRACES_TO` | REQ | UC/BR/CMD | Wiki-links en sección `## Trazabilidad` |
| `VALIDATES` | BDD Feature | UC/BR/CMD | Tags o wiki-links en scenarios |
| `DECIDES_FOR` | ADR | Any | Wiki-links en contenido de un ADR |
| `CROSS_DOMAIN_REF` | Any | Any | Syntax `[[domain::Entity]]` en contenido |
| `LAYER_DEPENDENCY` | Node(layer N) | Node(layer M) | Implícita: N > M según 04→03→02→01 |

### Regla de capas en el grafo

Las dependencias entre capas se reflejan en el grafo y se pueden usar para validación:
- `04-verification` → puede referenciar `03`, `02`, `01`
- `03-experience` → puede referenciar `02`, `01`
- `02-behavior` → puede referenciar `01`
- `01-domain` → NO referencia capas superiores
- `00-requirements` → fuera del flujo, puede mencionar cualquier capa

Un edge que viole esta regla se marca como `layer_violation: true` en el grafo.

## Requisitos funcionales enlazados

### Indexación
- **[[UC-001-IndexDocument]]**: Indexar un documento KDD individual (parse → extract → embed → store).
- **[[UC-002-IndexIncremental]]**: Detectar cambios via git y re-indexar solo lo modificado.
- **[[UC-003-EnrichWithAgent]]**: Usar el agente del dev para enriquecimiento profundo (opcional).

### Retrieval
- **[[UC-004-RetrieveContext]]**: Búsqueda híbrida (grafo + semántica + lexical) con fusion scoring — el UC principal para agentes.
- **[[UC-005-RetrieveImpact]]**: Dado un nodo, devolver todo lo que se ve afectado.

> Las estrategias individuales de retrieval (grafo, semántica, cobertura, violaciones de capa) se modelan como queries: [[QRY-001-RetrieveByGraph]], [[QRY-002-RetrieveSemantic]], [[QRY-005-RetrieveCoverage]], [[QRY-006-RetrieveLayerViolations]].

### Distribución
- **[[UC-006-MergeIndex]]**: Merge de índices de múltiples desarrolladores en servidor.
- **[[UC-007-SyncIndex]]**: Push/pull de artefactos de índice via git.

### Reglas
- **[[BR-DOCUMENT-001]]**: Dado un fichero, determinar su `kind` y aplicar el extractor correcto (Kind Router).
- **[[BR-EMBEDDING-001]]**: Qué secciones de cada `kind` reciben embedding y cuáles no (Embedding Strategy).
- **[[BR-INDEX-001]]**: Determinar qué nivel de indexación (L1/L2/L3) se ejecuta según recursos disponibles.
- **[[BR-MERGE-001]]**: Cómo resolver conflictos cuando dos devs modifican specs relacionadas.
- **[[BR-LAYER-001]]**: Validar que las referencias entre nodos respetan las dependencias de capa KDD.

## NFRs y compliance

- **[[REQ-001-Performance]]**: Indexación incremental <2s/doc local. Retrieval P95 <300ms.
- **[[REQ-002-Storage]]**: Artefactos de índice <10% del tamaño de las specs originales.
- **[[REQ-003-Privacy]]**: Modo offline-first; las specs nunca salen de la máquina si el dev no hace push.
- **[[REQ-004-Portability]]**: Embeddings generados con modelos abiertos; no vendor lock-in.

## Métricas de éxito y telemetría

| Métrica | SLI | SLO |
|---------|-----|-----|
| Precision de retrieval | `retrieval_precision{strategy}` | ≥90% en queries de agentes |
| Indexación incremental | `index_duration_seconds{scope="incremental"}` | P95 <2s |
| Retrieval latency | `retrieval_duration_seconds{quantile="0.95"}` | <300ms |
| Index freshness | `index_staleness_seconds` | <60s tras push |
| Distribución de cómputo | `index_compute_ratio{location="local"}` | ≥80% |

## Dependencias

- Modelo de embeddings local: `nomic-embed-text` o `bge-small-en-v1.5` (portables, open-source).
- Git hooks: `husky` / `lefthook` / custom script.
- Graph storage (servidor): Neo4j / SQLite con extensión de grafos / en memoria.
- Vector storage (servidor): `hnswlib` / `usearch` / embebido en el graph store.
- Agente enricher: API de Claude / Codex (opcional, usa licencia del dev).
- Validador KDD: `bun run validate:specs` (ya existente en el ecosistema KDD).

## Criterios de aceptación / Go-Live

- [ ] Todos los `kinds` KDD definidos tienen extractor e indexador funcional.
- [ ] SCN-IndexEntity-001: Indexar una entidad con ciclo de vida produce nodo + edges correctos.
- [ ] SCN-RetrieveImpact-001: Query de impacto sobre Entity:Pedido devuelve BR, CMD, EVT y UC conectados.
- [ ] SCN-MergeIndex-001: Merge de índices de 2 devs produce grafo unificado sin duplicados.
- [ ] SCN-HybridSearch-001: Query semántica "flujo de devolución" + expansión por grafo devuelve UC + BR + CMD relevantes.
- [ ] SCN-IncrementalIndex-001: Modificar una spec y hacer commit re-indexa solo esa spec en <2s.
- [ ] SCN-OfflineFirst-001: Indexación local funciona sin conexión a servidor.
- [ ] SCN-LayerValidation-001: Detectar y marcar referencias que violan dependencias de capa.
- [ ] SCN-MultiDomain-001: Indexar specs con `[[domain::Entity]]` produce edges cross-domain correctos.

---

## Apéndice A: Formato de artefactos de índice (.kdd-index/)

```
.kdd-index/
├── manifest.json              # Metadata del índice (versión, modelo embeddings, timestamp)
├── nodes/
│   ├── entity/
│   │   └── Pedido.json        # Nodo completo con campos indexados
│   ├── command/
│   │   └── CMD-001.json
│   ├── business-rule/
│   │   └── BR-PEDIDO-001.json
│   └── .../
├── edges/
│   └── edges.jsonl            # Lista de edges: {from, to, type, metadata}
├── embeddings/
│   ├── entity/
│   │   └── Pedido.bin         # Vector(s) binario(s)
│   └── .../
└── enrichments/               # Solo si se usó agent enricher
    └── Pedido.enrichment.json # Resumen, relaciones implícitas, impacto
```

### manifest.json (ejemplo)

```json
{
  "version": "1.0.0",
  "kdd_version": "1.0",
  "embedding_model": "nomic-embed-text-v1.5",
  "embedding_dimensions": 768,
  "indexed_at": "2026-02-15T10:30:00Z",
  "indexed_by": "dev-alice",
  "structure": "single-domain",
  "stats": {
    "nodes": 47,
    "edges": 132,
    "embeddings": 31,
    "enrichments": 12
  }
}
```

### Ejemplo de nodo (Entity)

```json
{
  "id": "Entity:Pedido",
  "kind": "entity",
  "source_file": "specs/01-domain/entities/Pedido.md",
  "source_hash": "a3f2b1c...",
  "status": "approved",
  "aliases": ["Orden", "Order"],
  "layer": "01-domain",
  "indexed_fields": {
    "description": "Representa un pedido de compra realizado por un Usuario...",
    "attributes": [
      {"name": "id", "type": "uuid"},
      {"name": "estado", "type": "enum", "values": ["borrador", "confirmado", "enviado", "entregado", "cancelado"]},
      {"name": "total", "type": "Money"},
      {"name": "creador", "type": "[[Usuario]]"}
    ],
    "relations": [
      {"relation": "pertenece a", "cardinality": "N:1", "target": "Entity:Usuario"},
      {"relation": "contiene", "cardinality": "1:N", "target": "Entity:LineaPedido"}
    ],
    "state_machine": {
      "states": ["borrador", "confirmado", "enviado", "entregado", "cancelado"],
      "transitions": [
        {"from": "borrador", "to": "confirmado", "event": "EVT-Pedido-Confirmado", "guard": "total > 0"},
        {"from": "confirmado", "to": "enviado", "event": "EVT-Pedido-Enviado"},
        {"from": "confirmado", "to": "cancelado", "event": "EVT-Pedido-Cancelado"},
        {"from": "enviado", "to": "entregado", "event": "EVT-Pedido-Entregado"}
      ]
    },
    "invariants": [
      "El total siempre es la suma de sus líneas",
      "No se puede cancelar un pedido ya entregado"
    ],
    "emits": ["EVT-Pedido-Creado", "EVT-Pedido-Confirmado", "EVT-Pedido-Cancelado"],
    "consumes": ["EVT-Pago-Completado"]
  }
}
```

## Apéndice B: Pipeline de indexación por niveles

| Nivel | Requiere | Produce | Coste |
|-------|----------|---------|-------|
| **L1: Determinista** | Solo parser | Nodos, edges, metadata | Cero (CPU local) |
| **L2: Semántico** | Modelo embeddings local | Vectores por sección | Bajo (modelo ~500MB, GPU opcional) |
| **L3: Enriquecido** | Agente (Claude/Codex) | Resúmenes, relaciones implícitas, impacto | Variable (usa licencia del dev) |

El sistema es funcional con solo L1. L2 y L3 son mejoras progresivas.

## Apéndice C: API de Retrieval (borrador)

```yaml
# Búsqueda semántica
POST /v1/retrieve/search
{
  "query": "flujo de devolución de dinero",
  "kinds": ["use-case", "process", "business-rule"],
  "layers": ["01-domain", "02-behavior"],
  "limit": 10,
  "min_score": 0.7
}
# → [{node, score, snippet}]

# Traversal de grafo
GET /v1/retrieve/graph?node=Entity:Pedido&depth=2&edge_types=emits,entity_rule
# → {center_node, related_nodes[], edges[]}

# Búsqueda híbrida (lo que usarán los agentes principalmente)
POST /v1/retrieve/context
{
  "query": "implementar cancelación de pedido",
  "strategy": "hybrid",
  "expand_graph": true,
  "depth": 2,
  "include_kinds": ["use-case", "business-rule", "event", "command", "entity"],
  "respect_layers": true,
  "max_tokens": 8000
}
# → {results[], graph_expansion[], total_tokens}

# Análisis de impacto
GET /v1/retrieve/impact?node=Entity:Pedido&change_type=modify_attribute
# → {directly_affected[], transitively_affected[], scenarios_to_rerun[]}

# Cobertura
GET /v1/retrieve/coverage?node=UC-001-CrearPedido
# → {required, present, missing[], coverage_percent}

# Validación de capas
GET /v1/retrieve/layer-violations
# → [{from_node, to_node, from_layer, to_layer, edge_type}]
```
