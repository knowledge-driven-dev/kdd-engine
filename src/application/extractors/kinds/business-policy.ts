import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, isEntityTarget, makeNodeId, resolveWikiLinkToNodeId, type Extractor } from "../base.ts";
import { extractWikiLinks } from "../../../infra/wiki-links.ts";

export class BusinessPolicyExtractor implements Extractor {
  kind: KDDKind = KDDKind.BUSINESS_POLICY;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.BUSINESS_POLICY, document.id);
    const fields: Record<string, unknown> = {};

    const decl = findSection(document.sections, "Declaración", "Declaration");
    if (decl) fields.declaration = decl.content;
    const when = findSection(document.sections, "Cuándo Aplica", "When Applies");
    if (when) fields.when_applies = when.content;
    const params = findSection(document.sections, "Parámetros", "Parameters");
    if (params) fields.parameters = params.content;
    const violation = findSection(document.sections, "Qué pasa si se incumple", "Violation", "What Happens on Violation");
    if (violation) fields.violation = violation.content;

    return {
      id: nodeId, kind: KDDKind.BUSINESS_POLICY, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.BUSINESS_POLICY, document.id);
    const edges: GraphEdge[] = [...buildWikiLinkEdges(document, nodeId, document.layer)];

    const decl = findSection(document.sections, "Declaración", "Declaration");
    if (decl) {
      for (const link of extractWikiLinks(decl.content)) {
        if (isEntityTarget(link.target)) {
          const toNode = resolveWikiLinkToNodeId(link);
          if (toNode) {
            edges.push({
              from_node: nodeId, to_node: toNode, edge_type: "ENTITY_RULE",
              source_file: document.source_path, extraction_method: "wiki_link",
              metadata: {}, layer_violation: false, bidirectional: false,
            });
          }
        }
      }
    }

    return deduplicateEdges(edges);
  }
}
