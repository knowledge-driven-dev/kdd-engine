import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, isEntityTarget, makeNodeId, resolveWikiLinkToNodeId, type Extractor } from "../base.ts";
import { extractWikiLinks } from "../../../infra/wiki-links.ts";

export class CrossPolicyExtractor implements Extractor {
  kind: KDDKind = KDDKind.CROSS_POLICY;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.CROSS_POLICY, document.id);
    const fields: Record<string, unknown> = {};

    const purpose = findSection(document.sections, "Propósito", "Purpose");
    if (purpose) fields.purpose = purpose.content;
    const decl = findSection(document.sections, "Declaración", "Declaration");
    if (decl) fields.declaration = decl.content;
    const formal = findSection(document.sections, "Formalización EARS", "EARS Formalization");
    if (formal) fields.formalization_ears = formal.content;
    const behavior = findSection(document.sections, "Comportamiento Estándar", "Standard Behavior");
    if (behavior) fields.standard_behavior = behavior.content;

    return {
      id: nodeId, kind: KDDKind.CROSS_POLICY, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.CROSS_POLICY, document.id);
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
