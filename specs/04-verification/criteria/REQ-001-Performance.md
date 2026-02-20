---
id: REQ-001
kind: requirement
title: Performance
status: draft
priority: high
source: PRD
---

# REQ-001 — Performance

## Descripción

El KDD Engine debe cumplir los SLOs de rendimiento definidos en el PRD para garantizar que la indexación no interrumpe el flujo de trabajo del desarrollador y que el retrieval es suficientemente rápido para que los agentes de IA lo usen en tiempo real.

## Criterios de Aceptación

- **CA-1**: La indexación incremental ([[CMD-002-IndexIncremental]]) de un [[KDDDocument]] individual completa en menos de 2 segundos (P95) en una máquina de desarrollo estándar.
- **CA-2**: La búsqueda híbrida ([[QRY-003-RetrieveHybrid]]) responde en menos de 300ms (P95) sobre un índice de hasta 500 documentos.
- **CA-3**: El análisis de impacto ([[QRY-004-RetrieveImpact]]) con profundidad 3 responde en menos de 500ms (P95).
- **CA-4**: El merge de 3 índices ([[CMD-004-MergeIndex]]) de hasta 200 nodos cada uno completa en menos de 5 segundos.
- **CA-5**: El freshness del índice tras un push al servidor es menor a 60 segundos (tiempo entre push y disponibilidad en API de retrieval).

## Trazabilidad

- [[UC-001-IndexDocument]] — Flujo de indexación individual (CA-1).
- [[UC-002-IndexIncremental]] — Flujo de indexación incremental (CA-1).
- [[UC-004-RetrieveContext]] — Flujo de búsqueda híbrida (CA-2).
- [[UC-005-RetrieveImpact]] — Flujo de análisis de impacto (CA-3).
- [[UC-006-MergeIndex]] — Flujo de merge (CA-4).
- [[UC-007-SyncIndex]] — Flujo de sync (CA-5).
