import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, type Extractor } from "../base.ts";

export class UIViewExtractor implements Extractor {
  kind: KDDKind = KDDKind.UI_VIEW;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.UI_VIEW, document.id);
    const fields: Record<string, unknown> = {};

    const desc = findSection(document.sections, "Descripción", "Description");
    if (desc) fields.description = desc.content;
    const layout = findSection(document.sections, "Layout", "Diseño");
    if (layout) fields.layout = layout.content;
    const components = findSection(document.sections, "Componentes", "Components");
    if (components) fields.components = components.content;
    const states = findSection(document.sections, "Estados", "States");
    if (states) fields.states = states.content;
    const behavior = findSection(document.sections, "Comportamiento", "Behavior");
    if (behavior) fields.behavior = behavior.content;

    return {
      id: nodeId, kind: KDDKind.UI_VIEW, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.UI_VIEW, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
