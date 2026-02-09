"""Entity extractor protocol as defined in ADR-0003."""

from dataclasses import dataclass
from typing import Protocol

from kb_engine.core.models.document import Chunk, Document
from kb_engine.core.models.graph import Edge, Node


@dataclass
class GraphExtractionResult:
    """Result of graph extraction strategy."""

    nodes_created: int = 0
    edges_created: int = 0


class ExtractionResult:
    """Result of entity extraction."""

    def __init__(
        self,
        nodes: list[Node] | None = None,
        edges: list[Edge] | None = None,
    ) -> None:
        self.nodes = nodes or []
        self.edges = edges or []


class EntityExtractor(Protocol):
    """Protocol for entity extractors.

    Extractors identify entities and relationships from chunks
    to build the knowledge graph.
    """

    @property
    def name(self) -> str:
        """The name of this extractor."""
        ...

    @property
    def priority(self) -> int:
        """Extraction priority (lower = higher priority)."""
        ...

    def can_extract(self, chunk: Chunk, document: Document) -> bool:
        """Check if this extractor can process the given chunk.

        Args:
            chunk: The chunk to potentially extract from.
            document: The source document.

        Returns:
            True if this extractor should process this chunk.
        """
        ...

    async def extract(
        self,
        chunk: Chunk,
        document: Document,
    ) -> ExtractionResult:
        """Extract entities and relationships from a chunk.

        Args:
            chunk: The chunk to extract from.
            document: The source document for context.

        Returns:
            ExtractionResult containing nodes and edges.
        """
        ...
