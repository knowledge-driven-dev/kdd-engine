import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, type Extractor } from "../base.ts";

export class RequirementExtractor implements Extractor {
  kind: KDDKind = KDDKind.REQUIREMENT;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.REQUIREMENT, document.id);
    const fields: Record<string, unknown> = {};

    const desc = findSection(document.sections, "Descripción", "Description");
    if (desc) fields.description = desc.content;
    const criteria = findSection(document.sections, "Criterios de Aceptación", "Acceptance Criteria");
    if (criteria) fields.acceptance_criteria = criteria.content;
    const trace = findSection(document.sections, "Trazabilidad", "Traceability");
    if (trace) fields.traceability = trace.content;

    return {
      id: nodeId, kind: KDDKind.REQUIREMENT, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.REQUIREMENT, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
