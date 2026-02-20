import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, type Extractor } from "../base.ts";

export class ObjectiveExtractor implements Extractor {
  kind: KDDKind = KDDKind.OBJECTIVE;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.OBJECTIVE, document.id);
    const fields: Record<string, unknown> = {};

    const actor = findSection(document.sections, "Actor", "Actors");
    if (actor) fields.actor = actor.content;
    const objective = findSection(document.sections, "Objetivo", "Objective");
    if (objective) fields.objective = objective.content;
    const criteria = findSection(document.sections, "Criterios de éxito", "Success Criteria");
    if (criteria) fields.success_criteria = criteria.content;

    return {
      id: nodeId, kind: KDDKind.OBJECTIVE, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.OBJECTIVE, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
