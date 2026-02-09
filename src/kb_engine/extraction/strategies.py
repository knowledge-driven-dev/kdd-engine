"""Graph extraction strategies for the indexation pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

from kb_engine.core.interfaces.extractors import GraphExtractionResult

if TYPE_CHECKING:
    from kb_engine.core.models.document import Chunk, Document
    from kb_engine.extraction.pipeline import ExtractionPipeline
    from kb_engine.smart.stores.falkordb_graph import FalkorDBGraphStore

logger = structlog.get_logger(__name__)


class GraphExtractionStrategy(Protocol):
    """Protocol for graph extraction strategies."""

    async def extract_and_store(
        self, document: Document, chunks: list[Chunk]
    ) -> GraphExtractionResult: ...

    async def delete_by_document(self, document_id: str) -> None: ...


class SmartGraphExtractionStrategy:
    """Graph extraction using FalkorDB with KDD-aware entity parsing.

    Uses DocumentKindDetector + EntityParser + EntityGraphExtractor
    to produce a rich knowledge graph from KDD documents.
    For non-entity documents, creates a basic document node.
    """

    def __init__(self, graph_store: FalkorDBGraphStore) -> None:
        self._graph_store = graph_store

    async def extract_and_store(
        self, document: Document, chunks: list[Chunk]
    ) -> GraphExtractionResult:
        from kb_engine.smart.parsers.detector import DocumentKindDetector
        from kb_engine.smart.parsers.entity import EntityParser
        from kb_engine.smart.extraction.entity import EntityGraphExtractor
        from kb_engine.smart.types import KDDDocumentKind

        log = logger.bind(document_id=str(document.id), title=document.title)

        detector = DocumentKindDetector()
        detection = detector.detect(
            document.content,
            filename=document.relative_path or document.source_path,
        )
        log.debug(
            "smart_strategy.detected",
            kind=detection.kind.value,
            confidence=detection.confidence,
        )

        if detection.kind == KDDDocumentKind.ENTITY and detection.confidence >= 0.5:
            parser = EntityParser()
            parsed = parser.parse(
                document.content,
                filename=document.relative_path,
            )
            entity_info = parser.extract_entity_info(parsed)

            # Override source doc id and propagate path for provenance
            doc_id = str(document.id)
            parsed.frontmatter["id"] = doc_id
            parsed.frontmatter["path"] = document.relative_path or document.source_path or ""

            extractor = EntityGraphExtractor(self._graph_store)
            nodes, edges = extractor.extract_and_store(parsed, entity_info)

            log.info(
                "smart_strategy.entity_extracted",
                entity=entity_info.name,
                nodes=nodes,
                edges=edges,
            )
            return GraphExtractionResult(nodes_created=nodes, edges_created=edges)

        # Non-entity document: create Document node + basic Entity node + EXTRACTED_FROM
        doc_id = str(document.id)
        doc_path = document.relative_path or document.source_path or ""
        doc_kind = detection.kind.value

        self._graph_store.upsert_document(
            doc_id=doc_id,
            title=document.title,
            path=doc_path,
            kind=doc_kind,
        )

        entity_id = f"doc:{doc_id}"
        self._graph_store.upsert_entity(
            entity_id=entity_id,
            name=document.title,
            description=f"Document: {document.title}",
            confidence=0.5,
        )
        self._graph_store.add_extracted_from(entity_id, "Entity", doc_id, "primary", 0.5)

        log.debug("smart_strategy.basic_node", kind=detection.kind.value)
        return GraphExtractionResult(nodes_created=2, edges_created=1)

    async def delete_by_document(self, document_id: str) -> None:
        self._graph_store.delete_by_source_doc(document_id)


class LegacyGraphExtractionStrategy:
    """Graph extraction wrapping the original ExtractionPipeline + GraphRepository.

    Preserves existing SQLite/Neo4j behavior without changes.
    """

    def __init__(self, graph_repo, extraction_pipeline: ExtractionPipeline) -> None:
        self._graph = graph_repo
        self._extraction_pipeline = extraction_pipeline

    async def extract_and_store(
        self, document: Document, chunks: list[Chunk]
    ) -> GraphExtractionResult:
        from kb_engine.core.models.graph import Node

        extraction_result = await self._extraction_pipeline.extract_document(
            document, chunks
        )
        nodes_created = 0
        for node_data in extraction_result.nodes:
            node = Node(
                name=node_data.name,
                node_type=node_data.node_type,
                description=node_data.description,
                source_document_id=document.id,
                properties=node_data.properties,
                confidence=node_data.confidence,
                extraction_method=node_data.extraction_method,
            )
            await self._graph.create_node(node)
            nodes_created += 1

        return GraphExtractionResult(
            nodes_created=nodes_created,
            edges_created=0,
        )

    async def delete_by_document(self, document_id: str) -> None:
        await self._graph.delete_by_document(document_id)
