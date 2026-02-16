"""KDD CLI — Click-based command-line interface.

Entry point: ``kdd`` command group.

Commands:
  kdd index <specs_path>    Index all specs (CMD-001/CMD-002)
  kdd search <query>        Hybrid search (QRY-003)
  kdd graph <node_id>       Graph traversal (QRY-001)
  kdd impact <node_id>      Impact analysis (QRY-004)
  kdd coverage <node_id>    Coverage analysis (QRY-005)
  kdd violations            Layer violations (QRY-006)
  kdd merge <paths...>      Merge indices (CMD-004)
  kdd status                Show index status
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from kdd.container import create_container


@click.group()
@click.version_option(version="1.0.0", prog_name="kdd")
def cli():
    """KDD — Knowledge-Driven Development retrieval engine."""
    pass


# ---------------------------------------------------------------------------
# kdd index
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("specs_path", type=click.Path(exists=True))
@click.option("--index-path", type=click.Path(), default=None, help="Output .kdd-index/ path")
@click.option("--incremental/--full", default=True, help="Incremental (default) or full reindex")
@click.option("--domain", default=None, help="Domain name for multi-domain support")
def index(specs_path: str, index_path: str | None, incremental: bool, domain: str | None):
    """Index KDD specs into .kdd-index/ artifacts."""
    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    if incremental:
        from kdd.application.commands.index_incremental import index_incremental

        result = index_incremental(
            specs_root,
            registry=container.registry,
            artifact_store=container.artifact_store,
            event_bus=container.event_bus,
            embedding_model=container.embedding_model,
            index_level=container.index_level,
            domain=domain,
        )
        click.echo(f"Indexed: {result.indexed}  Deleted: {result.deleted}  "
                    f"Skipped: {result.skipped}  Errors: {result.errors}")
        if result.is_full_reindex:
            click.echo("(full reindex — no prior manifest found)")
    else:
        from kdd.application.commands.index_incremental import index_incremental

        result = index_incremental(
            specs_root,
            registry=container.registry,
            artifact_store=container.artifact_store,
            event_bus=container.event_bus,
            embedding_model=container.embedding_model,
            index_level=container.index_level,
            domain=domain,
        )
        click.echo(f"Full index: {result.indexed} documents  "
                    f"Skipped: {result.skipped}  Errors: {result.errors}")

    click.echo(f"Index level: {container.index_level.value}")
    click.echo(f"Index path: {container.index_path}")


# ---------------------------------------------------------------------------
# kdd search
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Max results")
@click.option("--min-score", default=0.5, help="Minimum score threshold")
@click.option("--depth", default=2, help="Graph expansion depth")
@click.option("--no-graph", is_flag=True, help="Disable graph expansion")
@click.option("--kind", multiple=True, help="Filter by kind (repeatable)")
@click.option("--index-path", type=click.Path(), default=None)
@click.option("--specs-path", type=click.Path(exists=True), default=".")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def search(query: str, limit: int, min_score: float, depth: int, no_graph: bool,
           kind: tuple, index_path: str | None, specs_path: str, json_output: bool):
    """Search the KDD index (hybrid: semantic + graph + lexical)."""
    from kdd.application.queries.retrieve_hybrid import HybridQueryInput, retrieve_hybrid
    from kdd.domain.enums import KDDKind

    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    if not container.ensure_loaded():
        click.echo("Error: No index found. Run 'kdd index' first.", err=True)
        sys.exit(1)

    include_kinds = [KDDKind(k) for k in kind] if kind else None

    result = retrieve_hybrid(
        HybridQueryInput(
            query_text=query,
            expand_graph=not no_graph,
            depth=depth,
            include_kinds=include_kinds,
            min_score=min_score,
            limit=limit,
        ),
        container.graph_store,
        container.vector_store,
        container.embedding_model,
    )

    if json_output:
        data = {
            "total_results": result.total_results,
            "total_tokens": result.total_tokens,
            "warnings": result.warnings,
            "results": [
                {"node_id": r.node_id, "score": round(r.score, 4),
                 "match_source": r.match_source, "snippet": r.snippet}
                for r in result.results
            ],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        if result.warnings:
            for w in result.warnings:
                click.echo(f"  Warning: {w}", err=True)
        click.echo(f"Found {result.total_results} results:\n")
        for r in result.results:
            score_bar = "█" * int(r.score * 10)
            click.echo(f"  {r.score:.3f} {score_bar} {r.node_id}")
            if r.snippet:
                click.echo(f"         {r.snippet}")
            click.echo(f"         source: {r.match_source}")
            click.echo()


# ---------------------------------------------------------------------------
# kdd graph
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("node_id")
@click.option("--depth", "-d", default=2, help="Traversal depth")
@click.option("--edge-type", multiple=True, help="Filter edge types")
@click.option("--index-path", type=click.Path(), default=None)
@click.option("--specs-path", type=click.Path(exists=True), default=".")
def graph(node_id: str, depth: int, edge_type: tuple, index_path: str | None, specs_path: str):
    """Traverse the knowledge graph from a root node (QRY-001)."""
    from kdd.application.queries.retrieve_graph import GraphQueryInput, retrieve_by_graph

    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    if not container.ensure_loaded():
        click.echo("Error: No index found. Run 'kdd index' first.", err=True)
        sys.exit(1)

    edge_types = list(edge_type) if edge_type else None
    try:
        result = retrieve_by_graph(
            GraphQueryInput(root_node=node_id, depth=depth, edge_types=edge_types),
            container.graph_store,
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Center: {result.center_node.id if result.center_node else '?'}")
    click.echo(f"Related nodes: {result.total_nodes}  Edges: {result.total_edges}\n")
    for r in result.related_nodes:
        click.echo(f"  {r.score:.3f}  {r.node_id}  ({r.snippet})")


# ---------------------------------------------------------------------------
# kdd impact
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("node_id")
@click.option("--depth", "-d", default=3, help="Analysis depth")
@click.option("--index-path", type=click.Path(), default=None)
@click.option("--specs-path", type=click.Path(exists=True), default=".")
def impact(node_id: str, depth: int, index_path: str | None, specs_path: str):
    """Analyze the impact of changing a node (QRY-004)."""
    from kdd.application.queries.retrieve_impact import ImpactQueryInput, retrieve_impact

    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    if not container.ensure_loaded():
        click.echo("Error: No index found.", err=True)
        sys.exit(1)

    try:
        result = retrieve_impact(
            ImpactQueryInput(node_id=node_id, depth=depth),
            container.graph_store,
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Impact analysis for: {node_id}\n")
    click.echo(f"Directly affected: {result.total_directly}")
    for a in result.directly_affected:
        click.echo(f"  {a.node_id} [{a.edge_type}] — {a.impact_description}")

    if result.transitively_affected:
        click.echo(f"\nTransitively affected: {result.total_transitively}")
        for t in result.transitively_affected:
            path_str = " → ".join(t.path)
            click.echo(f"  {t.node_id} via {path_str}")

    if result.scenarios_to_rerun:
        click.echo(f"\nBDD scenarios to re-run: {len(result.scenarios_to_rerun)}")
        for s in result.scenarios_to_rerun:
            click.echo(f"  {s.scenario_name} — {s.reason}")


# ---------------------------------------------------------------------------
# kdd coverage
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("node_id")
@click.option("--index-path", type=click.Path(), default=None)
@click.option("--specs-path", type=click.Path(exists=True), default=".")
def coverage(node_id: str, index_path: str | None, specs_path: str):
    """Check governance coverage for a node (QRY-005)."""
    from kdd.application.queries.retrieve_coverage import CoverageQueryInput, retrieve_coverage

    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    if not container.ensure_loaded():
        click.echo("Error: No index found.", err=True)
        sys.exit(1)

    try:
        result = retrieve_coverage(
            CoverageQueryInput(node_id=node_id),
            container.graph_store,
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Coverage for {node_id}: {result.coverage_percent:.0f}%\n")
    for cat in result.categories:
        icon = "✓" if cat.status == "covered" else "✗"
        click.echo(f"  {icon} {cat.name}: {cat.status}")
        if cat.found:
            for fid in cat.found:
                click.echo(f"      → {fid}")


# ---------------------------------------------------------------------------
# kdd violations
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--index-path", type=click.Path(), default=None)
@click.option("--specs-path", type=click.Path(exists=True), default=".")
def violations(index_path: str | None, specs_path: str):
    """List all layer dependency violations (QRY-006)."""
    from kdd.application.queries.retrieve_violations import (
        ViolationsQueryInput,
        retrieve_violations,
    )

    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    if not container.ensure_loaded():
        click.echo("Error: No index found.", err=True)
        sys.exit(1)

    result = retrieve_violations(ViolationsQueryInput(), container.graph_store)

    click.echo(f"Total edges: {result.total_edges_analyzed}")
    click.echo(f"Violations: {result.total_violations} ({result.violation_rate:.1f}%)\n")

    for v in result.violations:
        click.echo(f"  {v.from_node} ({v.from_layer.value}) → "
                    f"{v.to_node} ({v.to_layer.value}) [{v.edge_type}]")


# ---------------------------------------------------------------------------
# kdd merge
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("sources", nargs=-1, required=True)
@click.option("-o", "--output", required=True, type=click.Path(), help="Output .kdd-index/ path")
@click.option("--strategy", default="last_write_wins",
              type=click.Choice(["last_write_wins", "fail_on_conflict"]))
def merge(sources: tuple, output: str, strategy: str):
    """Merge multiple .kdd-index/ directories (CMD-004)."""
    from kdd.application.commands.merge_index import merge_index

    source_paths = [Path(s) for s in sources]
    result = merge_index(source_paths, Path(output), conflict_strategy=strategy)

    if result.success:
        click.echo(f"Merge successful: {result.total_nodes} nodes, "
                    f"{result.total_edges} edges, "
                    f"{result.conflicts_resolved} conflicts resolved")
        click.echo(f"Output: {output}")
    else:
        click.echo(f"Merge failed: {result.error}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# kdd enrich
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("node_id")
@click.option("--timeout", default=120, help="Claude CLI timeout in seconds")
@click.option("--model", default=None, help="Claude model override (e.g. sonnet)")
@click.option("--index-path", type=click.Path(), default=None)
@click.option("--specs-path", type=click.Path(exists=True), default=".")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def enrich(node_id: str, timeout: int, model: str | None,
           index_path: str | None, specs_path: str, json_output: bool):
    """Enrich a node with AI agent analysis (CMD-003 / UC-003)."""
    from kdd.application.commands.enrich_with_agent import enrich_with_agent

    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    if not container.ensure_loaded():
        click.echo("Error: No index found. Run 'kdd index' first.", err=True)
        sys.exit(1)

    if container.agent_client is None:
        click.echo(
            "Error: Claude CLI not found. Install it from "
            "https://docs.anthropic.com/en/docs/claude-code",
            err=True,
        )
        sys.exit(1)

    # Apply overrides
    if hasattr(container.agent_client, "timeout") and timeout != 120:
        container.agent_client.timeout = timeout
    if hasattr(container.agent_client, "model") and model:
        container.agent_client.model = model

    result = enrich_with_agent(
        node_id,
        artifact_store=container.artifact_store,
        agent_client=container.agent_client,
        specs_root=specs_root,
    )

    if not result.success:
        click.echo(f"Error: {result.error}", err=True)
        sys.exit(1)

    if json_output:
        click.echo(json.dumps(result.enrichment, indent=2, default=str))
    else:
        enrichment = result.enrichment or {}
        click.echo(f"Enrichment for: {node_id}\n")
        if enrichment.get("summary"):
            click.echo(f"Summary: {enrichment['summary']}\n")
        click.echo(f"Implicit edges added: {result.implicit_edges}")
        impact = enrichment.get("impact_analysis", {})
        if impact:
            click.echo(f"Change risk: {impact.get('change_risk', 'unknown')}")
            click.echo(f"Reason: {impact.get('reason', '')}")


# ---------------------------------------------------------------------------
# kdd status
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--index-path", type=click.Path(), default=None)
@click.option("--specs-path", type=click.Path(exists=True), default=".")
def status(index_path: str | None, specs_path: str):
    """Show index status and statistics."""
    specs_root = Path(specs_path).resolve()
    idx_path = Path(index_path) if index_path else None
    container = create_container(specs_root, idx_path)

    manifest = container.artifact_store.read_manifest()
    if manifest is None:
        click.echo("No index found. Run 'kdd index <specs_path>' to create one.")
        return

    click.echo(f"Index path:    {container.index_path}")
    click.echo(f"Version:       {manifest.version}")
    click.echo(f"Index level:   {manifest.index_level.value}")
    click.echo(f"Indexed at:    {manifest.indexed_at}")
    click.echo(f"Indexed by:    {manifest.indexed_by}")
    click.echo(f"Git commit:    {manifest.git_commit or 'N/A'}")
    click.echo(f"Structure:     {manifest.structure}")
    click.echo(f"Nodes:         {manifest.stats.nodes}")
    click.echo(f"Edges:         {manifest.stats.edges}")
    click.echo(f"Embeddings:    {manifest.stats.embeddings}")
    if manifest.embedding_model:
        click.echo(f"Embed model:   {manifest.embedding_model}")
    if manifest.domains:
        click.echo(f"Domains:       {', '.join(manifest.domains)}")
