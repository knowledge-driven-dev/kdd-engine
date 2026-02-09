"""Integration tests for the smart pipeline with FalkorDB."""

import asyncio
from pathlib import Path

import pytest

from kb_engine.smart import (
    DocumentKindDetector,
    EntityIngestionPipeline,
    EntityParser,
    FalkorDBGraphStore,
    KDDDocumentKind,
)

# Test fixtures
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "entities" / "Usuario.md"
TEST_GRAPH_PATH = Path("/tmp/kb-engine-test-graph.db")
TEST_PROVENANCE_GRAPH_PATH = Path("/tmp/kb-engine-test-provenance-graph.db")


def _cleanup_db(path: Path) -> None:
    """Remove a FalkorDB database file and its settings file."""
    if path.exists():
        path.unlink()
    settings = Path(str(path) + ".settings")
    if settings.exists():
        settings.unlink()


@pytest.fixture(autouse=True)
def cleanup_graph():
    """Clean up test graph before and after tests."""
    _cleanup_db(TEST_GRAPH_PATH)
    _cleanup_db(TEST_PROVENANCE_GRAPH_PATH)
    yield
    _cleanup_db(TEST_GRAPH_PATH)
    _cleanup_db(TEST_PROVENANCE_GRAPH_PATH)


class TestDocumentKindDetector:
    """Tests for document kind detection."""

    def test_detect_entity_from_frontmatter(self):
        """Should detect entity kind from frontmatter."""
        content = FIXTURE_PATH.read_text()
        detector = DocumentKindDetector()

        result = detector.detect(content, "Usuario.md")

        assert result.kind == KDDDocumentKind.ENTITY
        assert result.confidence == 1.0
        assert result.detected_from == "frontmatter"

    def test_detect_unknown_without_frontmatter(self):
        """Should return unknown when no frontmatter kind is present."""
        content = "# Some Entity\n\nDescription here."
        detector = DocumentKindDetector()

        result = detector.detect(content, "Product.md")

        assert result.kind == KDDDocumentKind.UNKNOWN


class TestEntityParser:
    """Tests for entity document parsing."""

    def test_parse_entity_document(self):
        """Should parse entity document structure."""
        content = FIXTURE_PATH.read_text()
        parser = EntityParser()

        parsed = parser.parse(content, "Usuario.md")

        assert parsed.kind == KDDDocumentKind.ENTITY
        assert parsed.title == "Usuario"
        assert parsed.entity_name == "Usuario"
        assert "User" in parsed.aliases
        assert parsed.code_class == "User"
        assert parsed.code_table == "users"

    def test_extract_entity_info(self):
        """Should extract entity info from parsed document."""
        content = FIXTURE_PATH.read_text()
        parser = EntityParser()

        parsed = parser.parse(content, "Usuario.md")
        entity_info = parser.extract_entity_info(parsed)

        # Check attributes
        assert len(entity_info.attributes) >= 8
        attr_names = [a.name for a in entity_info.attributes]
        assert "id" in attr_names
        assert "email" in attr_names

        # Check relations
        assert len(entity_info.relations) >= 4

        # Check states
        assert len(entity_info.states) >= 5

        # Check events
        assert len(entity_info.events_emitted) >= 5


class TestFalkorDBGraphStore:
    """Tests for FalkorDB graph store."""

    def test_initialize_and_upsert(self):
        """Should initialize store and upsert entities."""
        store = FalkorDBGraphStore(TEST_GRAPH_PATH)
        store.initialize()

        # Upsert entity
        store.upsert_entity(
            entity_id="entity:Test",
            name="Test",
            description="Test entity",
            code_class="Test",
        )

        # Query
        results = store.execute_cypher(
            "MATCH (e:Entity {name: 'Test'}) RETURN e.name as name"
        )

        assert len(results) == 1
        assert results[0]["name"] == "Test"

        store.close()

    def test_relationships(self):
        """Should create and query relationships."""
        store = FalkorDBGraphStore(TEST_GRAPH_PATH)
        store.initialize()

        # Create entities
        store.upsert_entity("entity:A", "EntityA", "First entity")
        store.upsert_concept("concept:A.attr", "attr", "attribute", "An attribute", "EntityA")

        # Create relationship
        store.add_contains("entity:A", "concept:A.attr")

        # Query relationship
        results = store.execute_cypher("""
            MATCH (e:Entity)-[:CONTAINS]->(c:Concept)
            RETURN e.name as entity, c.name as concept
        """)

        assert len(results) == 1
        assert results[0]["entity"] == "EntityA"
        assert results[0]["concept"] == "attr"

        store.close()


