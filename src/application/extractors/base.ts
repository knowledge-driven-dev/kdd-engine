/**
 * Base extractor protocol and shared helpers.
 */

import type { GraphEdge, GraphNode, KDDDocument, KDDKind, KDDLayer, Section } from "../../domain/types.ts";
import { KIND_PREFIX, KDDLayer as Layers, LAYER_NUMERIC } from "../../domain/types.ts";
import { isLayerViolation } from "../../domain/rules.ts";
import { extractWikiLinks, type WikiLink } from "../../infra/wiki-links.ts";

export interface Extractor {
  kind: KDDKind;
  extractNode(document: KDDDocument): GraphNode;
  extractEdges(document: KDDDocument): GraphEdge[];
}

export function makeNodeId(kind: KDDKind, documentId: string): string {
  const prefix = KIND_PREFIX[kind] ?? kind.toUpperCase();
  return `${prefix}:${documentId}`;
}

export function findSection(sections: Section[], ...names: string[]): Section | null {
  const targets = new Set(names.map((n) => n.toLowerCase()));
  for (const s of sections) {
    if (targets.has(s.heading.toLowerCase())) return s;
  }
  return null;
}

export function findSections(sections: Section[], ...names: string[]): Section[] {
  const targets = new Set(names.map((n) => n.toLowerCase()));
  return sections.filter((s) => targets.has(s.heading.toLowerCase()));
}

export function findSectionWithChildren(
  sections: Section[],
  ...names: string[]
): string | null {
  const targets = new Set(names.map((n) => n.toLowerCase()));
  let parentIdx: number | null = null;
  let parentLevel = 0;

  for (let i = 0; i < sections.length; i++) {
    if (targets.has(sections[i]!.heading.toLowerCase())) {
      parentIdx = i;
      parentLevel = sections[i]!.level;
      break;
    }
  }

  if (parentIdx === null) return null;

  const parts: string[] = [];
  const parent = sections[parentIdx]!;
  if (parent.content.trim()) parts.push(parent.content);

  for (let i = parentIdx + 1; i < sections.length; i++) {
    const s = sections[i]!;
    if (s.level <= parentLevel) break;
    parts.push(`### ${s.heading}\n\n${s.content}`);
  }

  return parts.length > 0 ? parts.join("\n\n") : null;
}

export function resolveWikiLinkToNodeId(link: WikiLink): string | null {
  const t = link.target;
  const prefixMap: [string, string][] = [
    ["EVT-", "Event"],
    ["BR-", "BR"],
    ["BP-", "BP"],
    ["XP-", "XP"],
    ["CMD-", "CMD"],
    ["QRY-", "QRY"],
    ["UC-", "UC"],
    ["PROC-", "PROC"],
    ["REQ-", "REQ"],
    ["OBJ-", "OBJ"],
    ["ADR-", "ADR"],
    ["PRD-", "PRD"],
    ["UI-", "UIView"],
  ];
  for (const [prefix, nodePrefix] of prefixMap) {
    if (t.startsWith(prefix)) return `${nodePrefix}:${t}`;
  }
  return `Entity:${t}`;
}

export function buildWikiLinkEdges(
  document: KDDDocument,
  fromNodeId: string,
  fromLayer: KDDLayer,
): GraphEdge[] {
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();

  const fullContent = document.sections.map((s) => s.content).join("\n");
  const links = extractWikiLinks(fullContent);

  for (const link of links) {
    const toNodeId = resolveWikiLinkToNodeId(link);
    if (!toNodeId) continue;
    const key = `${fromNodeId}|${toNodeId}`;
    if (seen.has(key)) continue;
    seen.add(key);

    const destLayer = guessLayerFromNodeId(toNodeId);
    let violation = false;
    if (destLayer) violation = isLayerViolation(fromLayer, destLayer);

    const metadata: Record<string, unknown> = {};
    if (link.domain) metadata.domain = link.domain;
    if (link.alias) metadata.display_alias = link.alias;

    edges.push({
      from_node: fromNodeId,
      to_node: toNodeId,
      edge_type: "WIKI_LINK",
      source_file: document.source_path,
      extraction_method: "wiki_link",
      metadata,
      layer_violation: violation,
      bidirectional: true,
    });
  }

  return edges;
}

function guessLayerFromNodeId(nodeId: string): KDDLayer | null {
  const prefix = nodeId.includes(":") ? nodeId.split(":")[0]! : "";
  const layerMap: Record<string, KDDLayer> = {
    Entity: Layers.DOMAIN,
    Event: Layers.DOMAIN,
    BR: Layers.DOMAIN,
    BP: Layers.BEHAVIOR,
    XP: Layers.BEHAVIOR,
    CMD: Layers.BEHAVIOR,
    QRY: Layers.BEHAVIOR,
    PROC: Layers.BEHAVIOR,
    UC: Layers.BEHAVIOR,
    UIView: Layers.EXPERIENCE,
    UIComp: Layers.EXPERIENCE,
    REQ: Layers.VERIFICATION,
    OBJ: Layers.REQUIREMENTS,
    PRD: Layers.REQUIREMENTS,
    ADR: Layers.REQUIREMENTS,
    GLOSS: Layers.DOMAIN,
  };
  return layerMap[prefix] ?? null;
}

// ── Shared table/list parsing helpers ───────────────────────────────

export function parseTableRows(content: string): Record<string, string>[] {
  const lines = content
    .trim()
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("|"));

  if (lines.length < 2) return [];

  const headers = lines[0]!
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((h) => h.trim().replace(/`/g, ""));

  const rows: Record<string, string>[] = [];
  for (const line of lines.slice(2)) {
    const cells = line
      .replace(/^\||\|$/g, "")
      .split("|")
      .map((c) => c.trim());
    if (cells.length >= headers.length) {
      const row: Record<string, string> = {};
      headers.forEach((h, i) => (row[h] = cells[i]!));
      rows.push(row);
    }
  }
  return rows;
}

export function parseListItems(content: string): string[] {
  return content
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("- ") || l.startsWith("* "))
    .map((l) => l.slice(2).trim());
}

export function deduplicateEdges(edges: GraphEdge[]): GraphEdge[] {
  const seen = new Set<string>();
  return edges.filter((e) => {
    const key = `${e.from_node}|${e.to_node}|${e.edge_type}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** Check if a wiki-link target looks like an entity (not a prefixed spec). */
export function isEntityTarget(target: string): boolean {
  const specPrefixes = [
    "EVT-", "BR-", "BP-", "XP-", "CMD-", "QRY-",
    "UC-", "PROC-", "REQ-", "OBJ-", "ADR-", "PRD-", "UI-",
  ];
  return !specPrefixes.some((p) => target.startsWith(p));
}
