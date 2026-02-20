---
id: BR-LAYER-001
kind: business-rule
title: Layer Validation
category: validation
severity: medium
status: draft
---

# BR-LAYER-001 — Layer Validation

## Declaración

Las referencias entre [[GraphNode|nodos]] del grafo deben respetar las dependencias de capa KDD. Las capas superiores pueden referenciar capas inferiores, pero no al revés. El sistema valida cada [[GraphEdge]] generado y marca las violaciones sin rechazar la indexación.

### Jerarquía de capas (de arriba a abajo)

```
04-verification  → puede referenciar 03, 02, 01
03-experience    → puede referenciar 02, 01
02-behavior      → puede referenciar 01
01-domain        → NO referencia capas superiores
00-requirements  → fuera del flujo, puede referenciar cualquier capa
```

### Reglas de validación

1. Para cada [[GraphEdge]] generado, se comparan las capas de los nodos origen y destino.
2. Si el nodo origen está en una capa **inferior** al nodo destino (e.g. `01-domain → 02-behavior`), el edge se marca con `layer_violation: true`.
3. Los edges desde `00-requirements` hacia cualquier capa **nunca** son violación (está fuera del flujo).
4. Los edges de tipo `wiki_link` bidireccionales se validan en ambas direcciones: la dirección que viola la regla se marca.
5. Las violaciones **no bloquean** la indexación. El nodo y el edge se crean normalmente, pero quedan marcados para ser reportados por [[QRY-006-RetrieveLayerViolations]].

### Asignación de capa

La capa de un nodo se determina por la ubicación de su [[KDDDocument]] fuente:

| Prefijo de ruta | Capa | Valor numérico |
|----------------|------|----------------|
| `00-requirements/` | `00-requirements` | 0 |
| `01-domain/` | `01-domain` | 1 |
| `02-behavior/` | `02-behavior` | 2 |
| `03-experience/` | `03-experience` | 3 |
| `04-verification/` | `04-verification` | 4 |

Un edge viola la regla cuando `origin.layer_value > 0` y `origin.layer_value < destination.layer_value`.

## Por qué existe

La arquitectura KDD establece que las capas inferiores son los cimientos del sistema. Si una entidad de dominio (`01`) referencia un caso de uso (`02`), se crea una dependencia circular que dificulta el razonamiento sobre el sistema y degrada la calidad de las specs.

## Cuándo aplica

Durante la generación de [[GraphEdge|edges]] en el pipeline de indexación, para cada edge extraído de wiki-links o secciones del [[KDDDocument]].

## Qué pasa si se incumple

- Si las violaciones no se marcan, los agentes de retrieval pueden seguir edges que representan dependencias incorrectas, degradando la calidad del contexto recuperado.
- Si las violaciones bloquean la indexación (demasiado estricto), los autores de specs no pueden indexar trabajo en progreso que aún tiene referencias incorrectas.

## Ejemplos

**Referencia válida (capa superior → inferior):**
```
Edge: UC:UC-001 (02-behavior) → Entity:KDDDocument (01-domain)
→ layer_violation: false (02 → 01 es descendente, válido)
```

**Referencia inválida (capa inferior → superior):**
```
Edge: Entity:KDDDocument (01-domain) → UC:UC-001 (02-behavior)
→ layer_violation: true (01 → 02 es ascendente, violación)
→ El edge se crea pero queda marcado
```

**Referencia desde requirements (siempre válida):**
```
Edge: PRD:PRD-KDDEngine (00-requirements) → UC:UC-001 (02-behavior)
→ layer_violation: false (00-requirements está fuera del flujo)
```

**Referencia entre misma capa (válida):**
```
Edge: Entity:KDDDocument (01-domain) → Entity:GraphNode (01-domain)
→ layer_violation: false (misma capa, no hay ascendencia)
```
