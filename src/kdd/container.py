"""Dependency injection container.

Wires all infrastructure adapters and application components based on
available resources (embedding model, API keys).  Used by CLI and API
entry points.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from kdd.application.extractors.registry import ExtractorRegistry, create_default_registry
from kdd.application.queries.index_loader import IndexLoader
from kdd.domain.enums import IndexLevel
from kdd.domain.ports import EmbeddingModel, EventBus, GraphStore, VectorStore
from kdd.domain.rules import detect_index_level
from kdd.infrastructure.artifact.filesystem import FilesystemArtifactStore
from kdd.infrastructure.events.bus import InMemoryEventBus
from kdd.infrastructure.graph.networkx_store import NetworkXGraphStore

logger = logging.getLogger(__name__)


@dataclass
class Container:
    """Holds all wired dependencies for a KDD session."""

    specs_root: Path
    index_path: Path
    index_level: IndexLevel
    artifact_store: FilesystemArtifactStore
    graph_store: NetworkXGraphStore
    vector_store: VectorStore | None
    embedding_model: EmbeddingModel | None
    event_bus: EventBus
    registry: ExtractorRegistry
    loader: IndexLoader

    def ensure_loaded(self) -> bool:
        """Load index into memory if not already loaded."""
        return self.loader.load()


def create_container(
    specs_root: Path,
    index_path: Path | None = None,
    *,
    embedding_model_name: str | None = None,
) -> Container:
    """Create a fully wired Container.

    Auto-detects index level based on available resources:
    - L1: always (no embedding model needed)
    - L2: if sentence-transformers + hnswlib are available
    - L3: not auto-detected (requires explicit agent config)
    """
    if index_path is None:
        index_path = specs_root.parent / ".kdd-index"

    artifact_store = FilesystemArtifactStore(index_path)
    graph_store = NetworkXGraphStore()
    event_bus = InMemoryEventBus()
    registry = create_default_registry()

    # Attempt to load embedding model and vector store
    embedding_model: EmbeddingModel | None = None
    vector_store: VectorStore | None = None

    if embedding_model_name is not False:
        try:
            from kdd.infrastructure.embedding.sentence_transformer import (
                SentenceTransformerModel,
            )
            from kdd.infrastructure.vector.hnswlib_store import HNSWLibVectorStore

            model_name = embedding_model_name or "all-MiniLM-L6-v2"
            embedding_model = SentenceTransformerModel(model_name)
            vector_store = HNSWLibVectorStore()
            logger.info("L2 available: embedding model '%s' loaded", model_name)
        except ImportError:
            logger.info("L2 not available: sentence-transformers or hnswlib not installed")
        except Exception as e:
            logger.warning("L2 not available: %s", e)

    index_level = detect_index_level(
        embedding_model_available=embedding_model is not None,
        agent_api_available=False,
    )

    loader = IndexLoader(artifact_store, graph_store, vector_store)

    return Container(
        specs_root=specs_root,
        index_path=index_path,
        index_level=index_level,
        artifact_store=artifact_store,
        graph_store=graph_store,
        vector_store=vector_store,
        embedding_model=embedding_model,
        event_bus=event_bus,
        registry=registry,
        loader=loader,
    )
