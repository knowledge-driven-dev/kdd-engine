# ADR-0001: Repository Pattern para Abstracción de Almacenamiento

---
id: ADR-0001
status: superseded
superseded_note: "Migración a TypeScript/Bun (Feb 2026). El nuevo stack usa stores in-memory (graphology + brute-force cosine) cargados de ficheros JSON (.kdd-index/). No hay Repository Pattern — los stores se inyectan directamente via container.ts."
date: 2025-01-16
deciders: [leopoldo, claude]
consulted: []
informed: []
related_dc: DC-010
supersedes: null
superseded_by: null
---

## Contexto

El sistema de retrieval requiere trabajar con tres bases de datos diferentes:
- **Trazabilidad**: Metadatos y lineage (SQLite local / PostgreSQL server)
- **Vector DB**: Embeddings (ChromaDB local / Qdrant server)
- **Graph DB**: Grafo de conocimiento (SQLite local / Neo4j server) — opcional

Necesitamos una capa de abstracción que permita:
1. Cambiar de motor sin modificar lógica de negocio
2. Testear con mocks/fakes
3. Mantener el código desacoplado de implementaciones específicas

Se evaluaron 4 opciones:
- Usar abstracciones de un framework directamente
- Ports & Adapters (Hexagonal Architecture)
- Híbrido (framework + extensiones)
- Repository Pattern con Factory

## Decisión

**Adoptamos el Repository Pattern con Factory** para abstraer el acceso a las bases de datos.

### Interfaces de Repositorio

