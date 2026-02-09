"""Entity document ingestion pipeline."""

import time
from pathlib import Path

import structlog

from kb_engine.smart.chunking import HierarchicalChunker, LLMSummaryService, MockSummaryService
from kb_engine.smart.extraction import EntityGraphExtractor
from kb_engine.smart.parsers import DocumentKindDetector, EntityParser
from kb_engine.smart.schemas import ENTITY_SCHEMA
from kb_engine.smart.stores import FalkorDBGraphStore
from kb_engine.smart.types import IngestionResult, KDDDocumentKind

logger = structlog.get_logger(__name__)


class EntityIngestionPipeline:
    """Complete pipeline for ingesting entity KDD documents.

    This pipeline:
    1. Detects document type (must be entity)
    2. Parses using EntityParser
    3. Generates hierarchical chunks with summaries
    4. Extracts entities and stores in FalkorDB graph
    5. Returns ingestion result with statistics

    Example:
        ```python
        from kb_engine.smart.pipelines import EntityIngestionPipeline

        pipeline = EntityIngestionPipeline(graph_path="./kb-graph.db")

        with open("domain/entities/User.md") as f:
            content = f.read()

        result = await pipeline.ingest(content, filename="User.md")
        print(f"Created {result.chunks_created} chunks")
        print(f"Extracted {result.entities_extracted} entities")
        ```
    """

    def __init__(
        self,
        graph_path: str | Path = ".kb/graph.db",
        use_mock_summarizer: bool = False,
        max_chunk_size: int = 1024,
        chunk_overlap: int = 50,
    ) -> None:
        """Initialize the entity ingestion pipeline.

        Args:
            graph_path: Path to FalkorDB graph database file.
            use_mock_summarizer: Use mock summarizer (no LLM calls) for testing.
            max_chunk_size: Maximum chunk size in characters.
            chunk_overlap: Overlap between text chunks.
        """
        self._graph_path = Path(graph_path)

        # Initialize components
        self._detector = DocumentKindDetector()
        self._parser = EntityParser(schema=ENTITY_SCHEMA)

        # Summary service
        if use_mock_summarizer:
            self._summarizer = MockSummaryService()
        else:
            self._summarizer = LLMSummaryService()

        self._chunker = HierarchicalChunker(
            summary_service=self._summarizer,
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # Graph store (lazy init)
        self._graph_store: FalkorDBGraphStore | None = None
        self._extractor: EntityGraphExtractor | None = None

    def _init_graph(self) -> None:
        """Lazy initialization of graph store."""
        if self._graph_store is None:
            self._graph_store = FalkorDBGraphStore(self._graph_path)
            self._graph_store.initialize()
            self._extractor = EntityGraphExtractor(self._graph_store)

    async def ingest(
        self,
        content: str,
        filename: str | None = None,
        skip_graph: bool = False,
    ) -> IngestionResult:
        """Ingest an entity document.

        Args:
            content: Raw markdown content of the entity document.
            filename: Optional filename for context.
            skip_graph: If True, skip storing to graph (for testing).

        Returns:
            IngestionResult with counts and any errors.
        """
        start_time = time.time()
        result = IngestionResult()
        log = logger.bind(filename=filename, skip_graph=skip_graph)

        log.debug("pipeline.start", content_length=len(content))

        try:
            # 1. Detect document type
            log.debug("pipeline.step.detect.start")
            detection = self._detector.detect(content, filename)
            result.document_kind = detection.kind
            result.detection_confidence = detection.confidence
            log.debug(
                "pipeline.step.detect.complete",
                kind=detection.kind.value,
                confidence=detection.confidence,
            )

            if detection.kind != KDDDocumentKind.ENTITY:
                log.warning(
                    "pipeline.step.detect.rejected",
                    expected="entity",
                    got=detection.kind.value,
                )
                result.validation_errors.append(
                    f"Expected entity document, got {detection.kind.value}"
                )
                return result

            # 2. Parse document
            log.debug("pipeline.step.parse.start")
            parsed = self._parser.parse(content, filename)
            result.validation_errors.extend(parsed.validation_errors)
            log.debug(
                "pipeline.step.parse.complete",
                title=parsed.title,
                sections=len(parsed.sections),
                validation_errors=len(parsed.validation_errors),
            )

            if parsed.validation_errors:
                result.warnings.append("Document has validation errors but will be processed")

            # 3. Extract entity info
            log.debug("pipeline.step.extract_info.start")
            entity_info = self._parser.extract_entity_info(parsed)
            log.debug(
                "pipeline.step.extract_info.complete",
                attributes=len(entity_info.attributes),
                relations=len(entity_info.relations),
                states=len(entity_info.states),
            )

            # Document ID and path propagation for provenance
            doc_id = parsed.frontmatter.get("id", entity_info.name)
            parsed.frontmatter.setdefault("path", filename or "")
            result.document_id = doc_id
            log = log.bind(doc_id=doc_id)

            # 4. Generate hierarchical chunks
            log.debug("pipeline.step.chunk.start")
            chunks = await self._chunker.chunk(parsed, ENTITY_SCHEMA)
            result.chunks_created = len(chunks)
            chunk_types = {}
            for c in chunks:
                chunk_types[c.chunk_type] = chunk_types.get(c.chunk_type, 0) + 1
            log.debug(
                "pipeline.step.chunk.complete",
                total_chunks=len(chunks),
                chunk_types=chunk_types,
            )

            # 5. Store in graph
            if not skip_graph:
                log.debug("pipeline.step.graph.start")
                self._init_graph()
                nodes, edges = self._extractor.extract_and_store(parsed, entity_info)
                result.entities_extracted = nodes
                result.relations_created = edges
                log.debug(
                    "pipeline.step.graph.complete",
                    nodes=nodes,
                    edges=edges,
                )
            else:
                # Count what would be created
                ref_attr_count = sum(1 for a in entity_info.attributes if a.is_reference)
                result.entities_extracted = (
                    1 +  # Document node
                    1 +  # main entity
                    len(entity_info.attributes) +
                    len(entity_info.states) +
                    len(entity_info.relations) +
                    ref_attr_count +  # stub entities from reference attributes
                    len(entity_info.events_emitted) +
                    len(entity_info.events_consumed)
                )
                result.relations_created = (
                    1 +  # EXTRACTED_FROM for main entity
                    len(entity_info.attributes) +  # EXTRACTED_FROM for attributes
                    len(entity_info.attributes) +  # CONTAINS for attributes
                    len(entity_info.states) +  # EXTRACTED_FROM for states
                    len(entity_info.states) +  # CONTAINS for states
                    len(entity_info.relations) +  # EXTRACTED_FROM for related entities
                    len(entity_info.relations) +  # REFERENCES
                    ref_attr_count +  # EXTRACTED_FROM for ref attr stubs
                    ref_attr_count +  # REFERENCES from attrs
                    len(entity_info.events_emitted) +  # EXTRACTED_FROM for events emitted
                    len(entity_info.events_emitted) +  # PRODUCES
                    len(entity_info.events_consumed) +  # EXTRACTED_FROM for events consumed
                    len(entity_info.events_consumed)  # CONSUMES
                )
                log.debug("pipeline.step.graph.skipped")

            result.success = True
            log.info(
                "pipeline.complete",
                chunks=result.chunks_created,
                entities=result.entities_extracted,
                relations=result.relations_created,
            )

        except Exception as e:
            log.exception("pipeline.error", error=str(e))
            result.validation_errors.append(f"Pipeline error: {str(e)}")
            result.success = False

        result.processing_time_ms = (time.time() - start_time) * 1000
        log.debug("pipeline.timing", duration_ms=result.processing_time_ms)
        return result

    async def ingest_file(
        self,
        file_path: str | Path,
        skip_graph: bool = False,
    ) -> IngestionResult:
        """Ingest an entity document from file path.

        Args:
            file_path: Path to the markdown file.
            skip_graph: If True, skip storing to graph.

        Returns:
            IngestionResult.
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return await self.ingest(content, filename=path.name, skip_graph=skip_graph)

    def close(self) -> None:
        """Close graph store connection."""
        if self._graph_store:
            self._graph_store.close()

    def get_graph_stats(self) -> dict:
        """Get graph database statistics."""
        self._init_graph()
        return self._graph_store.get_stats()

    def query_graph(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a Cypher query on the graph.

        Args:
            cypher: Cypher query string.
            params: Query parameters.

        Returns:
            List of result dictionaries.
        """
        self._init_graph()
        return self._graph_store.execute_cypher(cypher, params)