class TestEntityIngestionPipeline:
    """Integration tests for the full pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_entity_document_skip_graph(self):
        """Should ingest entity document without storing to graph."""
        content = FIXTURE_PATH.read_text()

        pipeline = EntityIngestionPipeline(
            graph_path=TEST_GRAPH_PATH,
            use_mock_summarizer=True,
        )

        result = await pipeline.ingest(content, filename="Usuario.md", skip_graph=True)

        assert result.success
        assert result.document_kind == KDDDocumentKind.ENTITY
        assert result.document_id == "Usuario"
        assert result.chunks_created > 0
        assert result.entities_extracted > 0
        assert result.relations_created > 0
        assert len(result.validation_errors) == 0

    @pytest.mark.asyncio
    async def test_ingest_entity_document_with_graph(self):
        """Should ingest entity document and store to FalkorDB graph."""
        content = FIXTURE_PATH.read_text()

        pipeline = EntityIngestionPipeline(
            graph_path=TEST_GRAPH_PATH,
            use_mock_summarizer=True,
        )

        result = await pipeline.ingest(content, filename="Usuario.md", skip_graph=False)

        assert result.success
        assert result.entities_extracted > 0
        assert result.relations_created > 0

        # Verify data in graph
        stats = pipeline.get_graph_stats()
        assert stats["entity_count"] > 0

        # Query the graph
        entities = pipeline.query_graph(
            "MATCH (e:Entity {name: 'Usuario'}) RETURN e.name as name"
        )
        assert len(entities) == 1
        assert entities[0]["name"] == "Usuario"

        # Query relationships (CONTAINS)
        relations = pipeline.query_graph("""
            MATCH (e:Entity {name: 'Usuario'})-[:CONTAINS]->(c:Concept)
            RETURN c.name as concept, c.concept_type as ctype
        """)
        assert len(relations) > 0

        pipeline.close()

    @pytest.mark.asyncio
    async def test_reject_non_entity_document(self):
        """Should reject non-entity documents."""
        content = """---
kind: use-case
---

# Login de Usuario

## Resumen

