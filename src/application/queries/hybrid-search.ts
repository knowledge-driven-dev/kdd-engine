/**
 * QRY-003 — Hybrid search (semantic + lexical + graph + fusion).
 */

import { KIND_PREFIX, type GraphEdge, type KDDKind, type KDDLayer, type ScoredNode } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";
import type { VectorStore } from "../../infra/vector-store.ts";

const WEIGHT_SEMANTIC = 0.6;
const WEIGHT_GRAPH = 0.3;
const WEIGHT_LEXICAL = 0.1;
const CHARS_PER_TOKEN = 4;

export interface HybridSearchInput {
  queryText: string;
  expandGraph?: boolean;
  depth?: number;
  includeKinds?: KDDKind[];
  includeLayers?: KDDLayer[];
  respectLayers?: boolean;
  minScore?: number;
  limit?: number;
  maxTokens?: number;
}

export interface HybridSearchResult {
  results: ScoredNode[];
  graphExpansion: GraphEdge[];
  totalResults: number;
  totalTokens: number;
  warnings: string[];
}

export async function hybridSearch(
  input: HybridSearchInput,
  graphStore: GraphStore,
  vectorStore: VectorStore | null,
  encodeFn: ((texts: string[]) => Promise<number[][]>) | null,
): Promise<HybridSearchResult> {
  const {
    queryText,
    expandGraph = true,
    depth = 2,
    includeKinds,
    includeLayers,
    respectLayers = true,
    minScore = 0.5,
    limit = 10,
    maxTokens = 8000,
  } = input;

  if (queryText.trim().length < 3) {
    throw new Error("QUERY_TOO_SHORT: query_text must be at least 3 characters");
  }

  const warnings: string[] = [];
  const scores = new Map<string, Map<string, number>>();

  // Phase 1: Semantic search
  if (vectorStore && encodeFn) {
    const vectors = await encodeFn([queryText]);
    const matches = vectorStore.search(vectors[0]!, limit * 3, minScore * 0.8);

    for (const [embId, score] of matches) {
      const nodeId = embIdToNodeId(embId, graphStore);
      if (!nodeId) continue;
      const existing = scores.get(nodeId) ?? new Map<string, number>();
      existing.set("semantic", Math.max(existing.get("semantic") ?? 0, score));
      scores.set(nodeId, existing);
    }
  } else {
    warnings.push("NO_EMBEDDINGS: index is L1, semantic search skipped");
  }

  // Phase 2: Lexical search
  const lexicalNodes = graphStore.textSearch(queryText);
  for (const node of lexicalNodes) {
    if (kindLayerFilter(node, includeKinds, includeLayers)) {
      const existing = scores.get(node.id) ?? new Map<string, number>();
      existing.set("lexical", 0.5);
      scores.set(node.id, existing);
    }
  }

  // Phase 3: Graph expansion
  const allGraphEdges: GraphEdge[] = [];
  if (expandGraph) {
    const seedIds = [...scores.keys()];
    for (const seedId of seedIds) {
      if (!graphStore.hasNode(seedId)) continue;
      const [nodes, edges] = graphStore.traverse(seedId, depth, undefined, respectLayers);
      allGraphEdges.push(...edges);
      for (const n of nodes) {
        if (n.id === seedId) continue;
        if (kindLayerFilter(n, includeKinds, includeLayers)) {
          const existing = scores.get(n.id) ?? new Map<string, number>();
          existing.set("graph", 0.5);
          scores.set(n.id, existing);
        }
      }
    }
  }

  // Phase 4: Fusion scoring
  const fused: ScoredNode[] = [];
  for (const [nodeId, sources] of scores) {
    const node = graphStore.getNode(nodeId);
    if (!node) continue;
    if (!kindLayerFilter(node, includeKinds, includeLayers)) continue;

    const score = computeFusionScore(sources);
    if (score < minScore) continue;

    fused.push({
      node_id: nodeId,
      score,
      snippet: buildSnippet(node),
      match_source: determineMatchSource(sources),
    });
  }

  fused.sort((a, b) => b.score - a.score);

  // Token truncation
  const finalResults: ScoredNode[] = [];
  let totalTokens = 0;
  for (const scored of fused) {
    const snippetTokens = countTokens(scored.snippet);
    if (totalTokens + snippetTokens > maxTokens && finalResults.length > 0) break;
    finalResults.push(scored);
    totalTokens += snippetTokens;
    if (finalResults.length >= limit) break;
  }

  const seen = new Set<string>();
  const uniqueEdges = allGraphEdges.filter((e) => {
    const key = `${e.from_node}|${e.to_node}|${e.edge_type}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return {
    results: finalResults,
    graphExpansion: uniqueEdges,
    totalResults: finalResults.length,
    totalTokens,
    warnings,
  };
}

function embIdToNodeId(embId: string, graphStore: GraphStore): string | null {
  const docId = embId.includes(":chunk-")
    ? embId.split(":chunk-")[0]!
    : embId.split(":")[0]!;

  for (const prefix of Object.values(KIND_PREFIX)) {
    const candidate = `${prefix}:${docId}`;
    if (graphStore.hasNode(candidate)) return candidate;
  }
  if (graphStore.hasNode(docId)) return docId;
  return null;
}

function kindLayerFilter(
  node: { kind: string; layer: string },
  includeKinds?: KDDKind[],
  includeLayers?: KDDLayer[],
): boolean {
  if (includeKinds && !includeKinds.includes(node.kind as KDDKind)) return false;
  if (includeLayers && !includeLayers.includes(node.layer as KDDLayer)) return false;
  return true;
}

function computeFusionScore(sources: Map<string, number>): number {
  const semantic = sources.get("semantic") ?? 0;
  const graph = sources.get("graph") ?? 0;
  const lexical = sources.get("lexical") ?? 0;

  const sourceCount = [...sources.values()].filter((v) => v > 0).length;
  const bonus = sourceCount > 1 ? 0.1 * (sourceCount - 1) : 0;

  const weighted =
    semantic * WEIGHT_SEMANTIC + graph * WEIGHT_GRAPH + lexical * WEIGHT_LEXICAL + bonus;

  return Math.min(weighted / (WEIGHT_SEMANTIC + WEIGHT_GRAPH + WEIGHT_LEXICAL + 0.2), 1.0);
}

function determineMatchSource(sources: Map<string, number>): string {
  const hasSemantic = (sources.get("semantic") ?? 0) > 0;
  const hasGraph = (sources.get("graph") ?? 0) > 0;

  if (hasSemantic && hasGraph) return "fusion";
  if (hasSemantic) return "semantic";
  if (hasGraph) return "graph";
  return "lexical";
}

function buildSnippet(node: { kind: string; id: string; indexed_fields: Record<string, unknown> }): string {
  const title = node.indexed_fields.title;
  if (title) return `[${node.kind}] ${title}`;
  return `[${node.kind}] ${node.id}`;
}

function countTokens(text: string): number {
  return Math.max(1, Math.floor(text.length / CHARS_PER_TOKEN));
}