```python
from typing import Protocol, List, Optional
from dataclasses import dataclass

# ============================================================
# MODELOS DE DOMINIO
# ============================================================

@dataclass
class Document:
    id: str
    external_ref: str
    source_type: str  # 'repository' | 'upload'
    kind: str  # tipo KDD
    domain: str
    lifecycle_state: str  # 'dev' | 'staging' | 'pro' | 'deprecated'
    git_repo: Optional[str]
    git_ref: Optional[str]
    git_commit_sha: Optional[str]
    content_hash: str
    content: str

@dataclass
class Chunk:
    id: str
    document_id: str
    sequence: int
    content: str
    metadata: dict
    content_hash: str
    lifecycle_state: str

@dataclass
class Embedding:
    id: str
    chunk_id: str
    vector: List[float]
    model: str
    lifecycle_state: str

@dataclass
class Node:
    id: str
    document_id: str
    chunk_id: Optional[str]
    node_type: str  # tipo KDD (Entity, Rule, UseCase, etc.)
    name: str
    properties: dict
    lifecycle_state: str
    validation_status: str  # 'draft' | 'validated' | 'approved'

@dataclass
class Edge:
    id: str
    document_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str  # RELATES_TO, INVOKES, PRODUCES, etc.
    properties: dict
    lifecycle_state: str

@dataclass
class SearchFilters:
    lifecycle_states: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    node_types: Optional[List[str]] = None
    document_ids: Optional[List[str]] = None

@dataclass
class SearchResult:
    id: str
    score: float
    content: str
    metadata: dict
    document_id: str
    chunk_id: Optional[str]

# ============================================================
# INTERFACES DE REPOSITORIO
# ============================================================

class TraceabilityRepository(Protocol):
    """Repositorio para PostgreSQL - trazabilidad y metadatos."""

    # Documents
    async def save_document(self, doc: Document) -> str: ...
    async def get_document(self, doc_id: str) -> Optional[Document]: ...
    async def get_document_by_ref(self, external_ref: str, domain: str) -> Optional[Document]: ...
    async def update_document(self, doc: Document) -> None: ...
    async def delete_document(self, doc_id: str) -> None: ...
    async def list_documents(self, filters: SearchFilters) -> List[Document]: ...

    # Chunks
    async def save_chunks(self, chunks: List[Chunk]) -> List[str]: ...
    async def get_chunks_by_document(self, doc_id: str) -> List[Chunk]: ...
    async def delete_chunks_by_document(self, doc_id: str) -> None: ...

    # Embeddings (referencias)
    async def save_embedding_refs(self, embeddings: List[Embedding]) -> List[str]: ...
    async def get_embedding_refs_by_document(self, doc_id: str) -> List[Embedding]: ...
    async def delete_embedding_refs_by_document(self, doc_id: str) -> None: ...

    # Nodes (referencias)
    async def save_node_refs(self, nodes: List[Node]) -> List[str]: ...
    async def get_node_refs_by_document(self, doc_id: str) -> List[Node]: ...
    async def delete_node_refs_by_document(self, doc_id: str) -> None: ...

    # Edges (referencias)
    async def save_edge_refs(self, edges: List[Edge]) -> List[str]: ...
    async def get_edge_refs_by_document(self, doc_id: str) -> List[Edge]: ...
    async def delete_edge_refs_by_document(self, doc_id: str) -> None: ...

    # Lifecycle
    async def update_lifecycle_state(self, doc_id: str, new_state: str) -> None: ...

    # Lineage queries
    async def get_document_lineage(self, doc_id: str) -> dict: ...


class VectorRepository(Protocol):
    """Repositorio para Vector DB - embeddings y búsqueda semántica."""

    async def save_embeddings(self, embeddings: List[Embedding]) -> List[str]: ...
    async def search(
        self,
        query_vector: List[float],
        filters: SearchFilters,
        top_k: int = 10
    ) -> List[SearchResult]: ...
    async def delete_by_ids(self, ids: List[str]) -> None: ...
    async def delete_by_document(self, doc_id: str) -> None: ...
    async def update_lifecycle_state(self, ids: List[str], new_state: str) -> None: ...


class GraphRepository(Protocol):
    """Repositorio para Graph DB - nodos y relaciones."""

    # Nodes
    async def save_nodes(self, nodes: List[Node]) -> List[str]: ...
    async def get_node(self, node_id: str) -> Optional[Node]: ...
    async def search_nodes(
        self,
        query: str,
        filters: SearchFilters,
        top_k: int = 10
    ) -> List[Node]: ...
    async def delete_nodes_by_document(self, doc_id: str) -> None: ...

    # Edges
    async def save_edges(self, edges: List[Edge]) -> List[str]: ...
    async def get_edges_by_node(self, node_id: str) -> List[Edge]: ...
    async def delete_edges_by_document(self, doc_id: str) -> None: ...

    # Traversal (inspirado en HippoRAG PPR)
    async def traverse(
        self,
        start_nodes: List[str],
        max_depth: int = 2,
        edge_types: Optional[List[str]] = None,
        filters: SearchFilters = None
    ) -> List[Node]: ...

    # Community detection (inspirado en GraphRAG)
    async def detect_communities(self, algorithm: str = "leiden") -> List[dict]: ...
    async def get_community_nodes(self, community_id: str) -> List[Node]: ...

    # Lifecycle
    async def update_lifecycle_state(self, doc_id: str, new_state: str) -> None: ...


# ============================================================
# FACTORY
# ============================================================

class RepositoryFactory:
    """Factory para crear instancias de repositorios según configuración."""

    @staticmethod
    def create_traceability(config: dict) -> TraceabilityRepository:
        """Crea repositorio de trazabilidad."""
        store_type = config.get("traceability_store", "sqlite")

        if store_type == "sqlite":
            from .implementations.sqlite import SQLiteRepository
            return SQLiteRepository(config)
        elif store_type == "postgres":
            from .implementations.postgres import PostgresRepository
            return PostgresRepository(config)
        else:
            raise ValueError(f"Traceability store not supported: {store_type}")

    @staticmethod
    def create_vector(config: dict) -> VectorRepository:
        """Crea repositorio vectorial según configuración."""
        vector_type = config.get("vector_store", "chroma")

        if vector_type == "chroma":
            from .implementations.chroma import ChromaRepository
            return ChromaRepository(config)
        elif vector_type == "qdrant":
            from .implementations.qdrant import QdrantRepository
            return QdrantRepository(config)
        else:
            raise ValueError(f"Vector store not supported: {vector_type}")

    @staticmethod
    def create_graph(config: dict) -> GraphRepository | None:
        """Crea repositorio de grafos según configuración. Retorna None si desactivado."""
        graph_type = config.get("graph_store", "sqlite")

        if graph_type == "none":
            return None
        elif graph_type == "sqlite":
            from .implementations.sqlite_graph import SQLiteGraphRepository
            return SQLiteGraphRepository(config)
        elif graph_type == "neo4j":
            from .implementations.neo4j import Neo4jRepository
            return Neo4jRepository(config)
        else:
            raise ValueError(f"Graph store not supported: {graph_type}")
```

### Ejemplo de Uso

