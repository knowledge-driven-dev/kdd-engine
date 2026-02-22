import { describe, expect, test } from "bun:test";
import { GraphStore, orphanEdgesQuery } from "@kdd/core";
import type { GraphEdge, GraphNode } from "@kdd/core";

function makeNode(id: string, overrides?: Partial<GraphNode>): GraphNode {
  return {
    id,
    kind: "entity",
    source_file: `specs/${id}.md`,
    source_hash: "abc123",
    layer: "01-domain",
    status: "active",
    aliases: [],
    domain: null,
    indexed_fields: {},
    indexed_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeEdge(from: string, to: string, overrides?: Partial<GraphEdge>): GraphEdge {
  return {
    from_node: from,
    to_node: to,
    edge_type: "WIKI_LINK",
    source_file: `specs/${from}.md`,
    extraction_method: "wiki_link",
    metadata: {},
    layer_violation: false,
    bidirectional: false,
    ...overrides,
  };
}

describe("orphanEdgesQuery", () => {
  test("all edges valid → 0 orphans", () => {
    const store = new GraphStore();
    store.load(
      [makeNode("A"), makeNode("B"), makeNode("C")],
      [makeEdge("A", "B"), makeEdge("B", "C")],
    );

    const result = orphanEdgesQuery({}, store);
    expect(result.totalOrphan).toBe(0);
    expect(result.orphanEdges).toHaveLength(0);
    expect(result.totalEdgesOnDisk).toBe(2);
    expect(result.orphanRate).toBe(0);
  });

  test("missing target → reason: missing_target", () => {
    const store = new GraphStore();
    store.load(
      [makeNode("A")],
      [makeEdge("A", "MISSING")],
    );

    const result = orphanEdgesQuery({}, store);
    expect(result.totalOrphan).toBe(1);
    expect(result.orphanEdges[0]!.reason).toBe("missing_target");
    expect(result.orphanEdges[0]!.from_exists).toBe(true);
    expect(result.orphanEdges[0]!.to_exists).toBe(false);
    expect(result.orphanEdges[0]!.to_node).toBe("MISSING");
  });

  test("missing source → reason: missing_source", () => {
    const store = new GraphStore();
    store.load(
      [makeNode("B")],
      [makeEdge("MISSING", "B")],
    );

    const result = orphanEdgesQuery({}, store);
    expect(result.totalOrphan).toBe(1);
    expect(result.orphanEdges[0]!.reason).toBe("missing_source");
    expect(result.orphanEdges[0]!.from_exists).toBe(false);
    expect(result.orphanEdges[0]!.to_exists).toBe(true);
  });

  test("both missing → reason: both_missing", () => {
    const store = new GraphStore();
    store.load(
      [makeNode("C")],
      [makeEdge("GONE_A", "GONE_B")],
    );

    const result = orphanEdgesQuery({}, store);
    expect(result.totalOrphan).toBe(1);
    expect(result.orphanEdges[0]!.reason).toBe("both_missing");
    expect(result.orphanEdges[0]!.from_exists).toBe(false);
    expect(result.orphanEdges[0]!.to_exists).toBe(false);
  });

  test("edge type filter", () => {
    const store = new GraphStore();
    store.load(
      [makeNode("A")],
      [
        makeEdge("A", "MISSING1", { edge_type: "WIKI_LINK" }),
        makeEdge("A", "MISSING2", { edge_type: "DOMAIN_RELATION" }),
      ],
    );

    const result = orphanEdgesQuery({ includeEdgeTypes: ["WIKI_LINK"] }, store);
    expect(result.totalOrphan).toBe(1);
    expect(result.orphanEdges[0]!.edge_type).toBe("WIKI_LINK");
  });

  test("orphan rate calculation", () => {
    const store = new GraphStore();
    store.load(
      [makeNode("A"), makeNode("B")],
      [
        makeEdge("A", "B"),          // valid
        makeEdge("A", "MISSING1"),   // orphan
        makeEdge("A", "MISSING2"),   // orphan
        makeEdge("B", "MISSING3"),   // orphan
      ],
    );

    const result = orphanEdgesQuery({}, store);
    expect(result.totalOrphan).toBe(3);
    expect(result.totalEdgesOnDisk).toBe(4); // 1 loaded + 3 orphan
    expect(result.orphanRate).toBe(75); // 3/4 = 75%
  });

  test("addEdge also tracks orphans", () => {
    const store = new GraphStore();
    store.load([makeNode("A"), makeNode("B")], []);

    store.addEdge(makeEdge("A", "B"));         // valid
    store.addEdge(makeEdge("A", "MISSING"));   // orphan

    const result = orphanEdgesQuery({}, store);
    expect(result.totalOrphan).toBe(1);
    expect(result.orphanEdges[0]!.reason).toBe("missing_target");
  });
});
