# ADR-0003: Pipeline de Extracción de Entidades Multi-estrategia

---
id: ADR-0003
status: superseded
superseded_note: "Migración a TypeScript/Bun (Feb 2026). Reemplazado por 16 extractores dedicados por KDDKind (src/application/extractors/kinds/). Cada extractor entiende la estructura de su tipo. No hay pipeline multi-estrategia — un extractor por kind, registrado en ExtractorRegistry."
date: 2025-01-16
deciders: [leopoldo, claude]
consulted: []
informed: []
related_dc: DC-003
supersedes: null
superseded_by: null
---

## Contexto

El sistema necesita extraer entidades y relaciones de documentos KDD para poblar el grafo de conocimiento. Las entidades incluyen: Entity, Rule, UseCase, Process, Event, PRD, etc.

Características del problema:
- Documentos KDD tienen front-matter YAML estructurado con metadatos ricos
- Relaciones explícitas en campos como `related`, `invokes`, `produces`
- Enlaces wiki-style en contenido: `[[Entity]]`
- Referencias a IDs en texto: `UC-Checkout`, `RUL-Discount`
- Posibles relaciones implícitas en texto libre

Se evaluaron 5 opciones desde solo front-matter hasta LLM completo.

## Decisión

**Adoptamos un Pipeline de Extracción Multi-estrategia con Front-matter + Patrones como base y LLM opcional.**

La estrategia aprovecha que KDD ya tiene estructura rica, minimizando llamadas a LLM mientras permite enriquecimiento opcional.

### Arquitectura

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import yaml

# ============================================================
# MODELOS
# ============================================================

class NodeType(str, Enum):
    """Tipos de nodos — implementados en kdd_engine.core.models.graph."""
    ENTITY = "entity"
    USE_CASE = "use_case"
    RULE = "rule"
    PROCESS = "process"
    ACTOR = "actor"
    SYSTEM = "system"
    CONCEPT = "concept"
    DOCUMENT = "document"
    CHUNK = "chunk"


class EdgeType(str, Enum):
    """Tipos de relaciones — implementados en kdd_engine.core.models.graph."""
    # Structural
    CONTAINS = "CONTAINS"
    PART_OF = "PART_OF"
    REFERENCES = "REFERENCES"
    # Domain
    IMPLEMENTS = "IMPLEMENTS"
    DEPENDS_ON = "DEPENDS_ON"
    RELATED_TO = "RELATED_TO"
    TRIGGERS = "TRIGGERS"
    USES = "USES"
    PRODUCES = "PRODUCES"
    # Actor
    PERFORMS = "PERFORMS"
    OWNS = "OWNS"
    # Semantic
    SIMILAR_TO = "SIMILAR_TO"
    CONTRADICTS = "CONTRADICTS"
    EXTENDS = "EXTENDS"


@dataclass
class ExtractedNode:
    """Nodo extraído del documento."""
    id: str                          # ID único (ej: UC-Checkout@v1)
    name: str                        # Nombre legible
    node_type: NodeType
    source_document_id: str          # Documento de donde se extrajo
    source_chunk_id: Optional[str]   # Chunk específico (si aplica)
    properties: dict = field(default_factory=dict)
    confidence: float = 1.0          # 1.0 para estructurado, < 1.0 para inferido
    extraction_method: str = ""      # frontmatter, pattern, llm


@dataclass
class ExtractedEdge:
    """Relación extraída del documento."""
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    source_document_id: str
    properties: dict = field(default_factory=dict)
    confidence: float = 1.0
    extraction_method: str = ""


@dataclass
class ExtractionResult:
    """Resultado de extracción de un documento."""
    document_id: str
    nodes: List[ExtractedNode] = field(default_factory=list)
    edges: List[ExtractedEdge] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ============================================================
# EXTRACTORES
# ============================================================

