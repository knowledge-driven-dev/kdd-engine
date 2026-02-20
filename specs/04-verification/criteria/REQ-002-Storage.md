---
id: REQ-002
kind: requirement
title: Storage
status: draft
priority: medium
source: PRD
---

# REQ-002 — Storage

## Descripción

Los artefactos de índice generados por el KDD Engine (`.kdd-index/`) deben ser compactos y proporcionales al tamaño de las specs originales, para que puedan versionarse en Git sin degradar la experiencia del repositorio.

## Criterios de Aceptación

- **CA-1**: El tamaño total de `.kdd-index/` no excede el 10% del tamaño total de las specs en `/specs`.
- **CA-2**: Los [[Embedding|embeddings]] se almacenan en formato binario compacto, no en texto plano.
- **CA-3**: Los [[GraphNode|nodos]] y [[GraphEdge|edges]] se almacenan en formatos serializados eficientes (JSON compacto o JSONL).
- **CA-4**: El [[IndexManifest]] incluye `stats` que permiten verificar los tamaños sin recalcular.

## Trazabilidad

- [[UC-001-IndexDocument]] — Genera los artefactos de índice cuyo tamaño se mide.
- [[CMD-005-SyncIndex]] — Transmite los artefactos (el tamaño afecta el tiempo de sync).
- [[BR-EMBEDDING-001]] — Define qué secciones se embeben (afecta el volumen de embeddings).
