---
id: REQ-003
kind: requirement
title: Privacy
status: draft
priority: high
source: PRD
---

# REQ-003 — Privacy

## Descripción

El KDD Engine opera en modo offline-first. Las specs del desarrollador nunca salen de su máquina local a menos que el desarrollador ejecute un push explícito. Incluso durante el push, solo se transmiten los artefactos derivados (nodos, edges, embeddings), nunca el contenido original de las specs.

## Criterios de Aceptación

- **CA-1**: La indexación local ([[UC-001-IndexDocument]], [[UC-002-IndexIncremental]]) funciona completamente sin conexión a internet ni al servidor compartido.
- **CA-2**: El nivel L1 y L2 de indexación ([[BR-INDEX-001]]) no requiere llamadas a servicios externos.
- **CA-3**: El push ([[CMD-005-SyncIndex]]) transmite únicamente artefactos derivados: [[IndexManifest]], [[GraphNode|nodos]], [[GraphEdge|edges]], [[Embedding|embeddings]]. Nunca el contenido Markdown/YAML original de los [[KDDDocument|documentos]].
- **CA-4**: El nivel L3 (enriquecimiento con agente, [[UC-003-EnrichWithAgent]]) usa la API key del propio desarrollador. El sistema no almacena ni reenvía API keys.
- **CA-5**: No se envía telemetría ni métricas a servicios externos sin consentimiento explícito del desarrollador.

## Trazabilidad

- [[UC-001-IndexDocument]] — Indexación local offline (CA-1, CA-2).
- [[UC-003-EnrichWithAgent]] — Uso de API key del dev (CA-4).
- [[UC-007-SyncIndex]] — Push de artefactos derivados (CA-3).
- [[BR-INDEX-001]] — Niveles de indexación y recursos requeridos (CA-2).
