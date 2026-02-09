"""Retrieval pipeline - returns document references with URLs."""

import time

import structlog

from kb_engine.core.models.search import (
    DocumentReference,
    RetrievalMode,
    RetrievalResponse,
    SearchFilters,
)
from kb_engine.embedding import EmbeddingConfig, EmbeddingProviderFactory
from kb_engine.git.url_resolver import URLResolver
from kb_engine.utils.markdown import extract_snippet, heading_path_to_anchor

logger = structlog.get_logger(__name__)


class RetrievalPipeline:
    """Pipeline for processing retrieval queries.

    Returns DocumentReference objects with full URLs (including #anchors)
    instead of raw document content. This allows external agents to
    read the source documents directly.
    """

    def __init__(
        self,
        traceability_repo,
        vector_repo,
        graph_repo=None,
        url_resolver: URLResolver | None = None,
        embedding_config: EmbeddingConfig | None = None,
    ) -> None:
        self._traceability = traceability_repo
        self._vector = vector_repo
        self._graph = graph_repo
        self._url_resolver = url_resolver

        self._embedding_provider = EmbeddingProviderFactory(embedding_config).create_provider()

    async def search(
        self,
        query: str,
        mode: RetrievalMode = RetrievalMode.VECTOR,
        filters: SearchFilters | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> RetrievalResponse:
        """Execute a retrieval query, returning document references."""
        start_time = time.time()

        references: list[DocumentReference] = []

        if mode in (RetrievalMode.VECTOR, RetrievalMode.HYBRID):
            vector_refs = await self._vector_search(
                query, filters, limit, score_threshold
            )
            references.extend(vector_refs)

        if mode in (RetrievalMode.GRAPH, RetrievalMode.HYBRID):
            graph_refs = await self._graph_search(query, filters, limit)
            references.extend(graph_refs)

        # Deduplicate by URL if hybrid
        if mode == RetrievalMode.HYBRID:
            references = self._deduplicate_references(references, limit)

        # Sort by score descending
        references.sort(key=lambda r: r.score, reverse=True)
        references = references[:limit]

        processing_time = (time.time() - start_time) * 1000

        return RetrievalResponse(
            query=query,
            references=references,
            total_count=len(references),
            processing_time_ms=processing_time,
        )

    async def _vector_search(
        self,
        query: str,
        filters: SearchFilters | None,
        limit: int,
        score_threshold: float | None,
    ) -> list[DocumentReference]:
        """Perform vector similarity search and resolve to references."""
        query_vector = await self._embedding_provider.embed_text(query)

        chunk_scores = await self._vector.search(
            query_vector=query_vector,
            limit=limit,
            filters=filters,
            score_threshold=score_threshold,
        )

        references = []
        for chunk_id, score in chunk_scores:
            chunk = await self._traceability.get_chunk(chunk_id)
            if not chunk:
                continue

            document = await self._traceability.get_document(chunk.document_id)
            if not document:
                continue

            # Resolve URL
            anchor = chunk.section_anchor or heading_path_to_anchor(chunk.heading_path)
            if self._url_resolver and document.relative_path:
                url = self._url_resolver.resolve(document.relative_path, anchor)
            elif document.source_path:
                url = f"file://{document.source_path}"
                if anchor:
                    url += f"#{anchor}"
            else:
                url = f"doc://{document.id}"

            # Build section title from heading path
            section_title = chunk.heading_path[-1] if chunk.heading_path else None

            references.append(
                DocumentReference(
                    url=url,
                    document_path=document.relative_path or document.source_path or "",
                    section_anchor=anchor,
                    title=document.title,
                    section_title=section_title,
                    score=score,
                    snippet=extract_snippet(chunk.content),
                    domain=document.domain,
                    tags=document.tags,
                    chunk_type=chunk.chunk_type.value,
                    metadata=chunk.metadata,
                    retrieval_mode=RetrievalMode.VECTOR,
                )
            )

        return references

    async def _graph_search(
        self,
        query: str,
        filters: SearchFilters | None,
        limit: int,
    ) -> list[DocumentReference]:
        """Graph-based search: find nodes matching query and return related documents."""
        if not self._graph:
            logger.debug("graph_search.skipped", reason="no graph repository")
            return []

        # Find nodes matching the query by name
        matching_nodes = await self._graph.find_nodes(
            name_pattern=query,
            limit=limit * 2,  # Get extra to account for filtering
        )

        if not matching_nodes:
            return []

        references: list[DocumentReference] = []
        seen_keys: set[str] = set()

        for node in matching_nodes:
            # Get edges for this node to include relationship info
            edges = await self._graph.get_edges(node.id, direction="both")

            # Build relationship metadata
            relationships = []
            for edge in edges[:5]:  # Limit to 5 relationships per node
                other_node_id = edge.target_id if edge.source_id == node.id else edge.source_id
                other_node = await self._graph.get_node(other_node_id)
                other_name = other_node.name if other_node else str(other_node_id)

                rel_info = {
                    "type": edge.edge_type.value,
                    "direction": "outgoing" if edge.source_id == node.id else "incoming",
                    "related_node": other_name,
                    "confidence": edge.confidence,
                }
                relationships.append(rel_info)

            # Try to resolve document via source_chunk_id first
            chunk = None
            document = None
            anchor = None
            section_title = None

            if node.source_chunk_id:
                chunk_key = str(node.source_chunk_id)
                if chunk_key in seen_keys:
                    continue
                seen_keys.add(chunk_key)

                chunk = await self._traceability.get_chunk(node.source_chunk_id)
                if chunk:
                    document = await self._traceability.get_document(chunk.document_id)
                    anchor = chunk.section_anchor or heading_path_to_anchor(chunk.heading_path)
                    section_title = chunk.heading_path[-1] if chunk.heading_path else None

            # Fallback: try to find document by node name (for nodes without chunk_id)
            if not document and node.source_document_id:
                doc_key = str(node.source_document_id)
                if doc_key in seen_keys:
                    continue
                seen_keys.add(doc_key)
                document = await self._traceability.get_document(node.source_document_id)

            # Last resort: search for document by title matching node name
            if not document:
                node_key = f"node:{node.id}"
                if node_key in seen_keys:
                    continue
                seen_keys.add(node_key)

                # Search documents by title
                docs = await self._traceability.list_documents(limit=100)
                for doc in docs:
                    if doc.title and node.name.lower() in doc.title.lower():
                        document = doc
                        break

            if not document:
                continue

            # Resolve URL
            if self._url_resolver and document.relative_path:
                url = self._url_resolver.resolve(document.relative_path, anchor)
            elif document.source_path:
                url = f"file://{document.source_path}"
                if anchor:
                    url += f"#{anchor}"
            else:
                url = f"doc://{document.id}"

            # Build metadata with graph info
            metadata = dict(chunk.metadata) if chunk and chunk.metadata else {}
            metadata["graph_node_name"] = node.name
            metadata["graph_node_type"] = node.node_type.value
            metadata["graph_relationships"] = relationships
            if node.description:
                metadata["graph_node_description"] = node.description

            # Score based on node confidence and number of relationships
            score = node.confidence * (1 + len(relationships) * 0.1)

            # Build snippet from chunk or node description
            if chunk:
                snippet = extract_snippet(chunk.content)
                chunk_type = chunk.chunk_type.value
            else:
                snippet = node.description or f"Graph node: {node.name}"
                chunk_type = "graph_node"

            references.append(
                DocumentReference(
                    url=url,
                    document_path=document.relative_path or document.source_path or "",
                    section_anchor=anchor,
                    title=document.title,
                    section_title=section_title,
                    score=min(score, 1.0),
                    snippet=snippet,
                    domain=document.domain,
                    tags=document.tags,
                    chunk_type=chunk_type,
                    metadata=metadata,
                    retrieval_mode=RetrievalMode.GRAPH,
                )
            )

            if len(references) >= limit:
                break

        return references

    def _deduplicate_references(
        self,
        references: list[DocumentReference],
        limit: int,
    ) -> list[DocumentReference]:
        """Deduplicate references using Reciprocal Rank Fusion."""
        url_scores: dict[str, tuple[DocumentReference, float]] = {}
        k = 60  # RRF constant

        for rank, ref in enumerate(references):
            rrf_score = 1.0 / (k + rank + 1)
            if ref.url in url_scores:
                existing_ref, existing_score = url_scores[ref.url]
                url_scores[ref.url] = (existing_ref, existing_score + rrf_score)
            else:
                url_scores[ref.url] = (ref, rrf_score)

        merged = []
        for ref, rrf_score in url_scores.values():
            ref.score = rrf_score
            ref.retrieval_mode = RetrievalMode.HYBRID
            merged.append(ref)

        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[:limit]