```python
# Configuración
config = {
    "postgres": {"host": "localhost", "port": 5432, "db": "kbpod"},
    "vector_db": "qdrant",
    "qdrant": {"host": "localhost", "port": 6333},
    "graph_db": "neo4j",
    "neo4j": {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "..."}
}

# Crear repositorios
trace_repo = RepositoryFactory.create_traceability(config)
vector_repo = RepositoryFactory.create_vector(config)
graph_repo = RepositoryFactory.create_graph(config)

# Usar en servicio de indexación
class IndexingService:
    def __init__(
        self,
        trace_repo: TraceabilityRepository,
        vector_repo: VectorRepository,
        graph_repo: GraphRepository
    ):
        self.trace = trace_repo
        self.vector = vector_repo
        self.graph = graph_repo

    async def index_document(self, doc: Document, chunks: List[Chunk], ...):
        # 1. Guardar en trazabilidad (source of truth)
        doc_id = await self.trace.save_document(doc)
        await self.trace.save_chunks(chunks)

        # 2. Guardar embeddings
        embedding_ids = await self.vector.save_embeddings(embeddings)
        await self.trace.save_embedding_refs(embeddings)

        # 3. Guardar nodos/edges
        node_ids = await self.graph.save_nodes(nodes)
        await self.trace.save_node_refs(nodes)
        # ...
```

## Justificación

1. **Control total**: Tenemos control completo sobre las interfaces y operaciones específicas que necesitamos (lifecycle, trazabilidad, comunidades).

2. **Alineado con DDD**: Las interfaces están definidas en términos del dominio (Document, Chunk, Node) no de tecnología (QdrantClient, Neo4jDriver).

3. **Testeable**: Podemos crear implementaciones fake/mock para tests sin necesidad de bases de datos reales.

4. **Extensible**: Añadir un nuevo motor (ej: Milvus, ArangoDB) solo requiere implementar la interfaz correspondiente.

5. **Inspirado en papers**: HippoRAG y GraphRAG usan abstracciones similares para mantener flexibilidad.

## Alternativas Consideradas

### Alternativa 1: Framework RAG Puro

Usar abstracciones de un framework RAG (ej: VectorStore, GraphStore) directamente.

**Descartada porque**:
- Menos control sobre operaciones específicas (lifecycle, trazabilidad)
- Dependencia fuerte del roadmap del framework
- Las abstracciones de grafo suelen ser menos maduras

### Alternativa 2: Ports & Adapters sin Factory

Definir puertos e implementar adaptadores, pero sin factory centralizada.

**Descartada porque**:
- Más código boilerplate para instanciar
- Menos conveniente para tests y configuración por entorno

### Alternativa 3: Híbrido Framework + Extensiones

Usar un framework RAG donde sea posible, extender con interfaces propias.

**Descartada porque**:
- Dos modelos mentales (cuándo usar qué)
- Posibles conflictos de abstracción

## Consecuencias

### Positivas

- Código de negocio completamente desacoplado de implementaciones
- Fácil cambiar de Qdrant a Weaviate sin tocar servicios
- Tests unitarios sin dependencias externas
- Configuración centralizada por entorno

### Negativas

- Más código inicial que usar un framework directamente
- Debemos mantener las implementaciones de cada adaptador
- Posible divergencia si los motores tienen capacidades muy diferentes

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Interfaz no cubre caso de uso futuro | Media | Medio | Diseño extensible, interfaces Protocol |
| Implementaciones divergen en comportamiento | Baja | Alto | Tests de integración por implementación |
| Overhead de abstracción en rendimiento | Baja | Bajo | Las interfaces son thin wrappers |

## Plan de Implementación

- [x] Crear módulo `kb_engine.repositories`
- [x] Implementar modelos de dominio (Pydantic BaseModel)
- [x] Definir interfaces (Protocol)
- [x] Implementar SQLiteRepository (trazabilidad, perfil local)
- [x] Implementar ChromaRepository (vectorial, perfil local)
- [x] Implementar SQLiteGraphRepository (grafos, perfil local)
- [x] Crear tests con implementaciones SQLite
- [ ] Implementar PostgresRepository (trazabilidad, perfil server)
- [ ] Implementar QdrantRepository (vectorial, perfil server)
- [ ] Implementar Neo4jRepository (grafos, perfil server)

## Referencias

- [Design Challenge DC-010](../challenges/DC-010-engine-abstraction.md)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Ports and Adapters](https://alistair.cockburn.us/hexagonal-architecture/)
- [HippoRAG Implementation](https://github.com/OSU-NLP-Group/HippoRAG)
