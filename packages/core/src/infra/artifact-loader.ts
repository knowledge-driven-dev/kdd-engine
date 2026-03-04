/**
 * Artifact loader — reads .kdd-index/ artifacts.
 */

import { join } from "node:path";
import { Glob } from "bun";
import type { Embedding, EmbeddingMeta, GraphEdge, GraphNode, Manifest } from "../domain/types.ts";

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

  for await (const jsonPath of glob.scan({ cwd: embDir, absolute: true })) {
    const items: (Embedding | EmbeddingMeta)[] = await Bun.file(jsonPath).json();
    if (items.length === 0) continue;

    // Auto-detect format: legacy JSON has "vector" field, new format does not
    if ("vector" in items[0]!) {
      embeddings.push(...(items as Embedding[]));
    } else {
      // Read companion .f32 binary
      const f32Path = jsonPath.replace(/\.json$/, ".f32");
      const buf = await Bun.file(f32Path).arrayBuffer();
      const floats = new Float32Array(buf);
      const meta = items as EmbeddingMeta[];
      const dims = meta[0]!.dimensions;

      for (let i = 0; i < meta.length; i++) {
        const vector = Array.from(floats.subarray(i * dims, (i + 1) * dims));
        embeddings.push({ ...meta[i]!, vector });
      }
    }
  }

  return embeddings;
}
