import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, type Extractor } from "../base.ts";

export class UIComponentExtractor implements Extractor {
  kind: KDDKind = KDDKind.UI_COMPONENT;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.UI_COMPONENT, document.id);
    const fields: Record<string, unknown> = {};

    const desc = findSection(document.sections, "Descripción", "Description");
    if (desc) fields.description = desc.content;
    const entities = findSection(document.sections, "Entidades", "Entities");
    if (entities) fields.entities = entities.content;
    const useCases = findSection(document.sections, "Casos de Uso", "Use Cases");
    if (useCases) fields.use_cases = useCases.content;

    return {
      id: nodeId, kind: KDDKind.UI_COMPONENT, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.UI_COMPONENT, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