class Extractor(ABC):
    """Interfaz base para extractores."""

    @abstractmethod
    def extract(self, document: "Document", content: str) -> ExtractionResult:
        """Extrae entidades y relaciones del documento."""
        ...


class FrontmatterExtractor(Extractor):
    """
    Extrae entidades y relaciones del front-matter YAML.

    Campos procesados:
    - id: identificador del nodo principal
    - kind: tipo de documento KDD
    - aliases: nombres alternativos
    - related: relaciones genéricas
    - invokes: reglas invocadas (UseCase → Rule)
    - produces: eventos producidos (UseCase → Event)
    - validates: qué valida (Scenario → UseCase/Rule)
    - domain: dominio al que pertenece
    """

    # Mapeo de kind KDD a NodeType
    KIND_TO_NODE_TYPE = {
        "entity": NodeType.ENTITY,
        "use_case": NodeType.USE_CASE,
        "rule": NodeType.RULE,
        "process": NodeType.PROCESS,
        # Tipos KDD no mapeados directamente se asignan a CONCEPT
    }

    # Mapeo de campo frontmatter a tipo de relación
    FIELD_TO_EDGE_TYPE = {
        "related": EdgeType.RELATED_TO,
        "references": EdgeType.REFERENCES,
        "implements": EdgeType.IMPLEMENTS,
        "depends_on": EdgeType.DEPENDS_ON,
    }

    def extract(self, document: "Document", content: str) -> ExtractionResult:
        result = ExtractionResult(document_id=document.id)

        # Parsear front-matter
        frontmatter = self._parse_frontmatter(content)
        if not frontmatter:
            result.warnings.append("No front-matter found")
            return result

        # Crear nodo principal del documento
        main_node = self._create_main_node(document, frontmatter)
        result.nodes.append(main_node)

        # Extraer relaciones de campos específicos
        for field, edge_type in self.FIELD_TO_EDGE_TYPE.items():
            if field in frontmatter:
                edges = self._extract_edges_from_field(
                    source_id=main_node.id,
                    targets=frontmatter[field],
                    edge_type=edge_type,
                    document_id=document.id
                )
                result.edges.extend(edges)

        # Extraer nodos de aliases
        if aliases := frontmatter.get("aliases", []):
            main_node.properties["aliases"] = aliases

        return result

    def _parse_frontmatter(self, content: str) -> Optional[dict]:
        """Extrae y parsea el front-matter YAML."""
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        try:
            return yaml.safe_load(parts[1])
        except yaml.YAMLError:
            return None

    def _create_main_node(self, document: "Document", frontmatter: dict) -> ExtractedNode:
        """Crea el nodo principal del documento."""
        node_id = frontmatter.get("id", document.id)
        kind = frontmatter.get("kind", "unknown")
        node_type = self.KIND_TO_NODE_TYPE.get(kind, NodeType.UNKNOWN)

        # Extraer nombre del título H1 si existe
        name = self._extract_title(document.content) or node_id

        return ExtractedNode(
            id=node_id,
            name=name,
            node_type=node_type,
            source_document_id=document.id,
            source_chunk_id=None,
            properties={
                "status": frontmatter.get("status"),
                "domain": frontmatter.get("domain"),
                "tags": frontmatter.get("tags", []),
                "owner": frontmatter.get("owner"),
            },
            confidence=1.0,
            extraction_method="frontmatter"
        )

    def _extract_title(self, content: str) -> Optional[str]:
        """Extrae el título H1 del contenido."""
        for line in content.split("\n"):
            if line.startswith("# ") and not line.startswith("## "):
                return line[2:].strip()
        return None

    def _extract_edges_from_field(
        self,
        source_id: str,
        targets: any,
        edge_type: EdgeType,
        document_id: str
    ) -> List[ExtractedEdge]:
        """Extrae edges de un campo que contiene referencias."""
        edges = []

        # Normalizar a lista
        if isinstance(targets, str):
            targets = [targets]
        elif not isinstance(targets, list):
            return edges

        for target in targets:
            if isinstance(target, str) and target.strip():
                edges.append(ExtractedEdge(
                    source_node_id=source_id,
                    target_node_id=target.strip(),
                    edge_type=edge_type,
                    source_document_id=document_id,
                    confidence=1.0,
                    extraction_method="frontmatter"
                ))

        return edges


