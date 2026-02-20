---
id: UC-004
kind: use-case
title: RetrieveContext
version: 1
status: draft
actor: AIAgent
---

# UC-004 — RetrieveContext

## Descripción

Un agente de IA (Codex, Claude Code, Cursor, etc.) solicita contexto al motor de retrieval para ejecutar una tarea de desarrollo. El sistema ejecuta una búsqueda híbrida que combina semántica, grafo y lexical, devolviendo un [[RetrievalResult]] con los [[GraphNode|nodos]] más relevantes, el subgrafo de relaciones y un control de tokens para caber en la context window del agente.

Este es el **caso de uso principal** del KDD Engine — el punto de entrada que los agentes usan para obtener el contexto preciso que necesitan.

## Actores

- **AIAgent**: Agente de IA que necesita contexto de specs KDD para ejecutar una tarea.
- **Developer**: Puede invocar la búsqueda manualmente (`kb search "..."`) para exploración.

## Precondiciones

- Existe un índice cargado (local o mergeado desde servidor).
- Si el índice es L1 (sin embeddings), la búsqueda degrada a grafo + lexical.

## Flujo Principal

1. El agente envía una [[RetrievalQuery]] al API con `strategy: hybrid` y un `query_text` en lenguaje natural. Se emite [[EVT-RetrievalQuery-Received]].
2. El sistema valida los parámetros de la query (texto no vacío, límites en rango).
3. **Fase semántica**: el sistema ejecuta [[QRY-002-RetrieveSemantic]] con el `query_text`, obteniendo los [[Embedding|embeddings]] más similares y sus `document_id` asociados.
4. **Fase lexical**: el sistema ejecuta una búsqueda por texto exacto sobre los `indexed_fields` de los [[GraphNode|nodos]], obteniendo matches por keywords.
5. **Fase de grafo**: si `expand_graph` es `true`, para cada `document_id` encontrado en las fases anteriores, el sistema localiza el [[GraphNode]] correspondiente y ejecuta [[QRY-001-RetrieveByGraph]] con la profundidad configurada, obteniendo nodos y edges vecinos.
6. **Fusion scoring**: el sistema combina los resultados de las tres fases:
   - Nodos encontrados por semántica + grafo reciben el score más alto.
   - Nodos encontrados solo por semántica reciben score medio-alto.
   - Nodos encontrados solo por grafo (expansión) reciben score medio.
   - Nodos encontrados solo por lexical reciben score bajo.
7. El sistema ordena los resultados por score descendente y aplica `min_score` y `limit`.
8. El sistema estima los tokens del resultado y trunca si excede `max_tokens`.
9. El sistema construye el [[RetrievalResult]] con nodos, scores, snippets y subgrafo de edges.
10. Se emite [[EVT-RetrievalQuery-Completed]] con métricas de latencia.
11. El sistema devuelve el resultado al agente.

## Flujos Alternativos

### FA-1: Índice L1 (sin embeddings)
- En el paso 3, si el índice es L1, la fase semántica se omite. El sistema continúa con lexical + grafo. Se incluye un warning `NO_EMBEDDINGS` en la respuesta.

### FA-2: Sin expansión de grafo
- Si `expand_graph` es `false`, el paso 5 se omite. Solo se devuelven los nodos encontrados por semántica y lexical, sin subgrafo.

### FA-3: Violaciones de capa
- Si `respect_layers` es `true`, los edges marcados con `layer_violation` ([[BR-LAYER-001]]) se excluyen del traversal en el paso 5. Los nodos solo alcanzables por edges con violación no aparecen en resultados.

## Excepciones

### EX-1: Query inválida
- En el paso 2, si el `query_text` es vacío o menor a 3 caracteres, se emite [[EVT-RetrievalQuery-Failed]] con `QUERY_TOO_SHORT`.

### EX-2: Índice no disponible
- En el paso 3, si no hay índice cargado, se emite [[EVT-RetrievalQuery-Failed]] con `INDEX_UNAVAILABLE`.

### EX-3: Timeout
- Si la resolución excede el timeout configurado, se devuelven los resultados parciales obtenidos hasta ese momento con un warning `TIMEOUT`.

## Postcondiciones

- Un [[RetrievalResult]] ha sido generado y devuelto al agente.
- La [[RetrievalQuery]] está en estado `completed` con `duration_ms` registrado.
- El `duration_ms` cumple el SLO de P95 < 300ms ([[REQ-001-Performance]]).

## Reglas Aplicadas

- [[BR-EMBEDDING-001]] — Embedding Strategy: determina qué secciones fueron embebidas (afecta resultados semánticos).
- [[BR-LAYER-001]] — Layer Validation: filtra edges con violaciones de capa si `respect_layers` está activo.

## Comandos Ejecutados

- [[QRY-003-RetrieveHybrid]] — Query principal que implementa la búsqueda híbrida.
- [[QRY-002-RetrieveSemantic]] — Subquery de fase semántica.
- [[QRY-001-RetrieveByGraph]] — Subquery de expansión por grafo.
