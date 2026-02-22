/**
 * QRY-007 — RetrieveContext ("Amplificador de Contexto").
 *
 * Given hints (file paths, entity names, keywords), returns KDD artifacts
 * the agent should know before modifying code: business rules, policies,
 * invariants, preconditions, expected behavior — prioritized by kind.
 */

import { KIND_PREFIX, type GraphNode } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";

// ── Interfaces ───────────────────────────────────────────────────────

export interface ContextQueryInput {
  hints: string[];
  depth?: number;
  maxTokens?: number;
}

export interface ContextItem {
  node_id: string;
  kind: string;
  content: string;
  source_file: string;
  reached_via: string;
}

export interface ResolvedEntity {
  node_id: string;
  matched_from: string;
  match_method: "exact" | "basename" | "text_search";
}

export interface ContextResult {
  constraints: ContextItem[];
  behavior: ContextItem[];
  resolvedEntities: ResolvedEntity[];
  warnings: string[];
  totalItems: number;
  totalTokens: number;
}

// ── Priority tiers (lower = higher priority) ─────────────────────────

const CONSTRAINT_KINDS = new Set([
  "business-rule",
  "business-policy",
  "cross-policy",
]);

const ENTITY_KIND = "entity";

const BEHAVIOR_KINDS = new Set([
  "command",
  "use-case",
  "requirement",
]);

/** Sort key: constraints first, then entity invariants, then behavior. */
function kindPriority(kind: string): number {
  if (CONSTRAINT_KINDS.has(kind)) return 0;
  if (kind === ENTITY_KIND) return 1;
  if (BEHAVIOR_KINDS.has(kind)) return 2;
  return 3;
}

// ── All known prefixes (for hint resolution) ─────────────────────────

const ALL_PREFIXES = Object.values(KIND_PREFIX);

// ── Phase 1: Hint Resolution ─────────────────────────────────────────

interface ResolvedHint {
  nodeId: string;
  matchedFrom: string;
  matchMethod: "exact" | "basename" | "text_search";
}

function resolveHints(
  hints: string[],
  graphStore: GraphStore,
): { resolved: ResolvedHint[]; warnings: string[] } {
  const resolved: ResolvedHint[] = [];
  const seen = new Set<string>();
  const warnings: string[] = [];

  for (const hint of hints) {
    const before = resolved.length;

    // a) Exact node ID (contains ":")
    if (hint.includes(":")) {
      if (graphStore.hasNode(hint)) {
        addUnique(resolved, seen, { nodeId: hint, matchedFrom: hint, matchMethod: "exact" });
        continue;
      }
    }

    // b) File path (contains "/" or ".")
    if (hint.includes("/") || hint.includes(".")) {
      const basename = extractBasename(hint);
      const variants = generatePrefixVariants(basename);

      for (const variant of variants) {
        if (graphStore.hasNode(variant)) {
          addUnique(resolved, seen, { nodeId: variant, matchedFrom: hint, matchMethod: "basename" });
        }
      }

      // If prefix variants didn't match, try text search on basename
      if (resolved.length === before) {
        const found = graphStore.textSearch(basename);
        for (const node of found) {
          addUnique(resolved, seen, { nodeId: node.id, matchedFrom: hint, matchMethod: "text_search" });
        }
      }

      if (resolved.length > before) continue;
    }

    // c) Keyword — try prefix variants first, then text search
    if (!hint.includes(":") && !hint.includes("/") && !hint.includes(".")) {
      const variants = generatePrefixVariants(hint);
      for (const variant of variants) {
        if (graphStore.hasNode(variant)) {
          addUnique(resolved, seen, { nodeId: variant, matchedFrom: hint, matchMethod: "exact" });
        }
      }
    }

    // Fallback: text search (multi-word hints match nodes containing ALL words)
    if (resolved.length === before) {
      const words = hint.split(/\s+/).filter(Boolean);
      if (words.length > 1) {
        // Multi-word: find nodes matching all words
        const candidates = graphStore.textSearch(words[0]!);
        const rest = words.slice(1).map((w) => w.toLowerCase());
        for (const node of candidates) {
          const text = nodeSearchableText(node);
          if (rest.every((w) => text.includes(w))) {
            addUnique(resolved, seen, { nodeId: node.id, matchedFrom: hint, matchMethod: "text_search" });
          }
        }
      } else {
        const found = graphStore.textSearch(hint);
        for (const node of found) {
          addUnique(resolved, seen, { nodeId: node.id, matchedFrom: hint, matchMethod: "text_search" });
        }
      }
    }

    if (resolved.length === before) {
      warnings.push(`No match found for hint: '${hint}'`);
    }
  }

  return { resolved, warnings };
}

