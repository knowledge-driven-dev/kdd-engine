/**
 * QRY-006 — Layer violation detection.
 */

import { KDDLayer, type GraphEdge, type KDDKind, type LayerViolation } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";

export interface ViolationsQueryInput {
  includeKinds?: KDDKind[];
  includeLayers?: KDDLayer[];
}

export interface ViolationsQueryResult {
  violations: LayerViolation[];
  totalViolations: number;
  totalEdgesAnalyzed: number;
  violationRate: number;
}

export function violationsQuery(
  input: ViolationsQueryInput,
  graphStore: GraphStore,
): ViolationsQueryResult {
  const { includeKinds, includeLayers } = input;

  const allEdges = graphStore.allEdges();
  let violationEdges = graphStore.findViolations();

  if (includeKinds || includeLayers) {
    violationEdges = violationEdges.filter((edge) => {
      const fromNode = graphStore.getNode(edge.from_node);
      const toNode = graphStore.getNode(edge.to_node);

      if (includeKinds) {
        const fromMatch = fromNode && includeKinds.includes(fromNode.kind as KDDKind);
        const toMatch = toNode && includeKinds.includes(toNode.kind as KDDKind);
        if (!fromMatch && !toMatch) return false;
      }

      if (includeLayers) {
        const fromMatch = fromNode && includeLayers.includes(fromNode.layer as KDDLayer);
        const toMatch = toNode && includeLayers.includes(toNode.layer as KDDLayer);
        if (!fromMatch && !toMatch) return false;
      }

      return true;
    });
  }

  const violations: LayerViolation[] = violationEdges.map((edge) => {
    const fromNode = graphStore.getNode(edge.from_node);
    const toNode = graphStore.getNode(edge.to_node);
    return {
      from_node: edge.from_node,
      to_node: edge.to_node,
      from_layer: fromNode?.layer as KDDLayer ?? KDDLayer.DOMAIN,
      to_layer: toNode?.layer as KDDLayer ?? KDDLayer.DOMAIN,
      edge_type: edge.edge_type,
    };
  });

  const total = allEdges.length;
  const rate = total > 0 ? Math.round((violations.length / total) * 10000) / 100 : 0;

  return {
    violations,
    totalViolations: violations.length,
    totalEdgesAnalyzed: total,
    violationRate: rate,
  };
}
