import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, type Extractor } from "../base.ts";

export class GlossaryExtractor implements Extractor {
  kind: KDDKind = KDDKind.GLOSSARY;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.GLOSSARY, document.id);
    const fields: Record<string, unknown> = {};

    const definition = findSection(document.sections, "Definición", "Definition");
    if (definition) fields.definition = definition.content;
    const context = findSection(document.sections, "Contexto", "Context");
    if (context) fields.context = context.content;
    const related = findSection(document.sections, "Términos Relacionados", "Related Terms");
    if (related) fields.related_terms = related.content;

    return {
      id: nodeId, kind: KDDKind.GLOSSARY, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.GLOSSARY, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