El usuario inicia sesión.
"""
        pipeline = EntityIngestionPipeline(
            graph_path=TEST_GRAPH_PATH,
            use_mock_summarizer=True,
        )

        result = await pipeline.ingest(content, filename="UC-Login.md", skip_graph=True)

        assert not result.success
        assert "Expected entity document" in result.validation_errors[0]


class TestGraphProvenance:
    """Tests for graph-native provenance with Document nodes and EXTRACTED_FROM edges."""

    def test_provenance_extracted_from_edges(self):
        """Indexing a document should create EXTRACTED_FROM edges to a Document node."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        # Create a document and entity with provenance
        store.upsert_document("doc-1", "User", "entities/User.md", "entity")
        store.upsert_entity("entity:User", "User", "Domain user", confidence=1.0)
        store.add_extracted_from("entity:User", "Entity", "doc-1", "primary", 1.0)

        # Verify Document node
        docs = store.execute_cypher("MATCH (d:Document) RETURN d.id as id, d.title as title")
        assert len(docs) == 1
        assert docs[0]["id"] == "doc-1"

        # Verify EXTRACTED_FROM edge
        edges = store.execute_cypher("""
            MATCH (n:Entity)-[r:EXTRACTED_FROM]->(d:Document)
            RETURN n.name as name, r.role as role, d.id as doc_id
        """)
        assert len(edges) == 1
        assert edges[0]["name"] == "User"
        assert edges[0]["role"] == "primary"
        assert edges[0]["doc_id"] == "doc-1"

        store.close()

    def test_multi_document_provenance(self):
        """Two documents sharing an entity should both have EXTRACTED_FROM edges."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        # Doc A defines Entity X, references Entity Y
        store.upsert_document("doc-A", "Entity X", "x.md", "entity")
        store.upsert_entity("entity:X", "X", "Main entity X", confidence=1.0)
        store.add_extracted_from("entity:X", "Entity", "doc-A", "primary", 1.0)
        store.upsert_entity("entity:Y", "Y", "Referenced by X", confidence=0.7)
        store.add_extracted_from("entity:Y", "Entity", "doc-A", "referenced", 0.7)

        # Doc B defines Entity Y, references Entity X
        store.upsert_document("doc-B", "Entity Y", "y.md", "entity")
        store.upsert_entity("entity:Y", "Y", "Main entity Y", confidence=1.0)
        store.add_extracted_from("entity:Y", "Entity", "doc-B", "primary", 1.0)
        store.upsert_entity("entity:X", "X", "Referenced by Y", confidence=0.7)
        store.add_extracted_from("entity:X", "Entity", "doc-B", "referenced", 0.7)

        # Entity X should have EXTRACTED_FROM edges to both documents
        x_provenance = store.get_node_provenance("entity:X")
        assert len(x_provenance) == 2
        x_doc_ids = {p["doc_id"] for p in x_provenance}
        assert x_doc_ids == {"doc-A", "doc-B"}

        # Entity Y should have EXTRACTED_FROM edges to both documents
        y_provenance = store.get_node_provenance("entity:Y")
        assert len(y_provenance) == 2
        y_doc_ids = {p["doc_id"] for p in y_provenance}
        assert y_doc_ids == {"doc-A", "doc-B"}

        store.close()

    def test_delete_preserves_shared_entities(self):
        """Deleting one document should preserve entities shared with another."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        # Two docs both contribute to entity:Shared
        store.upsert_document("doc-1", "Doc 1", "d1.md", "entity")
        store.upsert_document("doc-2", "Doc 2", "d2.md", "entity")

        store.upsert_entity("entity:Shared", "Shared", "Shared entity", confidence=1.0)
        store.add_extracted_from("entity:Shared", "Entity", "doc-1", "primary", 1.0)
        store.add_extracted_from("entity:Shared", "Entity", "doc-2", "primary", 1.0)

        store.upsert_entity("entity:OnlyDoc1", "OnlyDoc1", "Only in doc 1", confidence=1.0)
        store.add_extracted_from("entity:OnlyDoc1", "Entity", "doc-1", "primary", 1.0)

        # Add domain relationship with source_doc_id for doc-1
        store.upsert_concept("concept:attr1", "attr1", "attribute", "An attr", "Shared")
        store.add_extracted_from("concept:attr1", "Concept", "doc-1", "primary", 0.95)
        store.add_contains("entity:Shared", "concept:attr1", source_doc_id="doc-1")

        # Delete doc-1
        store.delete_by_source_doc("doc-1")

        # entity:Shared should survive (still has EXTRACTED_FROM to doc-2)
        shared = store.get_entity("entity:Shared")
        assert shared is not None

        # entity:OnlyDoc1 should be deleted (orphan)
        only1 = store.get_entity("entity:OnlyDoc1")
        assert only1 is None

        # concept:attr1 should be deleted (orphan, no EXTRACTED_FROM left)
        concepts = store.execute_cypher(
            "MATCH (c:Concept {id: 'concept:attr1'}) RETURN c"
        )
        assert len(concepts) == 0

        # doc-1 Document node should be gone
        d1 = store.execute_cypher("MATCH (d:Document {id: 'doc-1'}) RETURN d")
        assert len(d1) == 0

        # doc-2 Document node should survive
        d2 = store.execute_cypher("MATCH (d:Document {id: 'doc-2'}) RETURN d")
        assert len(d2) == 1

        store.close()

    def test_confidence_guard(self):
        """Upserting with lower confidence should not overwrite higher-confidence data."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        # First upsert with high confidence
        store.upsert_entity(
            "entity:Guarded", "Guarded", "Full description", confidence=1.0
        )

        # Second upsert with lower confidence
        store.upsert_entity(
            "entity:Guarded", "GuardedOverwritten", "Stub description", confidence=0.7
        )

        # Should retain the higher-confidence values
        result = store.execute_cypher(
            "MATCH (e:Entity {id: 'entity:Guarded'}) RETURN e.name as name, e.description as descr, e.confidence as conf"
        )
        assert len(result) == 1
        assert result[0]["name"] == "Guarded"
        assert result[0]["descr"] == "Full description"
        assert result[0]["conf"] == 1.0

        store.close()

    def test_confidence_guard_allows_equal_or_higher(self):
        """Upserting with equal or higher confidence should overwrite."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        store.upsert_entity("entity:G", "Original", "Original desc", confidence=0.7)
        store.upsert_entity("entity:G", "Updated", "Updated desc", confidence=1.0)

        result = store.execute_cypher(
            "MATCH (e:Entity {id: 'entity:G'}) RETURN e.name as name, e.confidence as conf"
        )
        assert result[0]["name"] == "Updated"
        assert result[0]["conf"] == 1.0

        store.close()

    def test_get_document_impact(self):
        """get_document_impact should return all nodes extracted from a document."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        store.upsert_document("doc-impact", "Impact Doc", "impact.md", "entity")
        store.upsert_entity("entity:A", "A", "Entity A", confidence=1.0)
        store.add_extracted_from("entity:A", "Entity", "doc-impact", "primary", 1.0)
        store.upsert_concept("concept:A.x", "x", "attribute", "attr x", confidence=0.95)
        store.add_extracted_from("concept:A.x", "Concept", "doc-impact", "primary", 0.95)
        store.upsert_event("event:ACreated", "ACreated", "A created", confidence=0.9)
        store.add_extracted_from("event:ACreated", "Event", "doc-impact", "primary", 0.9)

        impact = store.get_document_impact("doc-impact")
        assert len(impact) == 3
        node_types = {i["node_type"] for i in impact}
        assert node_types == {"Entity", "Concept", "Event"}

        store.close()

    def test_get_node_provenance(self):
        """get_node_provenance should return all documents that contributed to a node."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        store.upsert_document("doc-p1", "Doc P1", "p1.md", "entity")
        store.upsert_document("doc-p2", "Doc P2", "p2.md", "entity")

        store.upsert_entity("entity:Multi", "Multi", "Multi-source", confidence=1.0)
        store.add_extracted_from("entity:Multi", "Entity", "doc-p1", "primary", 1.0)
        store.add_extracted_from("entity:Multi", "Entity", "doc-p2", "referenced", 0.7)

        provenance = store.get_node_provenance("entity:Multi")
        assert len(provenance) == 2
        roles = {p["role"] for p in provenance}
        assert roles == {"primary", "referenced"}
        doc_ids = {p["doc_id"] for p in provenance}
        assert doc_ids == {"doc-p1", "doc-p2"}

        store.close()

    def test_get_stats_includes_document_count(self):
        """get_stats should include document_count."""
        store = FalkorDBGraphStore(TEST_PROVENANCE_GRAPH_PATH)
        store.initialize(reset=True)

        store.upsert_document("doc-s1", "Stats Doc", "s1.md", "entity")
        store.upsert_entity("entity:S", "S", "Stats entity", confidence=1.0)

        stats = store.get_stats()
        assert "document_count" in stats
        assert stats["document_count"] == 1
        assert stats["entity_count"] == 1

        store.close()

    @pytest.mark.asyncio
    async def test_full_pipeline_creates_provenance(self):
        """Full pipeline ingestion should create Document + EXTRACTED_FROM edges."""
        content = FIXTURE_PATH.read_text()

        pipeline = EntityIngestionPipeline(
            graph_path=TEST_PROVENANCE_GRAPH_PATH,
            use_mock_summarizer=True,
        )

        result = await pipeline.ingest(content, filename="Usuario.md", skip_graph=False)
        assert result.success

        # Should have a Document node
        stats = pipeline.get_graph_stats()
        assert stats["document_count"] >= 1

        # Should have EXTRACTED_FROM edges
        edges = pipeline.query_graph("""
            MATCH (n)-[r:EXTRACTED_FROM]->(d:Document)
            RETURN count(r) as cnt
        """)
        assert edges[0]["cnt"] > 0

        # Main entity should have provenance to the document
        provenance = pipeline.query_graph("""
            MATCH (e:Entity {name: 'Usuario'})-[r:EXTRACTED_FROM]->(d:Document)
            RETURN d.id as doc_id, r.role as role
        """)
        assert len(provenance) == 1
        assert provenance[0]["role"] == "primary"

        pipeline.close()


