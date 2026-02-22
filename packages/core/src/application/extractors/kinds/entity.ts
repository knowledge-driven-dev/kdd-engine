/**
 * Entity extractor — kind: entity
 */

import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import {
  buildWikiLinkEdges,
  deduplicateEdges,
  findSection,
  makeNodeId,
  parseListItems,
  parseTableRows,
  resolveWikiLinkToNodeId,
  type Extractor,
} from "../base.ts";
import { extractWikiLinks } from "../../../infra/wiki-links.ts";

export class EntityExtractor implements Extractor {
  kind: KDDKind = KDDKind.ENTITY;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.ENTITY, document.id);
    const fields: Record<string, unknown> = {};

    const desc = findSection(document.sections, "Descripción", "Description");
    if (desc) fields.description = desc.content;

    const attr = findSection(document.sections, "Atributos", "Attributes");
    if (attr) fields.attributes = parseTableRows(attr.content);

    const rel = findSection(document.sections, "Relaciones", "Relations", "Relationships");
    if (rel) fields.relations = parseTableRows(rel.content);

    const inv = findSection(document.sections, "Invariantes", "Invariants", "Constraints");
    if (inv) fields.invariants = parseListItems(inv.content);

    const sm = findSection(document.sections, "Ciclo de Vida", "Lifecycle", "State Machine");
    if (sm) fields.state_machine = sm.content;

    return {
      id: nodeId,
      kind: KDDKind.ENTITY,
      source_file: document.source_path,
      source_hash: document.source_hash,
      layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain,
      indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.ENTITY, document.id);
    const edges: GraphEdge[] = [];

    edges.push(...buildWikiLinkEdges(document, nodeId, document.layer));

    // DOMAIN_RELATION from relations table
    const rel = findSection(document.sections, "Relaciones", "Relations", "Relationships");
    if (rel) {
      const rows = parseTableRows(rel.content);
      for (const row of rows) {
        let target: string | null = null;
        for (const val of Object.values(row)) {
          const links = extractWikiLinks(val);
          if (links.length > 0) {
            target = resolveWikiLinkToNodeId(links[0]!);
            break;
          }
        }
        if (!target) continue;
        const relName = Object.values(row)[0] ?? "";
        const cardinality = row["Cardinalidad"] ?? row["Cardinality"] ?? "";
        edges.push({
          from_node: nodeId,
          to_node: target,
          edge_type: "DOMAIN_RELATION",
          source_file: document.source_path,
          extraction_method: "section_content",
          metadata: { relation: relName, cardinality },
          layer_violation: false,
          bidirectional: false,
        });
      }
    }

    // EMITS from lifecycle events
    for (const section of document.sections) {
      const h = section.heading.toLowerCase();
      if (h === "eventos del ciclo de vida" || h === "lifecycle events") {
        const links = extractWikiLinks(section.content);
        for (const link of links) {
          if (link.target.startsWith("EVT-")) {
            const toNode = resolveWikiLinkToNodeId(link);
            if (toNode) {
              edges.push({
                from_node: nodeId,
                to_node: toNode,
                edge_type: "EMITS",
                source_file: document.source_path,
                extraction_method: "wiki_link",
                metadata: {},
                layer_violation: false,
                bidirectional: false,
              });
            }
          }
        }
      }
    }

    return deduplicateEdges(edges);
  }
}
