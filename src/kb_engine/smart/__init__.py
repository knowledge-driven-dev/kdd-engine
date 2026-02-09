"""Smart Ingestion Pipeline for KDD documents.

This module provides intelligent document processing with:
- Template-aware parsing based on document kind
- Hierarchical chunking with LLM-generated summaries
- FalkorDB graph store for knowledge graph
- ChromaDB for vector embeddings (TODO)
- SQLite for metadata and traceability (TODO)
"""

from kb_engine.smart.chunking import HierarchicalChunker, LLMSummaryService, MockSummaryService
from kb_engine.smart.extraction import EntityGraphExtractor
from kb_engine.smart.parsers import DocumentKindDetector, EntityParser
from kb_engine.smart.pipelines import EntityIngestionPipeline
from kb_engine.smart.schemas import ENTITY_SCHEMA
from kb_engine.smart.stores import FalkorDBGraphStore
from kb_engine.smart.types import (
    ContextualizedChunk,
    ExtractedEntityInfo,
    IngestionResult,
    KDDDocumentKind,
    ParsedDocument,
)

__all__ = [
    # Types
    "KDDDocumentKind",
    "ParsedDocument",
    "ContextualizedChunk",
    "ExtractedEntityInfo",
    "IngestionResult",
    # Schemas
    "ENTITY_SCHEMA",
    # Parsers
    "DocumentKindDetector",
    "EntityParser",
    # Chunking
    "HierarchicalChunker",
    "LLMSummaryService",
    "MockSummaryService",
    # Stores
    "FalkorDBGraphStore",
    # Extraction
    "EntityGraphExtractor",
    # Pipelines
    "EntityIngestionPipeline",
]
