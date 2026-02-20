---
id: REQ-004
kind: requirement
title: Portability
status: draft
priority: medium
source: PRD
---

# REQ-004 — Portability

## Descripción

El KDD Engine no debe crear dependencia de un proveedor específico de embeddings ni de infraestructura. Los modelos de embeddings deben ser open-source y portables, y el formato de los artefactos de índice debe ser abierto y documentado.

## Criterios de Aceptación

- **CA-1**: Los [[Embedding|embeddings]] se generan con modelos open-source portables (`nomic-embed-text`, `bge-small-en-v1.5` o equivalentes). No se requiere API de un proveedor específico para nivel L2.
- **CA-2**: El [[IndexManifest]] registra el `embedding_model` usado, permitiendo verificar compatibilidad entre índices ([[BR-MERGE-001]]).
- **CA-3**: El formato de `.kdd-index/` (JSON, JSONL, binario para vectores) está documentado y puede ser consumido por herramientas externas sin depender del KDD Engine.
- **CA-4**: El cambio de modelo de embeddings requiere re-indexación completa pero no cambios en el código del motor.
- **CA-5**: El graph storage puede funcionar con múltiples backends (SQLite, Neo4j, en memoria) sin cambios en la lógica de indexación o retrieval.

## Trazabilidad

- [[BR-INDEX-001]] — Niveles de indexación y modelos requeridos (CA-1).
- [[BR-MERGE-001]] — Validación de compatibilidad de modelos entre índices (CA-2).
- [[BR-EMBEDDING-001]] — Estrategia de embedding independiente de modelo (CA-1, CA-4).
- [[UC-006-MergeIndex]] — Merge requiere modelos compatibles (CA-2).
