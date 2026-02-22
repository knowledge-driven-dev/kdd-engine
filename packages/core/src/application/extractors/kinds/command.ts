import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, makeNodeId, parseTableRows, resolveWikiLinkToNodeId, type Extractor } from "../base.ts";
import { extractWikiLinks } from "../../../infra/wiki-links.ts";

export class CommandExtractor implements Extractor {
  kind: KDDKind = KDDKind.COMMAND;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.COMMAND, document.id);
    const fields: Record<string, unknown> = {};

    const purpose = findSection(document.sections, "Purpose", "Propósito");
    if (purpose) fields.purpose = purpose.content;
    const input = findSection(document.sections, "Input", "Entrada");
    if (input) fields.input_params = parseTableRows(input.content);
    const pre = findSection(document.sections, "Preconditions", "Precondiciones");
    if (pre) fields.preconditions = pre.content;
    const post = findSection(document.sections, "Postconditions", "Postcondiciones");
    if (post) fields.postconditions = post.content;
    const errors = findSection(document.sections, "Possible Errors", "Errores Posibles");
    if (errors) fields.errors = parseTableRows(errors.content);

    return {
      id: nodeId, kind: KDDKind.COMMAND, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.COMMAND, document.id);
    const edges: GraphEdge[] = [...buildWikiLinkEdges(document, nodeId, document.layer)];

    const post = findSection(document.sections, "Postconditions", "Postcondiciones");
    if (post) {
      for (const link of extractWikiLinks(post.content)) {
        if (link.target.startsWith("EVT-")) {
          const toNode = resolveWikiLinkToNodeId(link);
          if (toNode) {
            edges.push({
              from_node: nodeId, to_node: toNode, edge_type: "EMITS",
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
