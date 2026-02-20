/**
 * QRY-002 — Semantic search (pure vector, no graph expansion).
 */

import { KIND_PREFIX, type KDDKind, type KDDLayer, type ScoredNode } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";
import type { VectorStore } from "../../infra/vector-store.ts";

export interface SemanticQueryInput {
  queryText: string;
  includeKinds?: KDDKind[];
  includeLayers?: KDDLayer[];
  minScore?: number;
  limit?: number;
}

export interface SemanticQueryResult {
  results: ScoredNode[];
  totalResults: number;
  embeddingModel: string;
}

export async function semanticQuery(
  input: SemanticQueryInput,
  vectorStore: VectorStore,
  graphStore: GraphStore,
  encodeFn: (texts: string[]) => Promise<number[][]>,
  modelName: string,
): Promise<SemanticQueryResult> {
  const {
    queryText,
    includeKinds,
    includeLayers,
    minScore = 0.7,
    limit = 10,
  } = input;

  if (queryText.trim().length < 3) {
    throw new Error("QUERY_TOO_SHORT: query_text must be at least 3 characters");
  }

  const vectors = await encodeFn([queryText]);
  const matches = vectorStore.search(vectors[0]!, limit * 3, minScore);

  const seenNodes = new Set<string>();
  const results: ScoredNode[] = [];

  for (const [embId, score] of matches) {
    const docId = embId.includes(":chunk-")
      ? embId.split(":chunk-")[0]!
      : embId.split(":")[0]!;

    const node = findNodeForDoc(docId, graphStore);
    if (!node) continue;

    if (seenNodes.has(node.id)) continue;
    seenNodes.add(node.id);

    if (includeKinds && !includeKinds.includes(node.kind as KDDKind)) continue;
    if (includeLayers && !includeLayers.includes(node.layer as KDDLayer)) continue;

    results.push({
      node_id: node.id,
      score,
      snippet: buildSnippet(node),
      match_source: "semantic",
    });

    if (results.length >= limit) break;
  }

  return {
    results,
    totalResults: results.length,
    embeddingModel: modelName,
  };
}

function findNodeForDoc(docId: string, graphStore: GraphStore) {
  for (const prefix of Object.values(KIND_PREFIX)) {
    const node = graphStore.getNode(`${prefix}:${docId}`);
    if (node) return node;
  }
  return graphStore.getNode(docId);
}

function buildSnippet(node: { kind: string; id: string; indexed_fields: Record<string, unknown> }): string {
  const title = node.indexed_fields.title;
  if (title) return `[${node.kind}] ${title}`;
  return `[${node.kind}] ${node.id}`;
}
