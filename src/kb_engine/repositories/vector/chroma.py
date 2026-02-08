"""ChromaDB implementation of the vector repository."""

from pathlib import Path
from uuid import UUID

import structlog

from kb_engine.core.models.embedding import Embedding
from kb_engine.core.models.search import SearchFilters

logger = structlog.get_logger(__name__)


class ChromaRepository:
    """ChromaDB embedded implementation for vector storage and search.

    Uses ChromaDB in embedded mode (in-process, persistent on disk).
    """

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "kb_engine_embeddings",
    ) -> None:
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._client = None
        self._collection = None

    async def initialize(self) -> None:
        """Initialize ChromaDB client and collection."""
        import chromadb
        from chromadb.config import Settings

        Path(self._persist_directory).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self._persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB repository initialized",
            path=self._persist_directory,
            collection=self._collection_name,
        )

    def _ensure_collection(self):
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings

            Path(self._persist_directory).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self._persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def upsert_embeddings(self, embeddings: list[Embedding]) -> int:
        collection = self._ensure_collection()
        if not embeddings:
            return 0

        ids = [str(e.chunk_id) for e in embeddings]
        vectors = [e.vector for e in embeddings]
        metadatas = [
            {
                "chunk_id": str(e.chunk_id),
                "document_id": str(e.document_id),
                "model": e.model,
                **{k: str(v) for k, v in e.metadata.items()},
            }
            for e in embeddings
        ]

        collection.upsert(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas,
        )
        return len(embeddings)

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filters: SearchFilters | None = None,
        score_threshold: float | None = None,
    ) -> list[tuple[UUID, float]]:
        collection = self._ensure_collection()

        where_filter = None
        if filters:
            where_conditions = []
            if filters.document_ids:
                where_conditions.append(
                    {"document_id": {"$in": [str(d) for d in filters.document_ids]}}
                )
            if filters.chunk_types:
                where_conditions.append(
                    {"chunk_type": {"$in": filters.chunk_types}}
                )
            if filters.domains:
                where_conditions.append(
                    {"domain": {"$in": filters.domains}}
                )
            if len(where_conditions) == 1:
                where_filter = where_conditions[0]
            elif len(where_conditions) > 1:
                where_filter = {"$and": where_conditions}

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=limit,
            where=where_filter,
            include=["distances"],
        )

        chunk_scores: list[tuple[UUID, float]] = []
        if results["ids"] and results["distances"]:
            for chunk_id_str, distance in zip(
                results["ids"][0], results["distances"][0], strict=True
            ):
                # ChromaDB returns cosine distance; convert to similarity score
                score = 1.0 - distance
                if score_threshold is not None and score < score_threshold:
                    continue
                chunk_scores.append((UUID(chunk_id_str), score))

        return chunk_scores

    async def delete_by_document(self, document_id: UUID) -> int:
        collection = self._ensure_collection()
        try:
            # Get all embeddings for this document
            results = collection.get(
                where={"document_id": str(document_id)},
                include=[],
            )
            if results["ids"]:
                collection.delete(ids=results["ids"])
                return len(results["ids"])
        except Exception:
            logger.warning("Failed to delete by document", document_id=str(document_id))
        return 0

    async def delete_by_chunk_ids(self, chunk_ids: list[UUID]) -> int:
        collection = self._ensure_collection()
        ids = [str(cid) for cid in chunk_ids]
        try:
            collection.delete(ids=ids)
            return len(ids)
        except Exception:
            logger.warning("Failed to delete by chunk IDs")
            return 0

    async def get_collection_info(self) -> dict[str, int | str]:
        collection = self._ensure_collection()
        return {
            "name": self._collection_name,
            "count": collection.count(),
            "persist_directory": self._persist_directory,
        }
