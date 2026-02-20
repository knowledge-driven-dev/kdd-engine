# Investigación: Papers de RAG Híbrido (Grafos + Embeddings)

> Análisis de arquitecturas de referencia para el diseño del sistema RAG híbrido.

## Resumen Ejecutivo

| Paper/Framework | Enfoque Principal | Indexación | Retrieval | Fortaleza |
|-----------------|-------------------|------------|-----------|-----------|
| **LightRAG** | Key-value + grafo | LLM extrae entidades/relaciones | Dual-level (local/global) | Actualización incremental |
| **Microsoft GraphRAG** | Comunidades jerárquicas | Leiden + resúmenes | Map-reduce sobre comunidades | Queries globales |
| **HippoRAG** | Memoria humana | Tripletas SPO | Personalized PageRank | Eficiencia + multi-hop |
| **RAPTOR** | Árbol de resúmenes | Clustering recursivo | Multinivel (hojas→raíz) | Contexto jerárquico |
| **HybridRAG** | Vector + Graph paralelo | Dual indexación | Fusión de resultados | Mejor de ambos mundos |

---

## 1. LightRAG

**Paper**: [LightRAG: Simple and Fast Retrieval-Augmented Generation](https://lightrag.github.io/)

### Arquitectura

```
Documento → Segmentación → Extracción R(·) → Grafo de Entidades
                              ↓
                         Pares Key-Value P(·)
                              ↓
                         Deduplicación D(·)
```

### Proceso de Indexación

1. **Extracción de Entidades/Relaciones R(·)**
   - LLM identifica entidades (nodos) y relaciones (edges)
   - Ejemplo: "Cardiologists" ↔ "Heart Disease"

2. **Generación de Pares Key-Value P(·)**
   - Key: palabra o frase corta para retrieval eficiente
   - Value: párrafo que resume snippets relevantes

3. **Deduplicación D(·)**
   - Fusiona entidades idénticas de diferentes segmentos
   - Optimiza operaciones del grafo

### Retrieval Dual-Level

| Nivel | Propósito | Consultas |
|-------|-----------|-----------|
| **Low-Level** | Entidades específicas, atributos, relaciones directas | Detalle, hechos concretos |
| **High-Level** | Temas amplios, conceptos globales | Resúmenes, tendencias |

### Actualización Incremental

- Integra nuevos datos sin reprocesar todo el dataset
- Preserva integridad de conexiones existentes

### Relevancia para nuestro proyecto

- **Aplicable**: Key-value indexing para eficiencia
- **Aplicable**: Dual-level retrieval (detalle KDD vs contexto global)
- **Aplicable**: Actualización incremental (DC-009)

---

## 2. Microsoft GraphRAG

**Paper**: [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130)

**Docs**: [https://microsoft.github.io/graphrag/](https://microsoft.github.io/graphrag/)

### Las 7 Fases de Indexación

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PIPELINE DE INDEXACIÓN                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. TextUnits     2. Extracción    3. Comunidades   4. Resúmenes   │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐    │
│  │ Docs →  │─────▶│Entidades│─────▶│ Leiden  │─────▶│Community│    │
│  │ Chunks  │      │Relaciones│     │Hierarchy│      │ Reports │    │
│  │(300 tok)│      │         │      │         │      │         │    │
│  └─────────┘      └─────────┘      └─────────┘      └─────────┘    │
│                                                                     │
│  5. Documentos    6. Visualización  7. Embeddings                  │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐                     │
│  │Link docs│      │Node2Vec │      │ Vector  │                     │
│  │to units │      │ + UMAP  │      │ repr.   │                     │
│  └─────────┘      └─────────┘      └─────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### Fase 1: Composición de TextUnits
- Documentos → chunks de 300 tokens (configurable)
- Respeta límites de documentos
- Relación 1:N documento → text_units

#### Fase 2: Extracción de Grafos
- Extrae entidades (personas, lugares, eventos)
- Extrae relaciones entre entidades
- Consolida descripciones múltiples de misma entidad
- Opcional: extrae Covariates (afirmaciones temporales)

#### Fase 3: Detección de Comunidades (Leiden)
- Algoritmo jerárquico de Leiden
- Detecta comunidades de forma recursiva
- Crea estructura multinivel (Level 0, Level 1, ...)
- Umbrales de tamaño configurables

#### Fase 4: Summarización de Comunidades
- Genera reportes para cada comunidad
- Bottom-up: niveles bajos → niveles altos
- Resúmenes extensos + versiones abreviadas

#### Fase 5-7: Documentos, Visualización, Embeddings
- Enlaza documentos con TextUnits
- Node2Vec + UMAP para visualización 2D
- Embeddings de: entidades, text_units, community_reports

### Modelo de Conocimiento

7 tipos de entidades exportadas:
- **Documents**: documentos originales
- **TextUnits**: chunks
- **Entities**: nodos del grafo
- **Relationships**: edges del grafo
- **Covariates**: afirmaciones temporales
- **Communities**: clusters detectados
- **Community Reports**: resúmenes por comunidad

### Retrieval

| Modo | Mecanismo | Uso |
|------|-----------|-----|
| **Local** | Búsqueda en entidades + relaciones | Preguntas específicas |
| **Global** | Map-reduce sobre community reports | Preguntas temáticas amplias |

### Resultados

- 70-80% win rate vs naive RAG en comprehensiveness
- 20-70% menos tokens por query usando community summaries

### Relevancia para nuestro proyecto

- **Muy aplicable**: Estructura jerárquica de comunidades
- **Aplicable**: Community reports para queries globales sobre KDD
- **Considerar**: Leiden para agrupar entidades KDD relacionadas
- **Evaluar**: Costo de LLM para summarización de comunidades

---

## 3. HippoRAG / HippoRAG 2

**Paper**: [HippoRAG: Neurobiologically Inspired RAG](https://arxiv.org/abs/2405.14831)

**Repo**: [https://github.com/OSU-NLP-Group/HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG)

### Inspiración: Memoria Humana

El sistema emula el hipocampo humano:
- **Neocortex** → LLM (procesamiento semántico)
- **Hipocampo** → Grafo de conocimiento (indexación)
- **Parahippocampal Regions** → Retrieval (PageRank)

### Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    INDEXACIÓN                           │
├─────────────────────────────────────────────────────────┤
│  Documento → LLM Extractor → Tripletas (S, P, O)       │
│                                   ↓                     │
│                            Grafo de Conocimiento        │
│                                   ↓                     │
│                         Embeddings (entidades, hechos)  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    RETRIEVAL                            │
├─────────────────────────────────────────────────────────┤
│  Query → Extraer entidades → Personalized PageRank     │
│                                   ↓                     │
│                         Ranking de nodos relevantes     │
│                                   ↓                     │
│                         Pasajes asociados               │
└─────────────────────────────────────────────────────────┘
```

### Extracción de Tripletas

- **Sujeto**: entidad principal
- **Predicado**: relación/acción
- **Objeto**: entidad relacionada

Ejemplo: `(Cardiologist, treats, Heart Disease)`

### Personalized PageRank (PPR)

1. Inicia con entidades de la query como "semillas"
2. Propaga relevancia por el grafo
3. Detecta conexiones multi-hop
4. Ranking personalizado por query

### Ventajas

| Aspecto | HippoRAG vs Otros |
|---------|-------------------|
| Costo indexación | Menor que GraphRAG, RAPTOR, LightRAG |
| Latencia query | Baja (eficiente en online) |
| Multi-hop | Excelente (PPR detecta caminos) |
| Aprendizaje continuo | Sí, sin reentrenamiento |

### Modelos Soportados

- Embeddings: NV-Embed-v2, GritLM, Contriever
- LLM: OpenAI GPT, vLLM (local)
- Modo batch offline para indexación 3x más rápida

### Relevancia para nuestro proyecto

- **Muy aplicable**: Tripletas mapean bien a KDD (Entity RELATES_TO Entity)
- **Aplicable**: PPR para retrieval multi-hop en el grafo
- **Considerar**: Aprendizaje continuo para actualizaciones incrementales
- **Evaluar**: vLLM para extracción local (sin API externa)

---

## 4. RAPTOR

**Paper**: [RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval](https://arxiv.org/abs/2401.18059)

**Repo**: [https://github.com/parthsarthi03/raptor](https://github.com/parthsarthi03/raptor)

### Concepto Central

Construye un **árbol de resúmenes** de abajo hacia arriba:
- Hojas: chunks originales del documento
- Nodos intermedios: resúmenes de clusters
- Raíz: resumen global

### Proceso de Construcción

```
Nivel 3 (raíz):     [Resumen Global]
                          ↑
Nivel 2:        [Resumen A]  [Resumen B]
                    ↑             ↑
Nivel 1:      [Res1] [Res2]  [Res3] [Res4]
                ↑       ↑       ↑       ↑
Nivel 0:     [C1][C2] [C3][C4] [C5][C6] [C7][C8]
             └──────────────────────────────────┘
                    Chunks originales
```

### Algoritmo

1. **Embedding**: Genera embeddings de cada chunk
2. **Clustering**: Agrupa chunks similares (GMM o K-means)
3. **Summarization**: LLM genera resumen de cada cluster
4. **Recursión**: Repite 1-3 con los resúmenes hasta convergencia

### Retrieval

- Puede recuperar desde cualquier nivel del árbol
- Queries de detalle → niveles bajos (chunks)
- Queries temáticas → niveles altos (resúmenes)
- Combina ambos para contexto completo

### Resultados

- +20% accuracy absoluta en QuALITY benchmark (con GPT-4)
- Mejor en preguntas multi-step reasoning
- Mantiene granularidad + visión global

### Diferencia con GraphRAG

| Aspecto | RAPTOR | GraphRAG |
|---------|--------|----------|
| Estructura | Árbol de resúmenes | Grafo de entidades |
| Agrupación | Por similitud semántica | Por relaciones estructurales |
| Entidades | No explícitas | Explícitas (nodos) |
| Relaciones | Implícitas (clustering) | Explícitas (edges) |

### Relevancia para nuestro proyecto

- **Parcialmente aplicable**: Idea de niveles jerárquicos
- **Considerar**: Combinar con grafo (árbol de resúmenes POR comunidad)
- **No directamente aplicable**: No extrae entidades explícitas (necesario para KDD)

---

## 5. HybridRAG

**Paper**: [HybridRAG: Integrating Knowledge Graphs and Vector Retrieval](https://arxiv.org/abs/2408.04948)

### Concepto

Combina VectorRAG y GraphRAG en paralelo, fusionando resultados.

### Arquitectura

```
                    ┌─────────────┐
                    │    Query    │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               │               ▼
    ┌─────────────┐        │        ┌─────────────┐
    │  VectorRAG  │        │        │  GraphRAG   │
    │  (embeddings)│       │        │    (KG)     │
    └──────┬──────┘        │        └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                    ┌─────────────┐
                    │   Fusión    │
                    │  Contexto   │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │     LLM     │
                    │  Respuesta  │
                    └─────────────┘
```

### Resultados

- Supera a VectorRAG solo
- Supera a GraphRAG solo
- Mejor en retrieval accuracy y answer generation

### Relevancia para nuestro proyecto

- **Directamente aplicable**: Es exactamente nuestro enfoque (vector + grafo)
- **Validación**: Confirma que híbrido > individual
- **Considerar**: Estrategia de fusión de resultados

---

## 6. Comparativa de Enfoques

### Por Tipo de Query

| Tipo de Query | Mejor Enfoque |
|---------------|---------------|
| Hechos específicos | VectorRAG, HippoRAG (low-level) |
| Relaciones entre entidades | GraphRAG, HippoRAG (PPR) |
| Temas globales/resúmenes | GraphRAG (communities), RAPTOR |
| Multi-hop reasoning | HippoRAG, GraphRAG |
| Preguntas híbridas | HybridRAG, LightRAG (dual-level) |

### Por Costo Computacional

| Framework | Indexación | Query | LLM Calls |
|-----------|------------|-------|-----------|
| VectorRAG | Bajo | Bajo | Solo generación |
| LightRAG | Medio | Bajo | Extracción + generación |
| HippoRAG | Medio | Bajo | Extracción + generación |
| RAPTOR | Alto | Bajo | Summarización recursiva |
| GraphRAG | Alto | Medio | Extracción + comunidades + generación |

### Por Actualización Incremental

| Framework | Soporte Incremental |
|-----------|---------------------|
| VectorRAG | Sí (append embeddings) |
| LightRAG | Sí (diseñado para esto) |
| HippoRAG | Sí (aprendizaje continuo) |
| RAPTOR | Parcial (rebuild árbol) |
| GraphRAG | Parcial (rebuild comunidades) |

---

## 7. Recomendaciones para kdd-engine

### Arquitectura Propuesta

Basándome en la investigación, recomiendo una arquitectura híbrida inspirada en:

1. **LightRAG**: Dual-level retrieval + actualización incremental
2. **HippoRAG**: Extracción de tripletas + PPR para multi-hop
3. **GraphRAG**: Comunidades jerárquicas para queries globales

### Pipeline de Indexación Propuesto

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PIPELINE kdd-engine                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Parsing KDD    2. Chunking      3. Extracción    4. Grafo      │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐    │
│  │Frontmatter│───▶│Por tipo │─────▶│Entidades│─────▶│ Nodos + │    │
│  │+ Markdown│     │ KDD    │      │Relaciones│     │ Edges   │    │
│  └─────────┘      └─────────┘      └─────────┘      └─────────┘    │
│       │                │                                 │          │
│       ▼                ▼                                 ▼          │
│  ┌─────────┐      ┌─────────┐                      ┌─────────┐     │
│  │Trazabil.│      │Embeddings│                     │Comunidades│    │
│  │PostgreSQL│     │VectorDB │                     │ (Leiden) │     │
│  └─────────┘      └─────────┘                      └─────────┘     │
│                                                          │          │
│                                                          ▼          │
│                                                    ┌─────────┐     │
│                                                    │Community│     │
│                                                    │ Reports │     │
│                                                    └─────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Decisiones Preliminares

| DC | Decisión Sugerida | Inspiración |
|----|-------------------|-------------|
| DC-003 | Multi-estrategia: frontmatter + patrones + LLM | LightRAG, HippoRAG |
| DC-004 | Por tipo KDD + híbrido si excede | GraphRAG TextUnits |
| DC-008 | PostgreSQL source of truth + sync jobs | - |
| DC-010 | Repository pattern con factory | - |
| DC-011 | Git-native con mapeo configurable | - |

---

## 8. Referencias

- [LightRAG](https://lightrag.github.io/)
- [Microsoft GraphRAG](https://microsoft.github.io/graphrag/)
- [HippoRAG - GitHub](https://github.com/OSU-NLP-Group/HippoRAG)
- [RAPTOR Paper](https://arxiv.org/abs/2401.18059)
- [HybridRAG Paper](https://arxiv.org/abs/2408.04948)
- [GraphRAG Survey](https://arxiv.org/abs/2501.00309)
- [Awesome-GraphRAG](https://github.com/DEEP-PolyU/Awesome-GraphRAG)

---

*Documento de investigación - Última actualización: Sesión de diseño*
