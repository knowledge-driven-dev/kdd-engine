# Design Challenges

> **Propósito**: Documentar los retos de diseño que requieren exploración, análisis de alternativas y decisiones arquitectónicas formales (ADRs).

## Índice de Design Challenges

| ID | Nombre | Estado | Prioridad | ADRs Relacionados |
|----|--------|--------|-----------|-------------------|
| [DC-001](./DC-001-security-model.md) | Modelo de Seguridad | `open` | Alta | - |
| [DC-002](./DC-002-retrieval-strategies.md) | Estrategias de Retrieval | `open` | Alta | - |
| [DC-003](./DC-003-entity-extraction.md) | Extracción de Entidades | `decided` | Media | [ADR-0003](../adr/ADR-0003-entity-extraction-pipeline.md) |
| [DC-004](./DC-004-chunking-strategy.md) | Estrategia de Chunking | `decided` | Media | [ADR-0002](../adr/ADR-0002-kdd-semantic-chunking-strategy.md) |
| [DC-005](./DC-005-idp-integration.md) | Integración IdP | `open` | Alta | - |
| [DC-006](./DC-006-api-design.md) | Diseño de API | `open` | Media | - |
| [DC-007](./DC-007-curation-ui.md) | UI de Curación | `open` | Baja | - |
| [DC-008](./DC-008-db-synchronization.md) | Sincronización de BBDDs | `open` | Alta | - |
| [DC-009](./DC-009-incremental-updates.md) | Actualización Incremental | `open` | Media | - |
| [DC-010](./DC-010-engine-abstraction.md) | Abstracción de Motores | `decided` | Alta | [ADR-0001](../adr/ADR-0001-repository-pattern-for-storage-abstraction.md) |
| [DC-011](./DC-011-content-lifecycle.md) | Ciclo de Vida del Contenido | `open` | Alta | - |
| [DC-012](./DC-012-agent-tool-integration.md) | Integración con Agentes (MCP) | `decided` | Alta | [ADR-0004](../adr/ADR-0004-mcp-server-agent-integration.md) |

> **Nota**: En Feb 2026 se migró de Python a TypeScript/Bun. Los DCs `decided` tienen ADRs ahora marcados como `superseded`.
> La arquitectura actual: [docs/architecture/kdd-engine.md](../../architecture/kdd-engine.md).

## Estados

| Estado | Descripción |
|--------|-------------|
| `open` | Pendiente de análisis |
| `in_progress` | En proceso de exploración |
| `decided` | Decisión tomada, ADR creado |
| `deferred` | Pospuesto para futuras fases |

## Prioridades

| Prioridad | Criterio |
|-----------|----------|
| **Alta** | Bloquea el inicio del desarrollo |
| **Media** | Necesario antes de implementar el componente afectado |
| **Baja** | Puede decidirse durante la implementación |

## Flujo de Trabajo

```
┌─────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────┐
│  open   │───▶│ in_progress │───▶│   decided    │───▶│   ADR   │
└─────────┘    └─────────────┘    └──────────────┘    └─────────┘
                     │
                     ▼
               ┌──────────┐
               │ deferred │
               └──────────┘
```

## Relación con ADRs

Cada Design Challenge puede generar uno o más ADRs:

- **DC resuelve UN problema** → 1 ADR con la decisión final
- **DC tiene SUB-DECISIONES** → Múltiples ADRs relacionados

Los ADRs se almacenan en `/docs/design/adr/` con el formato `ADR-NNNN-titulo.md`.
