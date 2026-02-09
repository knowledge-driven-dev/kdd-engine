"""Main indexation pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from kb_engine.chunking import ChunkerFactory, ChunkingConfig
from kb_engine.core.exceptions import PipelineError
from kb_engine.core.models.document import Document, DocumentStatus
from kb_engine.core.models.repository import (
    EXTENSION_DEFAULTS,
    FileTypeConfig,
    RepositoryConfig,
)
from kb_engine.embedding import EmbeddingConfig, EmbeddingProviderFactory
from kb_engine.extraction import ExtractionConfig, ExtractionPipelineFactory
from kb_engine.git.scanner import GitRepoScanner
from kb_engine.git.url_resolver import URLResolver
from kb_engine.utils.hashing import compute_content_hash
from kb_engine.utils.markdown import extract_frontmatter, heading_path_to_anchor

if TYPE_CHECKING:
    from kb_engine.extraction.strategies import GraphExtractionStrategy

logger = structlog.get_logger(__name__)


class IndexationPipeline:
    """Pipeline for indexing documents into the knowledge base.

    Orchestrates the full indexation process:
    1. Parse and validate document
    2. Chunk content using semantic strategies
    3. Compute section anchors for each chunk
    4. Generate embeddings
    5. Extract entities and relationships (optional)
    6. Store in all repositories
    """

    def __init__(
        self,
        traceability_repo,
        vector_repo,
        graph_repo=None,
        graph_strategy: GraphExtractionStrategy | None = None,
        url_resolver: URLResolver | None = None,
        chunking_config: ChunkingConfig | None = None,
        embedding_config: EmbeddingConfig | None = None,
        extraction_config: ExtractionConfig | None = None,
    ) -> None:
        self._traceability = traceability_repo
        self._vector = vector_repo
        self._url_resolver = url_resolver

        # Initialize components
        self._chunker = ChunkerFactory(chunking_config)
        self._embedding_provider = EmbeddingProviderFactory(embedding_config).create_provider()
        self._extraction_pipeline = ExtractionPipelineFactory(extraction_config).create_pipeline()

        # Graph strategy: explicit strategy > legacy wrapper around graph_repo > None
        if graph_strategy is not None:
            self._graph_strategy = graph_strategy
        elif graph_repo is not None:
            from kb_engine.extraction.strategies import LegacyGraphExtractionStrategy

            self._graph_strategy = LegacyGraphExtractionStrategy(
                graph_repo, self._extraction_pipeline
            )
        else:
            self._graph_strategy = None

    async def index_document(self, document: Document) -> Document:
        """Index a document through the full pipeline."""
        try:
            document.status = DocumentStatus.PROCESSING
            document.content_hash = compute_content_hash(document.content)

            # 1. Save document to traceability store
            logger.debug("Step 1/8: saving document", title=document.title)
            document = await self._traceability.save_document(document)

            # 2. Chunk the document
            logger.debug("Step 2/8: chunking document", title=document.title)
            parser = document.metadata.get("_parser", "markdown")
            chunks = self._chunker.chunk_document(document, parser=parser)

            # 3. Compute section anchors from heading paths
            logger.debug("Step 3/8: computing anchors", chunks=len(chunks))
            for chunk in chunks:
                chunk.section_anchor = heading_path_to_anchor(chunk.heading_path)

            # 4. Save chunks to traceability store
            logger.debug("Step 4/8: saving chunks", chunks=len(chunks))
            chunks = await self._traceability.save_chunks(chunks)

            # 5. Generate embeddings
            logger.debug("Step 5/8: generating embeddings", chunks=len(chunks))
            embeddings = await self._embedding_provider.embed_chunks(chunks)

            # 6. Store embeddings in vector store
            logger.debug("Step 6/8: storing embeddings", count=len(embeddings))
            await self._vector.upsert_embeddings(embeddings)

            # 7. Extract entities and store in graph (if strategy available)
            if self._graph_strategy is not None:
                logger.debug("Step 7/8: extracting entities", title=document.title)
                graph_result = await self._graph_strategy.extract_and_store(
                    document, chunks
                )
                logger.debug(
                    "Step 7/8: entities extracted",
                    nodes=graph_result.nodes_created,
                    edges=graph_result.edges_created,
                )

            # 8. Update document status
            logger.debug("Step 8/8: updating status", title=document.title)
            document.status = DocumentStatus.INDEXED
            document.indexed_at = datetime.utcnow()
            document = await self._traceability.update_document(document)

            logger.info(
                "Document indexed",
                document_id=str(document.id),
                title=document.title,
                chunks=len(chunks),
            )
            return document

        except Exception as e:
            document.status = DocumentStatus.FAILED
            try:
                await self._traceability.update_document(document)
            except Exception:
                pass
            raise PipelineError(
                f"Failed to index document: {e}",
                details={"document_id": str(document.id)},
            ) from e

    async def reindex_document(self, document: Document) -> Document:
        """Reindex an existing document."""
        await self._vector.delete_by_document(document.id)
        if self._graph_strategy is not None:
            await self._graph_strategy.delete_by_document(str(document.id))
        await self._traceability.delete_chunks_by_document(document.id)
        return await self.index_document(document)

    async def delete_document(self, document: Document) -> bool:
        """Delete a document and all its indexed data."""
        await self._vector.delete_by_document(document.id)
        if self._graph_strategy is not None:
            await self._graph_strategy.delete_by_document(str(document.id))
        await self._traceability.delete_chunks_by_document(document.id)
        return await self._traceability.delete_document(document.id)

    @staticmethod
    def _resolve_file_type_config(
        repo_config: RepositoryConfig, relative_path: str
    ) -> FileTypeConfig:
        """Resolve the FileTypeConfig for a file based on its extension."""
        ext = Path(relative_path).suffix.lower()
        if ext in repo_config.file_type_config:
            return repo_config.file_type_config[ext]
        if ext in EXTENSION_DEFAULTS:
            return EXTENSION_DEFAULTS[ext]
        return FileTypeConfig(parser="plaintext", mime_type="text/plain")

    def _build_document(
        self,
        scanner: GitRepoScanner,
        repo_config: RepositoryConfig,
        relative_path: str,
        commit: str,
        remote_url: str | None,
        existing_id=None,
        content: str | None = None,
    ) -> Document:
        """Build a Document from a repository file with file-type-aware parsing."""
        if content is None:
            content = scanner.read_file(relative_path)
        title = Path(relative_path).stem
        ft_config = self._resolve_file_type_config(repo_config, relative_path)

        if ft_config.parser == "markdown":
            frontmatter, body = extract_frontmatter(content)
        else:
            frontmatter = {}

        metadata = {**frontmatter, "_parser": ft_config.parser}

        kwargs: dict = dict(
            title=frontmatter.get("title", title),
            content=content,
            source_path=str(scanner.repo_path / relative_path),
            external_id=f"{repo_config.name}:{relative_path}",
            domain=frontmatter.get("domain"),
            tags=frontmatter.get("tags", []),
            metadata=metadata,
            mime_type=ft_config.mime_type,
            repo_name=repo_config.name,
            relative_path=relative_path,
            git_commit=commit,
            git_remote_url=remote_url,
        )
        if existing_id is not None:
            kwargs["id"] = existing_id
        return Document(**kwargs)

    async def index_repository(self, repo_config: RepositoryConfig) -> list[Document]:
        """Index all matching files from a Git repository."""
        scanner = GitRepoScanner(repo_config)
        if not scanner.is_git_repo():
            raise PipelineError(f"Not a git repository: {repo_config.local_path}")

        resolver = self._url_resolver or URLResolver(repo_config)
        commit = scanner.get_current_commit()
        remote_url = scanner.get_remote_url()
        files = scanner.scan_files()

        logger.info(
            "Indexing repository",
            repo=repo_config.name,
            files=len(files),
            commit=commit[:8],
        )

        documents = []
        for relative_path in files:
            try:
                doc = self._build_document(
                    scanner, repo_config, relative_path, commit, remote_url
                )
                doc = await self.index_document(doc)
                documents.append(doc)
            except Exception as e:
                logger.error(
                    "Failed to index file",
                    path=relative_path,
                    error=str(e),
                )

        return documents

    async def sync_repository(self, repo_config: RepositoryConfig, since_commit: str) -> dict:
        """Incrementally sync a repository since a given commit.

        Returns a summary dict with indexed, deleted, and skipped counts.
        """
        scanner = GitRepoScanner(repo_config)
        resolver = self._url_resolver or URLResolver(repo_config)
        current_commit = scanner.get_current_commit()
        remote_url = scanner.get_remote_url()

        changed_files = scanner.get_changed_files(since_commit)
        deleted_files = scanner.get_deleted_files(since_commit)

        logger.info(
            "Syncing repository",
            repo=repo_config.name,
            changed=len(changed_files),
            deleted=len(deleted_files),
            since=since_commit[:8],
        )

        indexed = 0
        skipped = 0

        # Delete removed files
        for relative_path in deleted_files:
            external_id = f"{repo_config.name}:{relative_path}"
            existing = await self._traceability.get_document_by_external_id(external_id)
            if existing:
                await self.delete_document(existing)

        # Reindex changed files
        for relative_path in changed_files:
            try:
                content = scanner.read_file(relative_path)
                content_hash = compute_content_hash(content)

                external_id = f"{repo_config.name}:{relative_path}"
                existing = await self._traceability.get_document_by_external_id(external_id)

                if existing and existing.content_hash == content_hash:
                    skipped += 1
                    continue

                doc = self._build_document(
                    scanner,
                    repo_config,
                    relative_path,
                    current_commit,
                    remote_url,
                    existing_id=existing.id if existing else None,
                    content=content,
                )

                if existing:
                    await self.reindex_document(doc)
                else:
                    await self.index_document(doc)
                indexed += 1
            except Exception as e:
                logger.error(
                    "Failed to sync file",
                    path=relative_path,
                    error=str(e),
                )

        return {
            "commit": current_commit,
            "indexed": indexed,
            "deleted": len(deleted_files),
            "skipped": skipped,
        }
