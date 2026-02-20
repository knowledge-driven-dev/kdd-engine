/**
 * kdd CLI — TypeScript/Bun implementation.
 *
 * Subcommands: index, search, graph, impact, semantic, coverage, violations
 */

import { defineCommand, runMain } from "citty";
import { resolve } from "node:path";
import { Glob } from "bun";
import { createContainer } from "./container.ts";
import { hybridSearch } from "./application/queries/hybrid-search.ts";
import { graphQuery } from "./application/queries/graph-query.ts";
import { impactQuery } from "./application/queries/impact-query.ts";
import { semanticQuery } from "./application/queries/semantic-query.ts";
import { coverageQuery } from "./application/queries/coverage-query.ts";
import { violationsQuery } from "./application/queries/violations-query.ts";
import { indexDocument } from "./application/commands/index-document.ts";
import { createDefaultRegistry } from "./application/extractors/registry.ts";
import { ArtifactWriter } from "./infra/artifact-writer.ts";
import { createEncoder } from "./infra/embedding-model.ts";
import { detectIndexLevel } from "./domain/rules.ts";
import { IndexLevel, type KDDKind, type KDDLayer, type Manifest } from "./domain/types.ts";

// ── Index command ───────────────────────────────────────────────────

const indexCmd = defineCommand({
  meta: { name: "index", description: "Index KDD specs into .kdd-index/" },
  args: {
    specsPath: { type: "positional", description: "Path to specs directory", required: true },
    "index-path": { type: "string", description: "Output .kdd-index/ path", default: ".kdd-index" },
    domain: { type: "string", description: "Domain name" },
    level: { type: "string", description: "Index level: L1 (graph only) or L2 (graph + embeddings)", default: "L2" },
  },
  async run({ args }) {
    const specsRoot = resolve(args.specsPath);
    const indexPath = resolve(args["index-path"]);
    const domain = args.domain ?? null;

    const indexLevel = args.level === "L1" ? IndexLevel.L1 : IndexLevel.L2;

    console.log(`Indexing specs from: ${specsRoot}`);
    console.log(`Output: ${indexPath}`);
    console.log(`Level: ${indexLevel}`);

    const registry = createDefaultRegistry();
    const writer = new ArtifactWriter(indexPath);

    // Clear previous edges
    await writer.clearEdges();

    let encodeFn: ((texts: string[]) => Promise<number[][]>) | null = null;
    let modelName: string | undefined;
    let modelDimensions: number | undefined;

    if (indexLevel !== IndexLevel.L1) {
      modelName = "all-mpnet-base-v2";
      modelDimensions = 768;
      console.log(`Loading embedding model: ${modelName}...`);
      encodeFn = createEncoder(modelName);
    }

    const glob = new Glob("**/*.md");
    const files: string[] = [];
    for await (const path of glob.scan({ cwd: specsRoot, absolute: true })) {
      files.push(path);
    }
    files.sort();

    console.log(`Found ${files.length} markdown files\n`);

    let nodeCount = 0;
    let edgeCount = 0;
    let embeddingCount = 0;
    let skippedCount = 0;
    const domains = new Set<string>();

    for (const filePath of files) {
      const result = await indexDocument(filePath, {
        specsRoot,
        registry,
        artifactWriter: writer,
        encodeFn,
        modelName,
        modelDimensions,
        indexLevel,
        domain,
      });

      if (result.success) {
        nodeCount++;
        edgeCount += result.edge_count;
        embeddingCount += result.embedding_count;
        if (domain) domains.add(domain);
        const icon = result.warning ? "⚠" : "✓";
        console.log(`  ${icon} ${result.node_id} (${result.edge_count} edges, ${result.embedding_count} embeddings)`);
        if (result.warning) console.log(`    Warning: ${result.warning}`);
      } else {
        skippedCount++;
      }
    }

    // Write manifest
    let gitCommit: string | null = null;
    try {
      const proc = Bun.spawn(["git", "rev-parse", "HEAD"], { stdout: "pipe" });
      gitCommit = (await new Response(proc.stdout).text()).trim() || null;
    } catch { /* not a git repo */ }

    const manifest: Manifest = {
      version: "1.0.0",
      kdd_version: "1.0.0",
      embedding_model: modelName ?? null,
      embedding_dimensions: modelDimensions ?? null,
      indexed_at: new Date().toISOString(),
      indexed_by: "kdd-ts",
      structure: "flat",
      index_level: indexLevel,
      stats: { nodes: nodeCount, edges: edgeCount, embeddings: embeddingCount, enrichments: 0 },
      domains: [...domains],
      git_commit: gitCommit,
    };
    await writer.writeManifest(manifest);

    console.log(`\nDone: ${nodeCount} nodes, ${edgeCount} edges, ${embeddingCount} embeddings (${skippedCount} skipped)`);
  },
});

// ── Search subcommands ──────────────────────────────────────────────

const searchCmd = defineCommand({
  meta: { name: "search", description: "Hybrid search (semantic + lexical + graph)" },
  args: {
    query: { type: "positional", description: "Search query text", required: true },
    "index-path": { type: "string", description: "Path to .kdd-index/", default: ".kdd-index" },
    "min-score": { type: "string", description: "Minimum score threshold", default: "0.3" },
    n: { type: "string", description: "Max results", default: "10" },
    kind: { type: "string", description: "Filter by kind (comma-separated)" },
    "no-embeddings": { type: "boolean", description: "Skip embedding model loading", default: false },
  },
  async run({ args }) {
    const indexPath = resolve(args["index-path"]);
    const container = await createContainer(indexPath, {
      skipEmbeddings: args["no-embeddings"],
    });

    const includeKinds = args.kind
      ? (args.kind.split(",") as KDDKind[])
      : undefined;

    const result = await hybridSearch(
      {
        queryText: args.query,
        minScore: parseFloat(args["min-score"]),
        limit: parseInt(args.n, 10),
        includeKinds,
      },
      container.graphStore,
      container.vectorStore,
      container.encodeFn,
    );

    console.log(JSON.stringify(result, null, 2));
  },
});

