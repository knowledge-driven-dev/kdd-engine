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
@click.option("--limit", "-l", default=10, help="Max results")
@click.option("--threshold", "-t", type=float, default=None, help="Min score threshold")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON")
@click.option("--mode", "-m", type=click.Choice(["vector", "graph", "hybrid"]), default="vector", help="Retrieval mode")
@click.option("--status", "-s", multiple=True, help="Include documents with these statuses (default: approved). Can repeat.")
@click.option("--include-all", is_flag=True, help="Include documents of all statuses")
def search(query: str, limit: int, threshold: float | None, output_json: bool, mode: str, status: tuple[str, ...], include_all: bool) -> None:
    """Search the knowledge base.

    Returns document references with URLs pointing to exact sections.
    By default, only 'approved' documents are searched. Use --status to include
    other statuses (draft, proposed, deprecated) or --include-all for everything.
    """
    import json

    from kb_engine.core.models.search import RetrievalMode, SearchFilters

    mode_map = {
        "vector": RetrievalMode.VECTOR,
        "graph": RetrievalMode.GRAPH,
        "hybrid": RetrievalMode.HYBRID,
    }

    # Build status filters
    filters = None
    if include_all:
        filters = SearchFilters(include_all_statuses=True)
    elif status:
        filters = SearchFilters(include_statuses=list(status))

    async def _search():
        _, retrieval_service, factory = await _create_services()
        try:
            response = await retrieval_service.search(
                query=query,
                limit=limit,
                score_threshold=threshold,
                mode=mode_map[mode],
                filters=filters,
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
                            "kdd_status": ref.kdd_status,
                            "kdd_version": ref.kdd_version,
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


def _get_graph_store():
    """Create and initialize a FalkorDB graph store from settings."""
    from kb_engine.config.settings import get_settings
    from kb_engine.smart.stores.falkordb_graph import FalkorDBGraphStore

    settings = get_settings()
    store = FalkorDBGraphStore(settings.falkordb_path)
    store.initialize()
    return store


@cli.group()
def graph() -> None:
    """Graph-related commands."""
    pass


@graph.command("orphans")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_orphans(output_json: bool) -> None:
    """List stub entities without a primary document.

    These are entities referenced by other documents but whose own
    document hasn't been indexed yet.
    """
    import json

    store = _get_graph_store()
    orphans = store.get_orphan_entities()

    if output_json:
        click.echo(json.dumps({"orphans": orphans, "count": len(orphans)}, indent=2))
        return

    if not orphans:
        click.echo("No orphan entities found. All referenced entities have primary documents.")
        return

    click.echo(f"Found {len(orphans)} orphan entities (stubs without primary document):\n")
    for entity in orphans:
        click.echo(f"  - {entity['name']} (confidence: {entity['confidence']:.2f})")
        click.echo(f"    Referenced by: {', '.join(entity['referenced_by'])}")


@graph.command("completeness")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--status", "-s", type=click.Choice(["complete", "stub", "orphan"]), help="Filter by status")
def graph_completeness(output_json: bool, status: str | None) -> None:
    """Show completeness status for all entities.

    Status types:
    - complete: Has a primary document
    - stub: Only referenced, no primary document yet
    - orphan: No provenance edges at all
    """
    import json

    store = _get_graph_store()
    entities = store.get_entity_completeness()

    if status:
        entities = [e for e in entities if e["status"] == status]

    if output_json:
        click.echo(json.dumps({"entities": entities, "count": len(entities)}, indent=2))
        return

    if not entities:
        click.echo("No entities found.")
        return

    # Group by status
    by_status = {"complete": [], "stub": [], "orphan": []}
    for e in entities:
        by_status[e["status"]].append(e)

    click.echo(f"Entity completeness ({len(entities)} total):\n")

    if by_status["complete"]:
        click.echo(f"  Complete ({len(by_status['complete'])}):")
        for e in by_status["complete"][:10]:
            docs = ", ".join(e["primary_docs"]) if e["primary_docs"] else "?"
            click.echo(f"    [OK] {e['name']} <- {docs}")
        if len(by_status["complete"]) > 10:
            click.echo(f"    ... and {len(by_status['complete']) - 10} more")

    if by_status["stub"]:
        click.echo(f"\n  Stubs ({len(by_status['stub'])}):")
        for e in by_status["stub"]:
            refs = ", ".join(e["referenced_by"]) if e["referenced_by"] else "?"
            click.echo(f"    [STUB] {e['name']} (referenced by: {refs})")

    if by_status["orphan"]:
        click.echo(f"\n  Orphans ({len(by_status['orphan'])}):")
        for e in by_status["orphan"]:
            click.echo(f"    [ORPHAN] {e['name']}")


@graph.command("stats")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_stats(output_json: bool) -> None:
    """Show graph database statistics."""
    import json

    store = _get_graph_store()
    stats = store.get_stats()

    if output_json:
        click.echo(json.dumps(stats, indent=2))
        return

    click.echo("Graph Statistics:")
    click.echo(f"  Entities:  {stats.get('entity_count', 0)}")
    click.echo(f"  Concepts:  {stats.get('concept_count', 0)}")
    click.echo(f"  Events:    {stats.get('event_count', 0)}")
    click.echo(f"  Documents: {stats.get('document_count', 0)}")
    total = sum(stats.get(f"{t}_count", 0) for t in ["entity", "concept", "event"])
    click.echo(f"  Total domain nodes: {total}")


@graph.command("ls")
@click.option("--type", "node_type", type=click.Choice(["entity", "concept", "event"]), help="Filter by node type")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_ls(node_type: str | None, output_json: bool) -> None:
    """List all domain nodes in the graph."""
    import json

    store = _get_graph_store()
    nodes = store.get_all_nodes(node_type)

    if output_json:
        click.echo(json.dumps({"nodes": nodes, "count": len(nodes)}, indent=2))
        return

    if not nodes:
        click.echo("No nodes found.")
        return

    click.echo(f"Found {len(nodes)} nodes:\n")
    for node in nodes:
        click.echo(f"  [{node['label']}] {node['id']}  {node['name']}")


@graph.command("inspect")
@click.argument("node_id")
@click.option("--depth", "-d", default=2, help="Traversal depth (default: 2)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_inspect(node_id: str, depth: int, output_json: bool) -> None:
    """Inspect a node and its neighborhood.

    Shows the node's properties, related nodes, and provenance.
    """
    import json

    store = _get_graph_store()
    neighborhood = store.get_node_graph(node_id, depth=depth)
    provenance = store.get_node_provenance(node_id)

    if output_json:
        click.echo(json.dumps({
            "neighborhood": neighborhood,
            "provenance": provenance,
        }, indent=2))
        return

    click.echo(f"Node: {node_id}")
    click.echo(f"  Depth: {depth}")

    if neighborhood["nodes"]:
        click.echo(f"\n  Related nodes ({len(neighborhood['nodes'])}):")
        for n in neighborhood["nodes"]:
            click.echo(f"    [{n['node_type']}] {n['id']}  {n['name']}")
    else:
        click.echo("\n  No related nodes.")

    if neighborhood["edge_types"]:
        click.echo(f"\n  Relationship types: {', '.join(neighborhood['edge_types'])}")

    if provenance:
        click.echo(f"\n  Provenance ({len(provenance)} documents):")
        for p in provenance:
            click.echo(f"    [{p['role']}] {p['doc_id']}  {p['title']}")
    else:
        click.echo("\n  No provenance records.")


@graph.command("path")
@click.argument("from_id")
@click.argument("to_id")
@click.option("--max-depth", default=5, help="Maximum traversal depth (default: 5)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_path(from_id: str, to_id: str, max_depth: int, output_json: bool) -> None:
    """Check reachability between two nodes."""
    import json

    store = _get_graph_store()
    paths = store.find_path(from_id, to_id, max_depth=max_depth)

    if output_json:
        click.echo(json.dumps({
            "from": from_id,
            "to": to_id,
            "max_depth": max_depth,
            "reachable": len(paths) > 0,
            "paths": paths,
        }, indent=2))
        return

    if paths:
        p = paths[0]
        click.echo(f"Path found: {p['start_name']} -> {p['end_name']}")
    else:
        click.echo(f"No path found between {from_id} and {to_id} (max depth: {max_depth}).")


@graph.command("impact")
@click.argument("doc_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_impact(doc_id: str, output_json: bool) -> None:
    """Show nodes extracted from a document."""
    import json

    store = _get_graph_store()
    nodes = store.get_document_impact(doc_id)

    if output_json:
        click.echo(json.dumps({"doc_id": doc_id, "nodes": nodes, "count": len(nodes)}, indent=2))
        return

    if not nodes:
        click.echo(f"No nodes found for document: {doc_id}")
        return

    click.echo(f"Document {doc_id} impact ({len(nodes)} nodes):\n")
    for n in nodes:
        conf = f" (confidence: {n['confidence']:.2f})" if n.get("confidence") else ""
        click.echo(f"  [{n['node_type']}] {n['id']}  {n['name']}  role={n['role']}{conf}")


@graph.command("provenance")
@click.argument("node_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_provenance(node_id: str, output_json: bool) -> None:
    """Show documents that contributed to a node."""
    import json

    store = _get_graph_store()
    provenance = store.get_node_provenance(node_id)

    if output_json:
        click.echo(json.dumps({
            "node_id": node_id,
            "provenance": provenance,
            "count": len(provenance),
        }, indent=2))
        return

    if not provenance:
        click.echo(f"No provenance records for node: {node_id}")
        return

    click.echo(f"Provenance for {node_id} ({len(provenance)} documents):\n")
    for p in provenance:
        click.echo(f"  [{p['role']}] {p['doc_id']}  {p['title']}")
        if p.get("path"):
            click.echo(f"         {p['path']}")


@graph.command("cypher")
@click.argument("query")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_cypher(query: str, output_json: bool) -> None:
    """Execute a raw Cypher query.

    Example: kb graph cypher "MATCH (n) RETURN labels(n)[0] as type, count(n) as cnt"
    """
    import json

    store = _get_graph_store()

    try:
        results = store.execute_cypher(query)
    except Exception as e:
        if output_json:
            click.echo(json.dumps({"error": str(e)}, indent=2))
        else:
            click.echo(f"Cypher error: {e}", err=True)
        sys.exit(1)

    if output_json:
        click.echo(json.dumps({"results": results, "count": len(results)}, indent=2))
        return

    if not results:
        click.echo("Query returned no results.")
        return

    # Table output
    headers = list(results[0].keys())
    click.echo("  ".join(headers))
    click.echo("  ".join("-" * len(h) for h in headers))
    for row in results:
        click.echo("  ".join(str(row.get(h, "")) for h in headers))


@graph.command("delete")
@click.argument("node_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def graph_delete(node_id: str, force: bool, output_json: bool) -> None:
    """Delete a node and all its relationships."""
    import json

    if not force:
        click.confirm(f"Delete node '{node_id}' and all its relationships?", abort=True)

    store = _get_graph_store()
    deleted = store.delete_node(node_id)

    if output_json:
        click.echo(json.dumps({"node_id": node_id, "deleted": deleted}, indent=2))
        return

    if deleted:
        click.echo(f"Deleted node: {node_id}")
    else:
        click.echo(f"Node not found: {node_id}")


if __name__ == "__main__":
    cli()
