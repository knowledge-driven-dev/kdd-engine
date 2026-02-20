/**
 * Artifact loader — reads .kdd-index/ artifacts.
 */

import { join } from "node:path";
import { Glob } from "bun";
import type { Embedding, GraphEdge, GraphNode, Manifest } from "../domain/types.ts";

export async function loadManifest(indexPath: string): Promise<Manifest> {
  return Bun.file(join(indexPath, "manifest.json")).json();
}

export async function loadAllNodes(indexPath: string): Promise<GraphNode[]> {
  const nodesDir = join(indexPath, "nodes");
  const glob = new Glob("**/*.json");
  const nodes: GraphNode[] = [];

  for await (const path of glob.scan({ cwd: nodesDir, absolute: true })) {
    const node: GraphNode = await Bun.file(path).json();
    nodes.push(node);
  }

  return nodes;
}

export async function loadEdges(indexPath: string): Promise<GraphEdge[]> {
  const edgesFile = join(indexPath, "edges", "edges.jsonl");
  const text = await Bun.file(edgesFile).text();
  const edges: GraphEdge[] = [];

  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed) {
      edges.push(JSON.parse(trimmed) as GraphEdge);
    }
  }

  return edges;
}

export async function loadAllEmbeddings(indexPath: string): Promise<Embedding[]> {
  const embDir = join(indexPath, "embeddings");
  const glob = new Glob("**/*.json");
  const embeddings: Embedding[] = [];

  for await (const path of glob.scan({ cwd: embDir, absolute: true })) {
    const chunks: Embedding[] = await Bun.file(path).json();
    embeddings.push(...chunks);
  }

  return embeddings;
}
