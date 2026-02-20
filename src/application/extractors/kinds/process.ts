import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, findSectionWithChildren, makeNodeId, type Extractor } from "../base.ts";

export class ProcessExtractor implements Extractor {
  kind: KDDKind = KDDKind.PROCESS;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.PROCESS, document.id);
    const fields: Record<string, unknown> = {};

    const participants = findSection(document.sections, "Participantes", "Participants");
    if (participants) fields.participants = participants.content;
    const steps = findSectionWithChildren(document.sections, "Pasos", "Steps");
    if (steps) fields.steps = steps;
    const diagram = findSection(document.sections, "Diagrama", "Diagram");
    if (diagram) fields.mermaid_flow = diagram.content;

    return {
      id: nodeId, kind: KDDKind.PROCESS, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.PROCESS, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
