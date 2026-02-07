"""Factory for creating and managing chunking strategies."""

from kb_engine.chunking.base import BaseChunkingStrategy
from kb_engine.chunking.config import ChunkingConfig
from kb_engine.chunking.parsers import get_parser
from kb_engine.chunking.strategies.default import DefaultChunkingStrategy
from kb_engine.chunking.strategies.entity import EntityChunkingStrategy
from kb_engine.chunking.strategies.process import ProcessChunkingStrategy
from kb_engine.chunking.strategies.rule import RuleChunkingStrategy
from kb_engine.chunking.strategies.use_case import UseCaseChunkingStrategy
from kb_engine.core.models.document import Chunk, ChunkType, Document


class ChunkerFactory:
    """Factory for creating and orchestrating chunking strategies.

    The factory maintains a registry of strategies and selects
    the appropriate one based on content analysis.
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config = config or ChunkingConfig()
        self._strategies: list[BaseChunkingStrategy] = []
        self._default_strategy: BaseChunkingStrategy | None = None
        self._initialize_strategies()

    def _initialize_strategies(self) -> None:
        """Initialize the default set of strategies."""
        self._strategies = [
            EntityChunkingStrategy(self._config),
            UseCaseChunkingStrategy(self._config),
            RuleChunkingStrategy(self._config),
            ProcessChunkingStrategy(self._config),
        ]
        self._default_strategy = DefaultChunkingStrategy(self._config)

    def register_strategy(self, strategy: BaseChunkingStrategy) -> None:
        """Register a custom chunking strategy."""
        self._strategies.append(strategy)

    def get_strategy_for_content(
        self,
        document: Document,
        content: str,
    ) -> BaseChunkingStrategy:
        """Select the appropriate strategy for the given content.

        Iterates through registered strategies and returns the first
        one that can handle the content, or the default strategy.
        """
        if self._config.enable_semantic_chunking:
            for strategy in self._strategies:
                if strategy.can_handle(document, content):
                    return strategy

        return self._default_strategy or DefaultChunkingStrategy(self._config)

    def chunk_document(self, document: Document, parser: str = "markdown") -> list[Chunk]:
        """Chunk an entire document.

        Parses the document structure using the specified parser and
        applies appropriate strategies to each section.
        """
        all_chunks: list[Chunk] = []
        parse_fn = get_parser(parser)
        sections = parse_fn(document.content)

        sequence = 0
        for heading_path, content in sections:
            strategy = self.get_strategy_for_content(document, content)
            chunks = strategy.chunk(document, content, heading_path)

            # Update sequence numbers
            for chunk in chunks:
                chunk.sequence = sequence
                sequence += 1

            all_chunks.extend(chunks)

        return all_chunks

    def get_available_chunk_types(self) -> list[ChunkType]:
        """Get list of chunk types supported by registered strategies."""
        types = [s.chunk_type for s in self._strategies]
        if self._default_strategy:
            types.append(self._default_strategy.chunk_type)
        return list(set(types))
