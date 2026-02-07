"""Core domain models and interfaces for KB-Engine."""

from kb_engine.core.exceptions import (
    ChunkingError,
    ConfigurationError,
    ExtractionError,
    KBPodError,
    RepositoryError,
    ValidationError,
)
from kb_engine.core.models import (
    EXTENSION_DEFAULTS,
    Chunk,
    Document,
    DocumentReference,
    Edge,
    EdgeType,
    Embedding,
    FileTypeConfig,
    Node,
    NodeType,
    RetrievalMode,
    RetrievalResponse,
    RepositoryConfig,
    SearchFilters,
)

__all__ = [
    # Models
    "Document",
    "Chunk",
    "Embedding",
    "Node",
    "Edge",
    "NodeType",
    "EdgeType",
    "SearchFilters",
    "DocumentReference",
    "RetrievalResponse",
    "RetrievalMode",
    "RepositoryConfig",
    "FileTypeConfig",
    "EXTENSION_DEFAULTS",
    # Exceptions
    "KBPodError",
    "ConfigurationError",
    "ValidationError",
    "RepositoryError",
    "ChunkingError",
    "ExtractionError",
]