class PatternExtractor(Extractor):
    """
    Extrae referencias mediante patrones en el contenido.

    Patrones reconocidos:
    - Wiki links: [[Entity Name]]
    - IDs KDD: UC-*, RUL-*, PRC-*, EVT-*, ADR-*, PRD-*, REQ-*, STORY-*
    """

    # Patrones de entidades en texto (implementados en PatternExtractor)
    ENTITY_PATTERNS = [
        # (regex, NodeType, confidence)
        (r"(?:actor|usuario|user|...)[\s:]+(\w+)", NodeType.ACTOR, 0.8),
        (r"(?:sistema|system|servicio|...)[\s:]+(\w+)", NodeType.SYSTEM, 0.8),
        (r"(?:entidad|entity|objeto|...)[\s:]+(\w+)", NodeType.ENTITY, 0.8),
        (r"(?:caso de uso|use case|CU[-_]?\d+)[\s:]+(\w+)", NodeType.USE_CASE, 0.85),
        (r"(?:regla|rule|RN[-_]?\d+|BR[-_]?\d+)[\s:]+(\w+)", NodeType.RULE, 0.85),
    ]

    # Patrón para wiki links [[...]]
    WIKI_LINK_PATTERN = r'\[\[([^\]]+)\]\]'

    def extract(self, document: "Document", content: str) -> ExtractionResult:
        result = ExtractionResult(document_id=document.id)

        # Obtener ID del documento principal (del front-matter)
        main_node_id = self._get_main_node_id(content) or document.id

        # Extraer referencias de wiki links
        wiki_refs = self._extract_wiki_links(content)
        for ref in wiki_refs:
            result.edges.append(ExtractedEdge(
                source_node_id=main_node_id,
                target_node_id=ref,
                edge_type=EdgeType.REFERENCES,
                source_document_id=document.id,
                confidence=0.9,
                extraction_method="pattern_wiki"
            ))

        # Extraer entidades y relaciones por patrones en texto
        # (actores, sistemas, dependencias, etc.)

        return result

    def _get_main_node_id(self, content: str) -> Optional[str]:
        """Obtiene el ID del nodo principal del front-matter."""
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            fm = yaml.safe_load(parts[1])
            return fm.get("id")
        except:
            return None

    def _extract_wiki_links(self, content: str) -> Set[str]:
        """Extrae referencias de wiki links [[...]]."""
        # Ignorar front-matter
        content_body = self._get_body(content)
        matches = re.findall(self.WIKI_LINK_PATTERN, content_body)
        return set(matches)

    def _extract_id_references(
        self,
        content: str,
        exclude_id: str
    ) -> List[Tuple[str, NodeType]]:
        """Extrae referencias a IDs KDD en el contenido."""
        content_body = self._get_body(content)
        refs = []
        seen = set()

        for pattern, node_type in self.ID_PATTERNS.items():
            matches = re.findall(pattern, content_body)
            for match in matches:
                if match not in seen and match != exclude_id:
                    refs.append((match, node_type))
                    seen.add(match)

        return refs

    def _get_body(self, content: str) -> str:
        """Obtiene el contenido sin front-matter."""
        if not content.startswith("---"):
            return content
        parts = content.split("---", 2)
        return parts[2] if len(parts) >= 3 else content


