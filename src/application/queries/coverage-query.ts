/**
 * QRY-005 — Governance coverage analysis.
 */

import { EdgeType, KDDKind, type CoverageCategory, type GraphNode } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";

export interface CoverageQueryInput {
  nodeId: string;
}

export interface CoverageQueryResult {
  analyzedNode: GraphNode | undefined;
  categories: CoverageCategory[];
  present: number;
  missing: number;
  coveragePercent: number;
}

type CoverageRule = [name: string, description: string, edgeType: string];

const COVERAGE_RULES: Partial<Record<KDDKind, CoverageRule[]>> = {
  [KDDKind.ENTITY]: [
    ["events", "Domain events emitted by this entity", EdgeType.EMITS],
    ["business_rules", "Business rules for this entity", EdgeType.ENTITY_RULE],
    ["use_cases", "Use cases involving this entity", EdgeType.WIKI_LINK],
  ],
  [KDDKind.COMMAND]: [
    ["events", "Events emitted by this command", EdgeType.EMITS],
    ["use_cases", "Use cases that execute this command", EdgeType.UC_EXECUTES_CMD],
  ],
  [KDDKind.USE_CASE]: [
    ["commands", "Commands executed by this use case", EdgeType.UC_EXECUTES_CMD],
    ["rules", "Business rules applied", EdgeType.UC_APPLIES_RULE],
    ["requirements", "Requirements tracing to this UC", EdgeType.REQ_TRACES_TO],
  ],
  [KDDKind.BUSINESS_RULE]: [
    ["entity", "Entity this rule validates", EdgeType.ENTITY_RULE],
    ["use_cases", "Use cases that apply this rule", EdgeType.UC_APPLIES_RULE],
  ],
  [KDDKind.REQUIREMENT]: [
    ["traces", "Artifacts this requirement traces to", EdgeType.REQ_TRACES_TO],
  ],
};

export function coverageQuery(
  input: CoverageQueryInput,
  graphStore: GraphStore,
): CoverageQueryResult {
  const { nodeId } = input;

  if (!graphStore.hasNode(nodeId)) {
    throw new Error(`NODE_NOT_FOUND: ${nodeId}`);
  }

  const node = graphStore.getNode(nodeId);
  if (!node) throw new Error(`NODE_NOT_FOUND: ${nodeId}`);

  const rules = COVERAGE_RULES[node.kind as KDDKind];
  if (!rules) {
    throw new Error(`UNKNOWN_KIND: no coverage rules for kind '${node.kind}'`);
  }

  const incoming = graphStore.incomingEdges(nodeId);
  const outgoing = graphStore.outgoingEdges(nodeId);
  const allEdges = [...incoming, ...outgoing];

  const categories: CoverageCategory[] = [];
  let present = 0;
  let missing = 0;

  for (const [catName, catDesc, edgeType] of rules) {
    const foundIds: string[] = [];
    for (const edge of allEdges) {
      if (edge.edge_type === edgeType) {
        const other = edge.from_node === nodeId ? edge.to_node : edge.from_node;
        if (!foundIds.includes(other)) {
          foundIds.push(other);
        }
      }
    }

    if (foundIds.length > 0) {
      present++;
      categories.push({ name: catName, description: catDesc, edge_type: edgeType, status: "covered", found: foundIds });
    } else {
      missing++;
      categories.push({ name: catName, description: catDesc, edge_type: edgeType, status: "missing", found: [] });
    }
  }

  const total = present + missing;
  const coveragePercent = total > 0 ? Math.round((present / total) * 1000) / 10 : 0;

  return { analyzedNode: node, categories, present, missing, coveragePercent };
}
