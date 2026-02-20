/**
 * QRY-001 — Graph traversal from a root node.
 */

import type { GraphEdge, GraphNode, KDDKind, ScoredNode } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";

export interface GraphQueryInput {
  rootNode: string;
  depth?: number;
  edgeTypes?: string[];
  includeKinds?: KDDKind[];
  respectLayers?: boolean;
}

export interface GraphQueryResult {
  centerNode: GraphNode | undefined;
  relatedNodes: ScoredNode[];
  edges: GraphEdge[];
  totalNodes: number;
  totalEdges: number;
}

export function graphQuery(
  input: GraphQueryInput,
  graphStore: GraphStore,
): GraphQueryResult {
  const { rootNode, depth = 2, edgeTypes, includeKinds, respectLayers = true } = input;

  if (!graphStore.hasNode(rootNode)) {
    throw new Error(`NODE_NOT_FOUND: ${rootNode}`);
  }

  let [nodes, edges] = graphStore.traverse(rootNode, depth, edgeTypes, respectLayers);

  if (includeKinds) {
    const kindSet = new Set(includeKinds);
    nodes = nodes.filter((n) => kindSet.has(n.kind));
  }

  const center = graphStore.getNode(rootNode);

  const scored: ScoredNode[] = [];
  for (const node of nodes) {
    if (node.id === rootNode) continue;
    const dist = estimateDistance(node.id, rootNode, edges);
    const score = 1.0 / (1.0 + dist);
    scored.push({
      node_id: node.id,
      score,
      snippet: buildSnippet(node),
      match_source: "graph",
    });
  }

  scored.sort((a, b) => b.score - a.score);

  return {
    centerNode: center,
    relatedNodes: scored,
    edges,
    totalNodes: scored.length + (center ? 1 : 0),
    totalEdges: edges.length,
  };
}

function estimateDistance(
  nodeId: string,
  rootId: string,
  edges: GraphEdge[],
): number {
  const adj = new Map<string, Set<string>>();
  for (const e of edges) {
    if (!adj.has(e.from_node)) adj.set(e.from_node, new Set());
    adj.get(e.from_node)!.add(e.to_node);
    if (!adj.has(e.to_node)) adj.set(e.to_node, new Set());
    adj.get(e.to_node)!.add(e.from_node);
  }

  const visited = new Set<string>([rootId]);
  const queue: Array<[string, number]> = [[rootId, 0]];

  while (queue.length > 0) {
    const [current, dist] = queue.shift()!;
    if (current === nodeId) return dist;
    for (const neighbor of adj.get(current) ?? []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push([neighbor, dist + 1]);
      }
    }
  }

  return 999;
}

function buildSnippet(node: GraphNode): string {
  const title = node.indexed_fields.title;
  if (title) return `[${node.kind}] ${title}`;
  return `[${node.kind}] ${node.id}`;
}