class LLMExtractor(Extractor):
    """
    Extrae entidades y relaciones usando LLM.

    Útil para:
    - Relaciones implícitas en texto libre
    - Entidades no estructuradas
    - Enriquecimiento semántico
    """

    def __init__(self, llm_client: any, model: str = "gpt-4o-mini"):
        self.llm = llm_client
        self.model = model

    EXTRACTION_PROMPT = """Analiza el siguiente documento de especificación técnica y extrae:
1. Entidades mencionadas (conceptos de negocio, servicios, datos)
2. Relaciones entre entidades

Contexto: Este es un documento de tipo "{doc_kind}" del sistema KDD.

Documento:
{content}

Responde en JSON con este formato:
{{
  "entities": [
    {{"name": "...", "type": "entity|service|data|concept", "description": "..."}}
  ],
  "relations": [
    {{"source": "...", "target": "...", "relation": "uses|contains|depends_on|relates_to", "description": "..."}}
  ]
}}

Solo incluye entidades y relaciones que estén claramente mencionadas o implicadas en el texto.
No incluyas las ya declaradas en el front-matter (id, related, invokes, etc.)."""

    def extract(self, document: "Document", content: str) -> ExtractionResult:
        result = ExtractionResult(document_id=document.id)

        try:
            # Preparar prompt
            doc_kind = document.metadata.get("kind", "unknown")
            prompt = self.EXTRACTION_PROMPT.format(
                doc_kind=doc_kind,
                content=content[:4000]  # Limitar contenido
            )

            # Llamar LLM
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            # Parsear respuesta
            import json
            data = json.loads(response.choices[0].message.content)

            # Procesar entidades
            main_node_id = self._get_main_node_id(content) or document.id
            for entity in data.get("entities", []):
                # Crear nodo referenciado (placeholder)
                result.nodes.append(ExtractedNode(
                    id=self._generate_id(entity["name"]),
                    name=entity["name"],
                    node_type=self._map_type(entity.get("type", "concept")),
                    source_document_id=document.id,
                    properties={"description": entity.get("description", "")},
                    confidence=0.7,
                    extraction_method="llm"
                ))

            # Procesar relaciones
            for rel in data.get("relations", []):
                result.edges.append(ExtractedEdge(
                    source_node_id=main_node_id,
                    target_node_id=self._generate_id(rel["target"]),
                    edge_type=self._map_relation(rel.get("relation", "relates_to")),
                    source_document_id=document.id,
                    properties={"description": rel.get("description", "")},
                    confidence=0.7,
                    extraction_method="llm"
                ))

        except Exception as e:
            result.warnings.append(f"LLM extraction failed: {str(e)}")

        return result

    def _get_main_node_id(self, content: str) -> Optional[str]:
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            fm = yaml.safe_load(parts[1])
            return fm.get("id")
        except:
            return None

    def _generate_id(self, name: str) -> str:
        """Genera un ID a partir del nombre."""
        return name.lower().replace(" ", "-")

    def _map_type(self, type_str: str) -> NodeType:
        mapping = {
            "entity": NodeType.ENTITY,
            "service": NodeType.SYSTEM,
            "data": NodeType.ENTITY,
            "concept": NodeType.CONCEPT,
        }
        return mapping.get(type_str, NodeType.CONCEPT)

    def _map_relation(self, rel_str: str) -> EdgeType:
        mapping = {
            "uses": EdgeType.USES,
            "contains": EdgeType.CONTAINS,
            "depends_on": EdgeType.DEPENDS_ON,
            "relates_to": EdgeType.RELATED_TO,
        }
        return mapping.get(rel_str, EdgeType.RELATED_TO)


# ============================================================
# PIPELINE
# ============================================================

@dataclass
class ExtractionConfig:
    """Configuración del pipeline de extracción."""
    enable_frontmatter: bool = True
    enable_patterns: bool = True
    enable_llm: bool = False
    llm_client: any = None
    llm_model: str = "gpt-4o-mini"
    deduplicate: bool = True
    min_confidence: float = 0.5


