import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, parseTableRows, type Extractor } from "../base.ts";

export class EventExtractor implements Extractor {
  kind: KDDKind = KDDKind.EVENT;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.EVENT, document.id);
    const fields: Record<string, unknown> = {};

    const desc = findSection(document.sections, "Descripción", "Description");
    if (desc) fields.description = desc.content;
    const payload = findSection(document.sections, "Payload");
    if (payload) fields.payload = parseTableRows(payload.content);
    const producer = findSection(document.sections, "Productor", "Producer");
    if (producer) fields.producer = producer.content;
    const consumers = findSection(document.sections, "Consumidores", "Consumers");
    if (consumers) fields.consumers = consumers.content;

    return {
      id: nodeId, kind: KDDKind.EVENT, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.EVENT, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
