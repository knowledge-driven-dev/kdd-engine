/**
 * Graph store — graphology wrapper with BFS, reverse traversal, text search.
 */

import Graph from "graphology";
import type { GraphEdge, GraphNode, OrphanEdge } from "../domain/types.ts";

export class GraphStore {
  private graph = new Graph({ multi: true, type: "directed" });
  private nodes = new Map<string, GraphNode>();
  private _orphanEdges: OrphanEdge[] = [];

  load(nodes: GraphNode[], edges: GraphEdge[]): void {
    this.graph.clear();
    this.nodes.clear();
    this._orphanEdges = [];

    for (const node of nodes) {
      this.graph.addNode(node.id, { data: node });
      this.nodes.set(node.id, node);
    }

    for (const edge of edges) {
      const fromExists = this.graph.hasNode(edge.from_node);
      const toExists = this.graph.hasNode(edge.to_node);
      if (!fromExists || !toExists) {
        this._orphanEdges.push(toOrphanEdge(edge, fromExists, toExists));
        continue;
      }
      const key = `${edge.from_node}→${edge.to_node}:${edge.edge_type}`;
      if (!this.graph.hasEdge(key)) {
        this.graph.addEdgeWithKey(key, edge.from_node, edge.to_node, { data: edge });
      }
    }
  }

  addNode(node: GraphNode): void {
    if (this.graph.hasNode(node.id)) {
      this.graph.replaceNodeAttributes(node.id, { data: node });
    } else {
      this.graph.addNode(node.id, { data: node });
    }
    this.nodes.set(node.id, node);
  }

  addEdge(edge: GraphEdge): void {
    const fromExists = this.graph.hasNode(edge.from_node);
    const toExists = this.graph.hasNode(edge.to_node);
    if (!fromExists || !toExists) {
      this._orphanEdges.push(toOrphanEdge(edge, fromExists, toExists));
      return;
    }
    const key = `${edge.from_node}→${edge.to_node}:${edge.edge_type}`;
    if (!this.graph.hasEdge(key)) {
      this.graph.addEdgeWithKey(key, edge.from_node, edge.to_node, { data: edge });
    }
  }

