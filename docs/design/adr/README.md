# Architecture Decision Records (ADRs)

> **Propósito**: Documentar decisiones arquitectónicas significativas junto con su contexto, alternativas consideradas y consecuencias.

## Índice de ADRs

| ID | Título | Estado | Fecha | DC Relacionado |
|----|--------|--------|-------|----------------|
| [ADR-0001](./ADR-0001-repository-pattern-for-storage-abstraction.md) | Repository Pattern para Abstracción de Almacenamiento | `superseded` | 2025-01-16 | DC-010 |
| [ADR-0002](./ADR-0002-kdd-semantic-chunking-strategy.md) | Estrategia de Chunking Semántico por Tipo KDD | `superseded` | 2025-01-16 | DC-004 |
| [ADR-0003](./ADR-0003-entity-extraction-pipeline.md) | Pipeline de Extracción de Entidades Multi-estrategia | `superseded` | 2025-01-16 | DC-003 |
| [ADR-0004](./ADR-0004-mcp-server-agent-integration.md) | MCP Server para Integración con Agentes de IA | `superseded` | 2025-02-07 | DC-012 |

> **Nota**: Los ADRs 0001-0004 fueron superseded por la migración a TypeScript/Bun (Feb 2026).
> La arquitectura actual está documentada en [docs/architecture/kdd-engine.md](../../architecture/kdd-engine.md).

## Estados

| Estado | Descripción |
|--------|-------------|
| `proposed` | Decisión propuesta, pendiente de aprobación |
| `accepted` | Decisión aceptada e implementada |
| `deprecated` | Decisión ya no es relevante |
| `superseded` | Decisión reemplazada por otra (ver `superseded_by`) |

## Convenciones

### Nomenclatura

```
ADR-NNNN-titulo-en-minusculas.md
```

- `NNNN`: Número secuencial de 4 dígitos (0001, 0002, ...)
- `titulo`: Descripción corta en minúsculas con guiones

### Ejemplos

- `ADR-0001-repository-pattern-for-storage-abstraction.md`
- `ADR-0002-kdd-semantic-chunking-strategy.md`
- `ADR-0003-entity-extraction-pipeline.md`

## Proceso

1. **Crear DC** → Explorar el problema en un Design Challenge
2. **Analizar opciones** → Documentar alternativas en el DC
3. **Decidir** → Seleccionar opción y crear ADR
4. **Implementar** → Seguir el plan del ADR
5. **Mantener** → Actualizar estado si la decisión cambia

## Relación con Design Challenges

```
Design Challenge (DC)          ADR
┌─────────────────────┐       ┌─────────────────────┐
│ Explora el problema │──────▶│ Documenta la        │
│ y las alternativas  │       │ decisión final      │
└─────────────────────┘       └─────────────────────┘
```

Un DC puede generar:
- **0 ADRs** → Si se pospone (deferred)
- **1 ADR** → Decisión única
- **N ADRs** → Múltiples sub-decisiones
