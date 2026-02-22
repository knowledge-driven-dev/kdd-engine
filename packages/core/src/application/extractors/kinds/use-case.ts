import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, findSectionWithChildren, makeNodeId, resolveWikiLinkToNodeId, type Extractor } from "../base.ts";
import { extractWikiLinks } from "../../../infra/wiki-links.ts";

export class UseCaseExtractor implements Extractor {
  kind: KDDKind = KDDKind.USE_CASE;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.USE_CASE, document.id);
    const fields: Record<string, unknown> = {};

    const desc = findSection(document.sections, "Descripción", "Description");
    if (desc) fields.description = desc.content;
    const actors = findSection(document.sections, "Actores", "Actors");
    if (actors) fields.actors = actors.content;
    const pre = findSection(document.sections, "Precondiciones", "Preconditions");
    if (pre) fields.preconditions = pre.content;
    const flow = findSection(document.sections, "Flujo Principal", "Main Flow");
    if (flow) fields.main_flow = flow.content;
    const alt = findSectionWithChildren(document.sections, "Flujos Alternativos", "Alternative Flows");
    if (alt) fields.alternatives = alt;
    const exc = findSectionWithChildren(document.sections, "Excepciones", "Exceptions");
    if (exc) fields.exceptions = exc;
    const post = findSection(document.sections, "Postcondiciones", "Postconditions");
    if (post) fields.postconditions = post.content;

    return {
      id: nodeId, kind: KDDKind.USE_CASE, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.USE_CASE, document.id);
    const edges: GraphEdge[] = [...buildWikiLinkEdges(document, nodeId, document.layer)];

    // UC_APPLIES_RULE
    const rules = findSection(document.sections, "Reglas Aplicadas", "Applied Rules", "Rules Applied");
    if (rules) {
      for (const link of extractWikiLinks(rules.content)) {
        if (link.target.startsWith("BR-") || link.target.startsWith("BP-") || link.target.startsWith("XP-")) {
          const toNode = resolveWikiLinkToNodeId(link);
          if (toNode) {
            edges.push({
              from_node: nodeId, to_node: toNode, edge_type: "UC_APPLIES_RULE",
              source_file: document.source_path, extraction_method: "wiki_link",
              metadata: {}, layer_violation: false, bidirectional: false,
            });
          }
        }
      }
    }

    // UC_EXECUTES_CMD
    const cmds = findSection(document.sections, "Comandos Ejecutados", "Commands Executed");
    if (cmds) {
      for (const link of extractWikiLinks(cmds.content)) {
        if (link.target.startsWith("CMD-")) {
          const toNode = resolveWikiLinkToNodeId(link);
          if (toNode) {
            edges.push({
              from_node: nodeId, to_node: toNode, edge_type: "UC_EXECUTES_CMD",
              source_file: document.source_path, extraction_method: "wiki_link",
              metadata: {}, layer_violation: false, bidirectional: false,
            });
          }
        }
      }
    }

    // UC_STORY from OBJ-* links anywhere
    const fullContent = document.sections.map((s) => s.content).join("\n");
    for (const link of extractWikiLinks(fullContent)) {
      if (link.target.startsWith("OBJ-")) {
        const toNode = resolveWikiLinkToNodeId(link);
        if (toNode) {
          edges.push({
            from_node: nodeId, to_node: toNode, edge_type: "UC_STORY",
            source_file: document.source_path, extraction_method: "wiki_link",
            metadata: {}, layer_violation: false, bidirectional: false,
          });
        }
      }
    }

    return deduplicateEdges(edges);
  }
}