class ExtractionPipeline:
    """
    Pipeline de extracción de entidades y relaciones.

    Combina múltiples extractores y deduplica resultados.
    """

    def __init__(self, config: ExtractionConfig):
        self.config = config
        self.extractors: List[Extractor] = []

        # Siempre incluir front-matter (es la fuente más confiable)
        if config.enable_frontmatter:
            self.extractors.append(FrontmatterExtractor())

        # Patrones para capturar referencias en contenido
        if config.enable_patterns:
            self.extractors.append(PatternExtractor())

        # LLM para extracción avanzada (opcional)
        if config.enable_llm and config.llm_client:
            self.extractors.append(LLMExtractor(
                llm_client=config.llm_client,
                model=config.llm_model
            ))

    def extract(self, document: "Document") -> ExtractionResult:
        """Ejecuta el pipeline de extracción."""
        combined = ExtractionResult(document_id=document.id)

        # Ejecutar cada extractor
        for extractor in self.extractors:
            result = extractor.extract(document, document.content)
            combined.nodes.extend(result.nodes)
            combined.edges.extend(result.edges)
            combined.warnings.extend(result.warnings)

        # Deduplicar si está habilitado
        if self.config.deduplicate:
            combined = self._deduplicate(combined)

        # Filtrar por confianza mínima
        combined.nodes = [
            n for n in combined.nodes
            if n.confidence >= self.config.min_confidence
        ]
        combined.edges = [
            e for e in combined.edges
            if e.confidence >= self.config.min_confidence
        ]

        return combined

    def _deduplicate(self, result: ExtractionResult) -> ExtractionResult:
        """Deduplica nodos y edges, priorizando mayor confianza."""
        # Deduplicar nodos por ID
        nodes_by_id = {}
        for node in result.nodes:
            if node.id not in nodes_by_id:
                nodes_by_id[node.id] = node
            else:
                # Mantener el de mayor confianza
                if node.confidence > nodes_by_id[node.id].confidence:
                    nodes_by_id[node.id] = node

        # Deduplicar edges por (source, target, type)
        edges_by_key = {}
        for edge in result.edges:
            key = (edge.source_node_id, edge.target_node_id, edge.edge_type)
            if key not in edges_by_key:
                edges_by_key[key] = edge
            else:
                if edge.confidence > edges_by_key[key].confidence:
                    edges_by_key[key] = edge

        return ExtractionResult(
            document_id=result.document_id,
            nodes=list(nodes_by_id.values()),
            edges=list(edges_by_key.values()),
            warnings=result.warnings
        )


# ============================================================
# FACTORY
# ============================================================

class ExtractionPipelineFactory:
    """Factory para crear pipelines de extracción."""

    @staticmethod
    def create_default() -> ExtractionPipeline:
        """Pipeline por defecto: front-matter + patrones."""
        return ExtractionPipeline(ExtractionConfig(
            enable_frontmatter=True,
            enable_patterns=True,
            enable_llm=False
        ))

    @staticmethod
    def create_with_llm(llm_client: any, model: str = "gpt-4o-mini") -> ExtractionPipeline:
        """Pipeline con LLM para extracción avanzada."""
        return ExtractionPipeline(ExtractionConfig(
            enable_frontmatter=True,
            enable_patterns=True,
            enable_llm=True,
            llm_client=llm_client,
            llm_model=model
        ))

    @staticmethod
    def create_minimal() -> ExtractionPipeline:
        """Pipeline mínimo: solo front-matter."""
        return ExtractionPipeline(ExtractionConfig(
            enable_frontmatter=True,
            enable_patterns=False,
            enable_llm=False
        ))
```

### Ejemplo de Uso

```python
# Documento de ejemplo
doc = Document(
    id="doc-123",
    content="""---
id: UC-Checkout@v1
kind: use_case
status: approved
invokes: [RUL-ValidateCart, RUL-ApplyDiscount]
produces: [EVT-OrderCreated]
related: [UC-Payment]
---
# Realizar Checkout

## Descripción
El usuario completa su compra. Ver [[Carrito]] para detalles.

## Flujo Principal
1. Sistema valida el carrito (RUL-ValidateCart)
2. Aplica descuentos según RUL-ApplyDiscount
3. Procesa el pago via UC-Payment
""",
    metadata={"kind": "use_case"}
)

