---
id: BR-INDEX-001
kind: business-rule
title: Index Level
category: state
severity: medium
status: draft
---

# BR-INDEX-001 — Index Level

## Declaración

El pipeline de indexación de un [[KDDDocument]] se ejecuta en uno de tres niveles progresivos, determinado por los recursos disponibles en la máquina local. Cada nivel produce artefactos adicionales sobre el anterior, registrados en el [[IndexManifest]].

### Tabla de decisión

| Nivel | Condición de activación | Produce | Requiere |
|-------|------------------------|---------|----------|
| **L1: Determinista** | Siempre disponible | [[GraphNode]], [[GraphEdge|edges]], metadata | Solo CPU (parser Markdown + YAML) |
| **L2: Semántico** | Modelo de embeddings disponible localmente | Todo de L1 + [[Embedding|embeddings]] | Modelo local (~500MB). GPU opcional, funciona en CPU |
| **L3: Enriquecido** | Agente IA configurado (API key válida) | Todo de L2 + enrichments (resúmenes, relaciones implícitas, análisis de impacto) | API de Claude/Codex (usa licencia del dev) |

### Reglas de selección

1. El nivel se determina al inicio del pipeline, antes de procesar cualquier documento.
2. El sistema intenta el nivel más alto posible según los recursos detectados.
3. Si un nivel superior falla en tiempo de ejecución (e.g. modelo de embeddings no carga, API del agente no responde), el sistema degrada al nivel inferior sin abortar la indexación.
4. El nivel ejecutado se registra en el campo `index_level` del [[IndexManifest]].
5. Un índice L1 es **completamente funcional** para búsqueda por grafo y lexical. L2 y L3 son mejoras progresivas que habilitan búsqueda semántica y enriquecimiento.

## Por qué existe

El diseño distribuido de KDD Engine requiere que la indexación funcione en cualquier máquina de desarrollo, desde laptops sin GPU hasta estaciones con acceso a APIs de IA. La degradación graceful asegura que el sistema siempre produce un índice útil.

## Cuándo aplica

Al inicio de cada ejecución del pipeline de indexación, tanto en modo completo ([[CMD-001-IndexDocument]]) como incremental ([[CMD-002-IndexIncremental]]).

## Qué pasa si se incumple

- Si el sistema no detecta correctamente los recursos disponibles, puede intentar generar embeddings sin modelo (error) o no generar embeddings teniendo modelo disponible (pérdida de funcionalidad).
- Si la degradación graceful falla, el pipeline aborta y no produce índice — el peor escenario posible.

## Ejemplos

**Laptop sin GPU ni API key:**
```
Recursos: CPU only, sin modelo de embeddings, sin API key
→ Nivel: L1 (Determinista)
→ Produce: nodos + edges
→ Búsquedas disponibles: grafo, lexical
→ Búsquedas no disponibles: semántica
```

**Laptop con modelo local descargado:**
```
Recursos: CPU + modelo nomic-embed-text-v1.5 en ~/.cache/models/
→ Nivel: L2 (Semántico)
→ Produce: nodos + edges + embeddings
→ Búsquedas disponibles: grafo, lexical, semántica, híbrida
```

**Estación con modelo + API de Claude:**
```
Recursos: CPU + modelo + ANTHROPIC_API_KEY configurada
→ Nivel: L3 (Enriquecido)
→ Produce: nodos + edges + embeddings + enrichments
→ Búsquedas disponibles: todas + enriquecimiento profundo
```

**Degradación en runtime:**
```
Recursos detectados: L2
Pipeline: procesando Pedido.md...
Error: modelo de embeddings falla al cargar (OOM)
→ Degradación automática: L1
→ Warning: "Embedding model failed to load, falling back to L1"
→ IndexManifest.index_level = "L1"
```
