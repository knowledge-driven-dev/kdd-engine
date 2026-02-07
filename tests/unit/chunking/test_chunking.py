"""Tests for chunking functionality."""

import pytest

from kb_engine.chunking import ChunkerFactory, ChunkingConfig
from kb_engine.chunking.strategies import (
    DefaultChunkingStrategy,
    EntityChunkingStrategy,
    RuleChunkingStrategy,
    UseCaseChunkingStrategy,
)
from kb_engine.core.models.document import ChunkType, Document


@pytest.mark.unit
class TestChunkingConfig:
    """Tests for ChunkingConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ChunkingConfig()

        assert config.min_chunk_size == 100
        assert config.target_chunk_size == 512
        assert config.max_chunk_size == 1024
        assert config.overlap_size == 50

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ChunkingConfig(
            min_chunk_size=50,
            target_chunk_size=256,
            max_chunk_size=512,
        )

        assert config.min_chunk_size == 50
        assert config.target_chunk_size == 256
        assert config.max_chunk_size == 512


@pytest.mark.unit
class TestEntityChunkingStrategy:
    """Tests for EntityChunkingStrategy."""

    def test_can_handle_entity_content(self) -> None:
        """Test detection of entity content."""
        strategy = EntityChunkingStrategy()
        doc = Document(title="Test", content="")

        entity_content = """
## Entity: User

A user represents an authenticated individual.

### Attributes
- **id**: Unique identifier
- **name**: Full name
- **email**: Email address
"""
        assert strategy.can_handle(doc, entity_content) is True

    def test_cannot_handle_non_entity_content(self) -> None:
        """Test rejection of non-entity content."""
        strategy = EntityChunkingStrategy()
        doc = Document(title="Test", content="")

        non_entity_content = "This is just regular text without entity patterns."
        assert strategy.can_handle(doc, non_entity_content) is False

    def test_chunk_type(self) -> None:
        """Test chunk type is ENTITY."""
        strategy = EntityChunkingStrategy()
        assert strategy.chunk_type == ChunkType.ENTITY


@pytest.mark.unit
class TestUseCaseChunkingStrategy:
    """Tests for UseCaseChunkingStrategy."""

    def test_can_handle_use_case_content(self) -> None:
        """Test detection of use case content."""
        strategy = UseCaseChunkingStrategy()
        doc = Document(title="Test", content="")

        use_case_content = """
## Use Case: Login

### Actors
- User

### Preconditions
- User has an account

### Main Flow
1. User enters credentials
2. System validates
"""
        assert strategy.can_handle(doc, use_case_content) is True

    def test_chunk_type(self) -> None:
        """Test chunk type is USE_CASE."""
        strategy = UseCaseChunkingStrategy()
        assert strategy.chunk_type == ChunkType.USE_CASE


@pytest.mark.unit
class TestRuleChunkingStrategy:
    """Tests for RuleChunkingStrategy."""

    def test_can_handle_rule_content(self) -> None:
        """Test detection of rule content."""
        strategy = RuleChunkingStrategy()
        doc = Document(title="Test", content="")

        rule_content = """
## Business Rules

### RN-001: Validation Rule
When a user submits a form, then all required fields must be filled.
"""
        assert strategy.can_handle(doc, rule_content) is True

    def test_chunk_type(self) -> None:
        """Test chunk type is RULE."""
        strategy = RuleChunkingStrategy()
        assert strategy.chunk_type == ChunkType.RULE


@pytest.mark.unit
class TestDefaultChunkingStrategy:
    """Tests for DefaultChunkingStrategy."""

    def test_can_handle_any_content(self) -> None:
        """Test that default strategy handles any content."""
        strategy = DefaultChunkingStrategy()
        doc = Document(title="Test", content="")

        assert strategy.can_handle(doc, "Any content") is True
        assert strategy.can_handle(doc, "") is True

    def test_chunk_type(self) -> None:
        """Test chunk type is DEFAULT."""
        strategy = DefaultChunkingStrategy()
        assert strategy.chunk_type == ChunkType.DEFAULT

    def test_chunk_small_content(self) -> None:
        """Test chunking small content."""
        strategy = DefaultChunkingStrategy()
        doc = Document(title="Test", content="Small content")

        chunks = strategy.chunk(doc, "Small content")

        assert len(chunks) == 1
        assert chunks[0].content == "Small content"
        assert chunks[0].chunk_type == ChunkType.DEFAULT


@pytest.mark.unit
class TestChunkerFactory:
    """Tests for ChunkerFactory."""

    def test_factory_initialization(self) -> None:
        """Test factory initializes with strategies."""
        factory = ChunkerFactory()

        types = factory.get_available_chunk_types()
        assert ChunkType.ENTITY in types
        assert ChunkType.USE_CASE in types
        assert ChunkType.RULE in types
        assert ChunkType.DEFAULT in types

    def test_strategy_selection_entity(self) -> None:
        """Test strategy selection for entity content."""
        factory = ChunkerFactory()
        doc = Document(title="Test", content="")

        entity_content = "## Entity: User\n\n- **id**: UUID"
        strategy = factory.get_strategy_for_content(doc, entity_content)

        assert strategy.chunk_type == ChunkType.ENTITY

    def test_strategy_selection_default(self) -> None:
        """Test fallback to default strategy."""
        factory = ChunkerFactory()
        doc = Document(title="Test", content="")

        generic_content = "Some generic text without special patterns."
        strategy = factory.get_strategy_for_content(doc, generic_content)

        assert strategy.chunk_type == ChunkType.DEFAULT

    def test_chunk_document(self, sample_document: Document) -> None:
        """Test chunking a full document."""
        factory = ChunkerFactory()

        chunks = factory.chunk_document(sample_document)

        assert len(chunks) > 0
        assert all(c.document_id == sample_document.id for c in chunks)
        # Verify sequences are unique
        sequences = [c.sequence for c in chunks]
        assert len(sequences) == len(set(sequences))

    def test_chunk_document_with_json_parser(self) -> None:
        """Test chunking a JSON document."""
        factory = ChunkerFactory()
        doc = Document(
            title="config",
            content='{"database": {"host": "localhost", "port": 5432}}',
        )

        chunks = factory.chunk_document(doc, parser="json")

        assert len(chunks) > 0
        assert all(c.document_id == doc.id for c in chunks)

    def test_chunk_document_with_plaintext_parser(self) -> None:
        """Test chunking a plain text document."""
        factory = ChunkerFactory()
        doc = Document(
            title="readme",
            content="First paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
        )

        chunks = factory.chunk_document(doc, parser="plaintext")

        assert len(chunks) == 3
        assert all(c.document_id == doc.id for c in chunks)
        sequences = [c.sequence for c in chunks]
        assert sequences == [0, 1, 2]
