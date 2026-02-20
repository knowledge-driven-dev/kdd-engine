import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, parseTableRows, type Extractor } from "../base.ts";

export class QueryExtractor implements Extractor {
  kind: KDDKind = KDDKind.QUERY;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.QUERY, document.id);
    const fields: Record<string, unknown> = {};

    const purpose = findSection(document.sections, "Purpose", "Propósito");
    if (purpose) fields.purpose = purpose.content;
    const input = findSection(document.sections, "Input", "Entrada");
    if (input) fields.input_params = parseTableRows(input.content);
    const output = findSection(document.sections, "Output", "Salida");
    if (output) fields.output_structure = output.content;
    const errors = findSection(document.sections, "Possible Errors", "Errores Posibles");
    if (errors) fields.errors = parseTableRows(errors.content);

    return {
      id: nodeId, kind: KDDKind.QUERY, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.QUERY, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