# Pipeline por defecto
pipeline = ExtractionPipelineFactory.create_default()
result = pipeline.extract(doc)

# Resultado:
# Nodes: [UC-Checkout@v1]
# Edges:
#   - UC-Checkout@v1 --RELATED_TO--> RUL-ValidateCart (frontmatter, conf=1.0)
#   - UC-Checkout@v1 --RELATED_TO--> RUL-ApplyDiscount (frontmatter, conf=1.0)
#   - UC-Checkout@v1 --RELATED_TO--> UC-Payment (frontmatter, conf=1.0)
#   - UC-Checkout@v1 --REFERENCES--> Carrito (pattern_wiki, conf=0.9)
```

## Justificación

1. **Aprovecha estructura KDD**: El front-matter ya contiene la mayoría de relaciones importantes con 100% de confianza.

2. **Mínimo uso de LLM**: 90%+ de casos cubiertos sin LLM, reduciendo costos y latencia.

3. **Inspirado en papers**:
   - LightRAG/HippoRAG extraen con LLM, pero KDD ya está estructurado
   - GraphRAG consolida entidades duplicadas → nuestro `deduplicate()`

4. **Confianza explícita**: Cada extracción tiene un score de confianza para priorizar en retrieval.

5. **Extensible**: Añadir nuevo extractor = implementar `Extractor` + agregar a pipeline.

## Alternativas Consideradas

### Alternativa 1: Solo Front-matter

Extraer únicamente del YAML estructurado.

**Descartada porque**:
- Pierde referencias en contenido (`[[Entity]]`)
- No captura menciones a IDs en texto libre

### Alternativa 2: LLM para Todo

Usar LLM para toda la extracción.

**Descartada porque**:
- Costoso e innecesario para datos ya estructurados
- Puede alucinar entidades
- Mayor latencia de indexación

### Alternativa 3: spaCy NER

Usar NER de spaCy para detectar entidades.

**Descartada como requerimiento base porque**:
- Requiere entrenamiento para dominio KDD
- Front-matter + patrones cubren la mayoría de casos
- Puede añadirse después si se necesita

## Consecuencias

### Positivas

- Extracción rápida y confiable para mayoría de casos
- Costos de LLM opcionales y controlados
- Trazabilidad clara (sabemos de dónde viene cada extracción)
- Confianza explícita permite priorización

### Negativas

- Relaciones muy implícitas en texto libre no se capturan sin LLM
- Patrones regex pueden tener falsos positivos
- Documentos mal estructurados producen menos extracciones

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Patrón no reconoce nuevo formato ID | Media | Bajo | Patrones configurables |
| LLM alucina entidades | Media | Medio | Confianza < 1.0, validación humana |
| Front-matter incompleto | Media | Bajo | Patrones como fallback |

## Plan de Implementación

- [x] Crear módulo `kdd_engine.extraction`
- [x] Implementar FrontmatterExtractor
- [x] Implementar PatternExtractor
- [x] Implementar LLMExtractor (opcional, desactivado por defecto)
- [x] Implementar ExtractionPipeline con deduplicación
- [x] Crear ExtractionPipelineFactory
- [x] Tests unitarios por extractor
- [x] Integrar con IndexationPipeline

## Referencias

- [Design Challenge DC-003](../challenges/DC-003-entity-extraction.md)
- [LightRAG Entity Extraction](https://lightrag.github.io/)
- [HippoRAG Triplet Extraction](https://github.com/OSU-NLP-Group/HippoRAG)
- [GraphRAG Entity Resolution](https://microsoft.github.io/graphrag/)
- [Metodología KDD](../kdd.md)
