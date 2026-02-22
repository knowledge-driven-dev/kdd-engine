import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, type Extractor } from "../base.ts";

export class ADRExtractor implements Extractor {
  kind: KDDKind = KDDKind.ADR;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.ADR, document.id);
    const fields: Record<string, unknown> = {};

    const context = findSection(document.sections, "Contexto", "Context");
    if (context) fields.context = context.content;
    const decision = findSection(document.sections, "Decisión", "Decision");
    if (decision) fields.decision = decision.content;
    const consequences = findSection(document.sections, "Consecuencias", "Consequences");
    if (consequences) fields.consequences = consequences.content;

    return {
      id: nodeId, kind: KDDKind.ADR, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.ADR, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