# Quick manual test
async def main():
    """Run a quick test of the pipeline."""
    print("=" * 60)
    print("Testing Smart Pipeline with FalkorDB")
    print("=" * 60)

    # Clean up
    if TEST_GRAPH_PATH.exists():
        TEST_GRAPH_PATH.unlink()

    content = FIXTURE_PATH.read_text()
    print(f"\nLoaded: {FIXTURE_PATH.name} ({len(content)} chars)")

    # Create pipeline
    pipeline = EntityIngestionPipeline(
        graph_path=TEST_GRAPH_PATH,
        use_mock_summarizer=True,
    )

    # Ingest with graph storage
    print("\nIngesting document...")
    result = await pipeline.ingest(content, filename="Usuario.md", skip_graph=False)

    print(f"\nResult:")
    print(f"  - Success: {result.success}")
    print(f"  - Document ID: {result.document_id}")
    print(f"  - Chunks created: {result.chunks_created}")
    print(f"  - Entities extracted: {result.entities_extracted}")
    print(f"  - Relations created: {result.relations_created}")
    print(f"  - Processing time: {result.processing_time_ms:.2f}ms")

    # Query graph
    print("\n" + "-" * 60)
    print("Querying FalkorDB Graph")
    print("-" * 60)

    print("\nEntities:")
    entities = pipeline.query_graph("MATCH (e:Entity) RETURN e.name as name, e.code_class as code")
    for e in entities:
        print(f"  - {e['name']} ({e['code']})")

    print("\nRelationships from Usuario:")
    # Query each relationship type
    for rel_type in ["CONTAINS", "REFERENCES", "PRODUCES", "CONSUMES"]:
        rels = pipeline.query_graph(f"""
            MATCH (e:Entity {{name: 'Usuario'}})-[r:{rel_type}]->(n)
            RETURN label(n) as target_type, n.name as target_name
            LIMIT 5
        """)
        for r in rels:
            print(f"  - {rel_type} -> {r['target_type']}:{r['target_name']}")

    print("\nGraph stats:")
    stats = pipeline.get_graph_stats()
    for key, value in stats.items():
        print(f"  - {key}: {value}")

    pipeline.close()

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
