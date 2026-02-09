"""CLI for KB-Engine local mode."""

import asyncio
import sys
from pathlib import Path

import click
import structlog

from kb_engine.config.logging import configure_logging

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run an async function synchronously."""
    return asyncio.run(coro)


async def _create_services(settings=None):
    """Create indexing and retrieval services."""
    from kb_engine.config.settings import Settings, get_settings
    from kb_engine.embedding.config import EmbeddingConfig
    from kb_engine.pipelines.indexation.pipeline import IndexationPipeline
    from kb_engine.pipelines.inference.pipeline import RetrievalPipeline
    from kb_engine.repositories.factory import RepositoryFactory
    from kb_engine.services.indexing import IndexingService
    from kb_engine.services.retrieval import RetrievalService

    if settings is None:
        settings = get_settings()

    factory = RepositoryFactory(settings)
    traceability = await factory.get_traceability_repository()
    vector = await factory.get_vector_repository()
    graph_strategy = await factory.get_graph_strategy()
    graph = await factory.get_graph_repository()

    embedding_config = EmbeddingConfig(
        provider=settings.embedding_provider,
        local_model_name=settings.local_embedding_model,
        openai_model=settings.openai_embedding_model,
    )

    indexing_pipeline = IndexationPipeline(
        traceability_repo=traceability,
        vector_repo=vector,
        graph_strategy=graph_strategy,
        embedding_config=embedding_config,
    )
    retrieval_pipeline = RetrievalPipeline(
        traceability_repo=traceability,
        vector_repo=vector,
        graph_repo=graph,
        embedding_config=embedding_config,
    )

    return (
        IndexingService(pipeline=indexing_pipeline),
        RetrievalService(pipeline=retrieval_pipeline),
        factory,
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """KB-Engine: Intelligent document retrieval system."""
    log_level = "DEBUG" if verbose else "INFO"
    configure_logging(log_level=log_level)


@cli.command()
@click.argument("repo_path", default=".")
@click.option("--name", "-n", help="Repository name (default: directory name)")
@click.option("--pattern", "-p", multiple=True, default=["**/*.md"], help="Include glob patterns")
@click.option("--exclude", "-e", multiple=True, help="Exclude glob patterns")
def index(repo_path: str, name: str | None, pattern: tuple[str, ...], exclude: tuple[str, ...]) -> None:
    """Index a Git repository.

    Scans the repository for matching files and indexes them.
    """
    repo_path_obj = Path(repo_path).resolve()
    if not repo_path_obj.exists():
        click.echo(f"Error: Path does not exist: {repo_path_obj}", err=True)
        sys.exit(1)

    repo_name = name or repo_path_obj.name

    async def _index():
        from kb_engine.core.models.repository import RepositoryConfig

        config = RepositoryConfig(
            name=repo_name,
            local_path=str(repo_path_obj),
            include_patterns=list(pattern),
            exclude_patterns=list(exclude),
        )

        indexing_service, _, factory = await _create_services()
        try:
            click.echo(f"Indexing repository: {repo_name} ({repo_path_obj})")
            documents = await indexing_service.index_repository(config)
            click.echo(f"Indexed {len(documents)} documents")
            for doc in documents:
                click.echo(f"  - {doc.relative_path or doc.title}")
        finally:
            await factory.close()

    run_async(_index())


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=5, help="Max results")
@click.option("--threshold", "-t", type=float, default=None, help="Min score threshold")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON")
@click.option("--mode", "-m", type=click.Choice(["vector", "graph", "hybrid"]), default="vector", help="Retrieval mode")
def search(query: str, limit: int, threshold: float | None, output_json: bool, mode: str) -> None:
    """Search the knowledge base.

    Returns document references with URLs pointing to exact sections.
    """
    import json

    from kb_engine.core.models.search import RetrievalMode

    mode_map = {
        "vector": RetrievalMode.VECTOR,
        "graph": RetrievalMode.GRAPH,
        "hybrid": RetrievalMode.HYBRID,
    }

    async def _search():
        _, retrieval_service, factory = await _create_services()
        try:
            response = await retrieval_service.search(
                query=query,
                limit=limit,
                score_threshold=threshold,
                mode=mode_map[mode],
            )

            if output_json:
                # JSON output for agents
                output = {
                    "query": response.query,
                    "total_count": response.total_count,
                    "processing_time_ms": response.processing_time_ms,
                    "references": [
                        {
                            "url": ref.url,
                            "document_path": ref.document_path,
                            "title": ref.title,
                            "section_title": ref.section_title,
                            "section_anchor": ref.section_anchor,
                            "score": ref.score,
                            "snippet": ref.snippet,
                            "domain": ref.domain,
                            "tags": ref.tags,
                            "chunk_type": ref.chunk_type,
                            "retrieval_mode": ref.retrieval_mode.value,
                            "metadata": ref.metadata,
                        }
                        for ref in response.references
                    ],
                }
                click.echo(json.dumps(output, indent=2, ensure_ascii=False))
                return

            # Human-readable output
            if not response.references:
                click.echo("No results found.")
                return

            click.echo(f"Found {response.total_count} results ({response.processing_time_ms:.0f}ms):\n")
            for i, ref in enumerate(response.references, 1):
                mode_indicator = f"[{ref.retrieval_mode.value}]" if ref.retrieval_mode.value != "vector" else ""
                click.echo(f"  {i}. [{ref.score:.3f}] {mode_indicator} {ref.url}")
                if ref.title:
                    click.echo(f"     Title: {ref.title}")
                if ref.section_title:
                    click.echo(f"     Section: {ref.section_title}")
                if ref.snippet:
                    snippet = ref.snippet[:120] + "..." if len(ref.snippet) > 120 else ref.snippet
                    click.echo(f"     {snippet}")
                # Show graph relationships if present
                if ref.metadata.get("graph_relationships"):
                    rels = ref.metadata["graph_relationships"]
                    rel_strs = [f"{r['type']}→{r['related_node']}" for r in rels[:3]]
                    click.echo(f"     Relations: {', '.join(rel_strs)}")
                click.echo()
        finally:
            await factory.close()

    run_async(_search())


@cli.command()
@click.argument("repo_path", default=".")
@click.option("--name", "-n", help="Repository name (default: directory name)")
@click.option("--since", "-s", required=True, help="Commit hash to sync from")
@click.option("--pattern", "-p", multiple=True, default=["**/*.md"], help="Include glob patterns")
def sync(repo_path: str, name: str | None, since: str, pattern: tuple[str, ...]) -> None:
    """Sync a repository incrementally.

    Only re-indexes files that changed since the given commit.
    """
    repo_path_obj = Path(repo_path).resolve()
    repo_name = name or repo_path_obj.name

    async def _sync():
        from kb_engine.core.models.repository import RepositoryConfig

        config = RepositoryConfig(
            name=repo_name,
            local_path=str(repo_path_obj),
            include_patterns=list(pattern),
        )

        indexing_service, _, factory = await _create_services()
        try:
            click.echo(f"Syncing repository: {repo_name} (since {since[:8]}...)")
            result = await indexing_service.sync_repository(config, since)
            click.echo(
                f"Sync complete: {result['indexed']} indexed, "
                f"{result['deleted']} deleted, {result['skipped']} unchanged"
            )
            click.echo(f"Current commit: {result['commit'][:8]}")
        finally:
            await factory.close()

    run_async(_sync())


@cli.command()
def status() -> None:
    """Show the status of the local index."""
    async def _status():
        from kb_engine.config.settings import get_settings

        settings = get_settings()
        _, _, factory = await _create_services(settings)

        try:
            traceability = await factory.get_traceability_repository()
            vector = await factory.get_vector_repository()

            docs = await traceability.list_documents(limit=1000)
            vector_info = await vector.get_collection_info()

            click.echo("KB-Engine Status")
            click.echo(f"  Profile:    {settings.profile}")
            click.echo(f"  SQLite DB:  {settings.sqlite_path}")
            click.echo(f"  ChromaDB:   {settings.chroma_path}")
            click.echo(f"  Embedding:  {settings.embedding_provider} ({settings.local_embedding_model})")
            click.echo(f"  Documents:  {len(docs)}")
            click.echo(f"  Vectors:    {vector_info.get('count', 'N/A')}")

            if docs:
                click.echo("\nIndexed documents:")
                for doc in docs[:20]:
                    status_str = doc.status.value
                    path = doc.relative_path or doc.source_path or doc.title
                    click.echo(f"  [{status_str:>10}] {path}")
                if len(docs) > 20:
                    click.echo(f"  ... and {len(docs) - 20} more")
        finally:
            await factory.close()

    run_async(_status())


if __name__ == "__main__":
    cli()