  traverse(
    root: string,
    depth: number,
    edgeTypes?: string[],
    respectLayers = true,
  ): [GraphNode[], GraphEdge[]] {
    if (!this.graph.hasNode(root)) return [[], []];

    const visited = new Set<string>([root]);
    const collectedEdges: GraphEdge[] = [];
    const queue: Array<[string, number]> = [[root, 0]];

    while (queue.length > 0) {
      const [current, dist] = queue.shift()!;
      if (dist >= depth) continue;

      this.graph.forEachOutEdge(current, (_edgeKey, attrs, _src, target) => {
        const edge: GraphEdge = attrs.data;
        if (!edgeMatches(edge, edgeTypes, respectLayers)) return;
        collectedEdges.push(edge);
        if (!visited.has(target)) {
          visited.add(target);
          queue.push([target, dist + 1]);
        }
      });

      this.graph.forEachInEdge(current, (_edgeKey, attrs, source) => {
        const edge: GraphEdge = attrs.data;
        if (!edgeMatches(edge, edgeTypes, respectLayers)) return;
        collectedEdges.push(edge);
        if (!visited.has(source)) {
          visited.add(source);
          queue.push([source, dist + 1]);
        }
      });
    }

    const resultNodes = [...visited]
      .map((id) => this.nodes.get(id))
      .filter((n): n is GraphNode => n != null);

    const seen = new Set<string>();
    const uniqueEdges = collectedEdges.filter((e) => {
      const key = `${e.from_node}|${e.to_node}|${e.edge_type}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    return [resultNodes, uniqueEdges];
  }

  reverseTraverse(
    root: string,
    depth: number,
  ): Array<[GraphNode, GraphEdge[]]> {
    if (!this.graph.hasNode(root)) return [];

    const results: Array<[GraphNode, GraphEdge[]]> = [];
    const visited = new Set<string>([root]);
    const queue: Array<[string, number, GraphEdge[]]> = [[root, 0, []]];

    while (queue.length > 0) {
      const [current, dist, path] = queue.shift()!;
      if (dist >= depth) continue;

      this.graph.forEachInEdge(current, (_edgeKey, attrs, source) => {
        if (visited.has(source)) return;
        visited.add(source);
        const edge: GraphEdge = attrs.data;
        const newPath = [...path, edge];
        const predNode = this.nodes.get(source);
        if (predNode) {
          results.push([predNode, newPath]);
        }
        queue.push([source, dist + 1, newPath]);
      });
    }

    return results;
  }

  textSearch(query: string, fields?: string[]): GraphNode[] {
    const queryLower = query.toLowerCase();
    const results: GraphNode[] = [];

    for (const node of this.nodes.values()) {
      if (nodeMatchesText(node, queryLower, fields)) {
        results.push(node);
      }
    }

    return results;
  }

  getNode(id: string): GraphNode | undefined {
    return this.nodes.get(id);
  }

  hasNode(id: string): boolean {
    return this.nodes.has(id);
  }

  incomingEdges(nodeId: string): GraphEdge[] {
    if (!this.graph.hasNode(nodeId)) return [];
    const edges: GraphEdge[] = [];
    this.graph.forEachInEdge(nodeId, (_key, attrs) => {
      edges.push(attrs.data as GraphEdge);
    });
    return edges;
  }

  outgoingEdges(nodeId: string): GraphEdge[] {
    if (!this.graph.hasNode(nodeId)) return [];
    const edges: GraphEdge[] = [];
    this.graph.forEachOutEdge(nodeId, (_key, attrs) => {
      edges.push(attrs.data as GraphEdge);
    });
    return edges;
  }

  allEdges(): GraphEdge[] {
    const edges: GraphEdge[] = [];
    this.graph.forEachEdge((_key, attrs) => {
      edges.push(attrs.data as GraphEdge);
    });
    return edges;
  }

  allNodes(): GraphNode[] {
    return [...this.nodes.values()];
  }

  nodeCount(): number {
    return this.nodes.size;
  }

  edgeCount(): number {
    return this.graph.size;
  }

  findViolations(): GraphEdge[] {
    return this.allEdges().filter((e) => e.layer_violation);
  }

  orphanEdges(): OrphanEdge[] {
    return this._orphanEdges;
  }
}

function edgeMatches(
  edge: GraphEdge,
  edgeTypes: string[] | undefined,
  respectLayers: boolean,
): boolean {
  if (respectLayers && edge.layer_violation) return false;
  if (edgeTypes != null && !edgeTypes.includes(edge.edge_type)) return false;
  return true;
}

function toOrphanEdge(edge: GraphEdge, fromExists: boolean, toExists: boolean): OrphanEdge {
  const reason = !fromExists && !toExists
    ? "both_missing"
    : !fromExists
      ? "missing_source"
      : "missing_target";
  return {
    from_node: edge.from_node,
    to_node: edge.to_node,
    edge_type: edge.edge_type,
    source_file: edge.source_file,
    from_exists: fromExists,
    to_exists: toExists,
    reason,
  };
}

function nodeMatchesText(
  node: GraphNode,
  queryLower: string,
  fields?: string[],
): boolean {
  let searchValues: string[];

  if (fields) {
    searchValues = Object.entries(node.indexed_fields)
      .filter(([k, v]) => fields.includes(k) && v != null)
      .map(([, v]) => String(v));
  } else {
    searchValues = Object.values(node.indexed_fields)
      .filter((v) => v != null)
      .map((v) => String(v));
  }

  searchValues.push(node.id);
  searchValues.push(...node.aliases);

  return searchValues.some((val) => val.toLowerCase().includes(queryLower));
}