const graphCmd = defineCommand({
  meta: { name: "graph", description: "Graph traversal from a root node" },
  args: {
    root: { type: "positional", description: "Root node ID (e.g. Entity:KDDDocument)", required: true },
    "index-path": { type: "string", description: "Path to .kdd-index/", default: ".kdd-index" },
    depth: { type: "string", description: "Traversal depth", default: "2" },
    kind: { type: "string", description: "Filter by kind (comma-separated)" },
  },
  async run({ args }) {
    const indexPath = resolve(args["index-path"]);
    const container = await createContainer(indexPath, { skipEmbeddings: true });

    const includeKinds = args.kind
      ? (args.kind.split(",") as KDDKind[])
      : undefined;

    const result = graphQuery(
      {
        rootNode: args.root,
        depth: parseInt(args.depth, 10),
        includeKinds,
      },
      container.graphStore,
    );

    console.log(JSON.stringify(result, null, 2));
  },
});

const impactCmd = defineCommand({
  meta: { name: "impact", description: "Impact analysis (reverse BFS)" },
  args: {
    node: { type: "positional", description: "Node ID to analyze", required: true },
    "index-path": { type: "string", description: "Path to .kdd-index/", default: ".kdd-index" },
    depth: { type: "string", description: "Analysis depth", default: "3" },
  },
  async run({ args }) {
    const indexPath = resolve(args["index-path"]);
    const container = await createContainer(indexPath, { skipEmbeddings: true });

    const result = impactQuery(
      {
        nodeId: args.node,
        depth: parseInt(args.depth, 10),
      },
      container.graphStore,
    );

    console.log(JSON.stringify(result, null, 2));
  },
});

const semanticCmd = defineCommand({
  meta: { name: "semantic", description: "Pure semantic search (vector only)" },
  args: {
    query: { type: "positional", description: "Search query text", required: true },
    "index-path": { type: "string", description: "Path to .kdd-index/", default: ".kdd-index" },
    "min-score": { type: "string", description: "Minimum score threshold", default: "0.7" },
    n: { type: "string", description: "Max results", default: "10" },
    kind: { type: "string", description: "Filter by kind (comma-separated)" },
  },
  async run({ args }) {
    const indexPath = resolve(args["index-path"]);
    const container = await createContainer(indexPath);

    if (!container.vectorStore || !container.encodeFn) {
      console.error("Error: No embeddings found in index. Semantic search requires L2+ index.");
      process.exit(1);
    }

    const includeKinds = args.kind
      ? (args.kind.split(",") as KDDKind[])
      : undefined;

    const result = await semanticQuery(
      {
        queryText: args.query,
        minScore: parseFloat(args["min-score"]),
        limit: parseInt(args.n, 10),
        includeKinds,
      },
      container.vectorStore,
      container.graphStore,
      container.encodeFn,
      container.modelName ?? "unknown",
    );

    console.log(JSON.stringify(result, null, 2));
  },
});

const coverageCmd = defineCommand({
  meta: { name: "coverage", description: "Governance coverage analysis" },
  args: {
    node: { type: "positional", description: "Node ID to analyze (e.g. Entity:KDDDocument)", required: true },
    "index-path": { type: "string", description: "Path to .kdd-index/", default: ".kdd-index" },
  },
  async run({ args }) {
    const indexPath = resolve(args["index-path"]);
    const container = await createContainer(indexPath, { skipEmbeddings: true });

    const result = coverageQuery(
      { nodeId: args.node },
      container.graphStore,
    );

    console.log(JSON.stringify(result, null, 2));
  },
});

const violationsCmd = defineCommand({
  meta: { name: "violations", description: "Detect layer dependency violations" },
  args: {
    "index-path": { type: "string", description: "Path to .kdd-index/", default: ".kdd-index" },
    kind: { type: "string", description: "Filter by kind (comma-separated)" },
    layer: { type: "string", description: "Filter by layer (comma-separated)" },
  },
  async run({ args }) {
    const indexPath = resolve(args["index-path"]);
    const container = await createContainer(indexPath, { skipEmbeddings: true });

    const includeKinds = args.kind
      ? (args.kind.split(",") as KDDKind[])
      : undefined;
    const includeLayers = args.layer
      ? (args.layer.split(",") as KDDLayer[])
      : undefined;

    const result = violationsQuery(
      { includeKinds, includeLayers },
      container.graphStore,
    );

    console.log(JSON.stringify(result, null, 2));
  },
});

// ── Main ────────────────────────────────────────────────────────────

const main = defineCommand({
  meta: { name: "kdd", version: "1.0.0", description: "KDD specification toolkit (TypeScript/Bun)" },
  subCommands: {
    index: indexCmd,
    search: searchCmd,
    graph: graphCmd,
    impact: impactCmd,
    semantic: semanticCmd,
    coverage: coverageCmd,
    violations: violationsCmd,
  },
});

runMain(main);
