"""Semantic chunking module for KB-Engine (ADR-0002)."""

from kb_engine.chunking.base import BaseChunkingStrategy
from kb_engine.chunking.config import ChunkingConfig
from kb_engine.chunking.factory import ChunkerFactory
from kb_engine.chunking.parsers import get_parser
from kb_engine.chunking.types import ChunkType

__all__ = [
    "ChunkingConfig",
    "ChunkType",
    "BaseChunkingStrategy",
    "ChunkerFactory",
    "get_parser",
]
