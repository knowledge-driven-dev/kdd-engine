/**
 * QRY-004 — Impact analysis (reverse BFS).
 */

import { EdgeType, type GraphEdge, type GraphNode } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";

export interface ImpactQueryInput {
  nodeId: string;
  changeType?: string;
  depth?: number;
}

export interface AffectedNode {
  node_id: string;
  kind: string;
  edge_type: string;
  impact_description: string;
}

export interface TransitivelyAffected {
  node_id: string;
  kind: string;
  path: string[];
  edge_types: string[];
}

export interface ScenarioToRerun {
  node_id: string;
  scenario_name: string;
  reason: string;
}

export interface ImpactQueryResult {
  analyzedNode: GraphNode | undefined;
  directlyAffected: AffectedNode[];
  transitivelyAffected: TransitivelyAffected[];
  scenariosToRerun: ScenarioToRerun[];
  totalDirectly: number;
  totalTransitively: number;
}

export function impactQuery(
  input: ImpactQueryInput,
  graphStore: GraphStore,
): ImpactQueryResult {
  const { nodeId, changeType = "modify_attribute", depth = 3 } = input;

  if (!graphStore.hasNode(nodeId)) {
    throw new Error(`NODE_NOT_FOUND: ${nodeId}`);
  }

  const analyzed = graphStore.getNode(nodeId);

  // Phase 1: Direct dependents (incoming edges)
  const directEdges = graphStore.incomingEdges(nodeId);
  const directlyAffected: AffectedNode[] = [];
  const directIds = new Set<string>();

  for (const edge of directEdges) {
    const predNode = graphStore.getNode(edge.from_node);
    if (!predNode) continue;
    directIds.add(predNode.id);
    directlyAffected.push({
      node_id: predNode.id,
      kind: predNode.kind,
      edge_type: edge.edge_type,
      impact_description: describeImpact(edge, changeType),
    });
  }

  // Phase 2: Transitive dependents
  const transitivelyAffected: TransitivelyAffected[] = [];
  if (depth > 1) {
    const reverseResults = graphStore.reverseTraverse(nodeId, depth);
    for (const [node, pathEdges] of reverseResults) {
      if (directIds.has(node.id) || node.id === nodeId) continue;
      const pathIds = [nodeId];
      const edgeTypes: string[] = [];
      for (const e of pathEdges) {
        pathIds.push(e.from_node);
        edgeTypes.push(e.edge_type);
      }
      transitivelyAffected.push({
        node_id: node.id,
        kind: node.kind,
        path: pathIds,
        edge_types: edgeTypes,
      });
    }
  }

  // Phase 3: Find BDD scenarios
  const scenarios: ScenarioToRerun[] = [];
  const allAffectedIds = new Set([
    ...directIds,
    ...transitivelyAffected.map((t) => t.node_id),
    nodeId,
  ]);

  for (const edge of graphStore.allEdges()) {
    if (edge.edge_type === EdgeType.VALIDATES && allAffectedIds.has(edge.to_node)) {
      const featureNode = graphStore.getNode(edge.from_node);
      if (featureNode) {
        scenarios.push({
          node_id: featureNode.id,
          scenario_name: (featureNode.indexed_fields.title as string) ?? featureNode.id,
          reason: `Validates ${edge.to_node} which is affected`,
        });
      }
    }
  }

  return {
    analyzedNode: analyzed,
    directlyAffected,
    transitivelyAffected,
    scenariosToRerun: scenarios,
    totalDirectly: directlyAffected.length,
    totalTransitively: transitivelyAffected.length,
  };
}

const IMPACT_DESC: Record<string, string> = {
  ENTITY_RULE: "Business rule validates this entity",
  UC_APPLIES_RULE: "Use case applies this rule",
  UC_EXECUTES_CMD: "Use case executes this command",
  EMITS: "Emits this event",
  CONSUMES: "Consumes this event",
  WIKI_LINK: "References this artifact",
  DOMAIN_RELATION: "Has a domain relationship",
  REQ_TRACES_TO: "Requirement traces to this artifact",
  VALIDATES: "Validates this artifact via BDD scenarios",
};

function describeImpact(edge: GraphEdge, changeType: string): string {
  const desc = IMPACT_DESC[edge.edge_type] ?? `Connected via ${edge.edge_type}`;
  return `${desc} — change type: ${changeType}`;
}