function extractBasename(filePath: string): string {
  const parts = filePath.split("/");
  const filename = parts[parts.length - 1]!;
  // Remove extension
  const dotIdx = filename.lastIndexOf(".");
  return dotIdx > 0 ? filename.substring(0, dotIdx) : filename;
}

function generatePrefixVariants(name: string): string[] {
  const variants: string[] = [];
  // Try both original case and capitalized
  const names = [name];
  const capitalized = name.charAt(0).toUpperCase() + name.slice(1);
  if (capitalized !== name) names.push(capitalized);

  for (const n of names) {
    for (const prefix of ALL_PREFIXES) {
      variants.push(`${prefix}:${n}`);
    }
  }
  return variants;
}

function nodeSearchableText(node: GraphNode): string {
  const parts = [node.id.toLowerCase(), ...node.aliases.map((a) => a.toLowerCase())];
  for (const val of Object.values(node.indexed_fields)) {
    if (val != null) parts.push(String(val).toLowerCase());
  }
  return parts.join(" ");
}

function addUnique(
  arr: ResolvedHint[],
  seen: Set<string>,
  item: ResolvedHint,
): void {
  if (!seen.has(item.nodeId)) {
    seen.add(item.nodeId);
    arr.push(item);
  }
}

// ── Phase 2: Constraint Discovery ────────────────────────────────────

interface DiscoveredNode {
  node: GraphNode;
  reachedVia: string;
  distance: number;
}

function discoverConstraints(
  resolvedHints: ResolvedHint[],
  graphStore: GraphStore,
  depth: number,
): Map<string, DiscoveredNode> {
  const discovered = new Map<string, DiscoveredNode>();
  const rootIds = new Set(resolvedHints.map((r) => r.nodeId));

  for (const { nodeId } of resolvedHints) {
    const rootNode = graphStore.getNode(nodeId);
    if (!rootNode) continue;

    // Add the root node itself
    if (!discovered.has(nodeId)) {
      discovered.set(nodeId, {
        node: rootNode,
        reachedVia: nodeId,
        distance: 0,
      });
    }

    // A) Direct edges (both incoming and outgoing)
    const outEdges = graphStore.outgoingEdges(nodeId);
    for (const edge of outEdges) {
      const target = graphStore.getNode(edge.to_node);
      if (!target || discovered.has(target.id)) continue;
      discovered.set(target.id, {
        node: target,
        reachedVia: `${nodeId} -> ${edge.edge_type} -> ${target.id}`,
        distance: 1,
      });
    }

    const inEdges = graphStore.incomingEdges(nodeId);
    for (const edge of inEdges) {
      const source = graphStore.getNode(edge.from_node);
      if (!source || discovered.has(source.id)) continue;
      discovered.set(source.id, {
        node: source,
        reachedVia: `${source.id} -> ${edge.edge_type} -> ${nodeId}`,
        distance: 1,
      });
    }

    // B) Deeper traversal if depth > 1
    if (depth > 1) {
      const [nodes, edges] = graphStore.traverse(nodeId, depth);
      for (const node of nodes) {
        if (discovered.has(node.id)) continue;
        // Find the edge that connects to this node for reachedVia
        const connectingEdge = edges.find(
          (e) => e.to_node === node.id || e.from_node === node.id,
        );
        const via = connectingEdge
          ? `${connectingEdge.from_node} -> ${connectingEdge.edge_type} -> ${connectingEdge.to_node}`
          : `${nodeId} -> traverse(${depth}) -> ${node.id}`;

        discovered.set(node.id, {
          node,
          reachedVia: via,
          distance: 2,
        });
      }
    }
  }

  return discovered;
}

