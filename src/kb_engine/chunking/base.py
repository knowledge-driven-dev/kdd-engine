"""Base chunking strategy implementation."""

from abc import ABC, abstractmethod

from kb_engine.chunking.config import ChunkingConfig
from kb_engine.core.interfaces.chunkers import ChunkingStrategy
from kb_engine.core.models.document import Chunk, ChunkType, Document


class BaseChunkingStrategy(ChunkingStrategy, ABC):
    """Base class for chunking strategies.

    Provides common functionality for all chunking strategies.
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config = config or ChunkingConfig()

    @property
    @abstractmethod
    def chunk_type(self) -> ChunkType:
        """The type of chunks this strategy produces."""
        ...

    @abstractmethod
    def can_handle(self, document: Document, section_content: str) -> bool:
        """Check if this strategy can handle the given content."""
        ...

    @abstractmethod
    def chunk(
        self,
        document: Document,
        content: str,
        heading_path: list[str] | None = None,
    ) -> list[Chunk]:
        """Chunk the content into semantic units."""
        ...

    def _create_chunk(
        self,
        document: Document,
        content: str,
        sequence: int,
        heading_path: list[str] | None = None,
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> Chunk:
        """Create a chunk with standard metadata."""
        return Chunk(
            document_id=document.id,
            content=content,
            chunk_type=self.chunk_type,
            sequence=sequence,
            heading_path=heading_path or [],
            start_offset=start_offset,
            end_offset=end_offset,
            metadata={
                "domain": document.domain,
                "source_path": document.source_path,
            },
        )

    def _split_by_size(
        self,
        text: str,
        max_size: int | None = None,
    ) -> list[str]:
        """Split text into chunks respecting size limits.

        This is a simple character-based split. Subclasses may
        override with token-based splitting.
        """
        max_size = max_size or self._config.max_chunk_size
        if len(text) <= max_size:
            return [text]

        chunks = []
        current_pos = 0
        overlap = self._config.overlap_size

        while current_pos < len(text):
            end_pos = min(current_pos + max_size, len(text))

            if end_pos < len(text) and self._config.preserve_sentences:
                # Only accept sentence breaks that leave room to advance past overlap
                search_start = current_pos + overlap + 1
                for sep in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                    last_sep = text.rfind(sep, search_start, end_pos)
                    if last_sep > current_pos:
                        end_pos = last_sep + len(sep)
                        break

            chunks.append(text[current_pos:end_pos].strip())

            if end_pos >= len(text):
                break
            current_pos = end_pos - overlap

        return [c for c in chunks if c]
