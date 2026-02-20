/**
 * Container — wires up artifact loading and store initialization.
 */

import { loadAllEmbeddings, loadAllNodes, loadEdges, loadManifest } from "./infra/artifact-loader.ts";
import { createEncoder } from "./infra/embedding-model.ts";
import { GraphStore } from "./infra/graph-store.ts";
import { VectorStore } from "./infra/vector-store.ts";
import type { Manifest } from "./domain/types.ts";

export interface Container {
  manifest: Manifest;
  graphStore: GraphStore;
  vectorStore: VectorStore | null;
  encodeFn: ((texts: string[]) => Promise<number[][]>) | null;
  modelName: string | null;
}

export async function createContainer(
  indexPath: string,
  options: { skipEmbeddings?: boolean } = {},
): Promise<Container> {
  const manifest = await loadManifest(indexPath);

  const [nodes, edges] = await Promise.all([
    loadAllNodes(indexPath),
    loadEdges(indexPath),
  ]);

  const graphStore = new GraphStore();
  graphStore.load(nodes, edges);

  let vectorStore: VectorStore | null = null;
  let encodeFn: ((texts: string[]) => Promise<number[][]>) | null = null;
  let modelName: string | null = null;

  const hasEmbeddings = manifest.stats.embeddings > 0;
  if (hasEmbeddings && !options.skipEmbeddings) {
    const embeddings = await loadAllEmbeddings(indexPath);
    vectorStore = new VectorStore();
    vectorStore.load(embeddings);

    modelName = embeddings[0]?.model ?? manifest.embedding_model ?? null;
    encodeFn = createEncoder(modelName ?? undefined);
  }

  return { manifest, graphStore, vectorStore, encodeFn, modelName };
}