// ── Phase 3: Content Extraction ──────────────────────────────────────

const MAX_CONTENT_LENGTH = 300;

function extractContent(node: GraphNode): string {
  const fields = node.indexed_fields;

  switch (node.kind) {
    case "business-rule":
    case "business-policy":
    case "cross-policy":
      return truncate(stringField(fields, "declaration"), MAX_CONTENT_LENGTH);

    case "entity":
      return truncate(
        stringField(fields, "invariants") || stringField(fields, "description"),
        MAX_CONTENT_LENGTH,
      );

    case "command":
      return truncate(
        joinFields(fields, ["preconditions", "postconditions"]),
        MAX_CONTENT_LENGTH,
      );

    case "use-case":
      return truncate(
        joinFields(fields, ["description", "preconditions"]),
        MAX_CONTENT_LENGTH,
      );

    case "requirement":
      return truncate(stringField(fields, "description"), MAX_CONTENT_LENGTH);

    default:
      return truncate(
        stringField(fields, "description") || stringField(fields, "purpose") || node.id,
        MAX_CONTENT_LENGTH,
      );
  }
}

function stringField(fields: Record<string, unknown>, key: string): string {
  const val = fields[key];
  if (val == null) return "";
  if (Array.isArray(val)) return val.map(String).join("; ");
  return String(val);
}

function joinFields(fields: Record<string, unknown>, keys: string[]): string {
  return keys
    .map((k) => stringField(fields, k))
    .filter(Boolean)
    .join(" | ");
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.substring(0, maxLen - 3) + "...";
}

// ── Phase 4: Sort & Token Budget ─────────────────────────────────────

function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

// ── Main query function ──────────────────────────────────────────────

export function contextQuery(
  input: ContextQueryInput,
  graphStore: GraphStore,
): ContextResult {
  const { hints, depth = 1, maxTokens = 4000 } = input;

  if (hints.length === 0) {
    throw new Error("EMPTY_HINTS: At least one hint is required");
  }

  // Phase 1: Resolve hints to graph nodes
  const { resolved, warnings } = resolveHints(hints, graphStore);

  const resolvedEntities: ResolvedEntity[] = resolved.map((r) => ({
    node_id: r.nodeId,
    matched_from: r.matchedFrom,
    match_method: r.matchMethod,
  }));

  if (resolved.length === 0) {
    return {
      constraints: [],
      behavior: [],
      resolvedEntities: [],
      warnings: hints.map((h) => `No match found for hint: '${h}'`),
      totalItems: 0,
      totalTokens: 0,
    };
  }

  // Phase 2: Discover constraints via graph edges
  const discovered = discoverConstraints(resolved, graphStore, depth);

  // Phase 3: Extract content and build items
  const allItems: (ContextItem & { _priority: number; _distance: number })[] = [];

  for (const [, disc] of discovered) {
    const content = extractContent(disc.node);
    if (!content) continue;

    allItems.push({
      node_id: disc.node.id,
      kind: disc.node.kind,
      content,
      source_file: disc.node.source_file,
      reached_via: disc.reachedVia,
      _priority: kindPriority(disc.node.kind),
      _distance: disc.distance,
    });
  }

  // Phase 4: Sort by priority, then distance
  allItems.sort((a, b) => {
    if (a._priority !== b._priority) return a._priority - b._priority;
    return a._distance - b._distance;
  });

  // Apply token budget
  const constraints: ContextItem[] = [];
  const behavior: ContextItem[] = [];
  let totalTokens = 0;

  for (const item of allItems) {
    const itemTokens = estimateTokens(
      `${item.node_id} ${item.kind} ${item.content} ${item.source_file} ${item.reached_via}`,
    );

    if (totalTokens + itemTokens > maxTokens) break;
    totalTokens += itemTokens;

    const { _priority, _distance, ...contextItem } = item;

    if (_priority <= 1) {
      // constraints: BR, BP, XP, entity invariants
      constraints.push(contextItem);
    } else {
      // behavior: CMD, UC, REQ
      behavior.push(contextItem);
    }
  }

  return {
    constraints,
    behavior,
    resolvedEntities,
    warnings,
    totalItems: constraints.length + behavior.length,
    totalTokens,
  };
}
