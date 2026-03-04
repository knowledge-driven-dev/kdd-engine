import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { join } from "node:path";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { ArtifactWriter, loadAllEmbeddings, VectorStore } from "@kdd/core";
import type { Embedding } from "@kdd/core";

function makeEmbedding(overrides?: Partial<Embedding>): Embedding {
  const dims = 4;
  return {
    id: "emb-001-0",
    document_id: "DOC-001",
    document_kind: "entity",
    section_path: "root",
    chunk_index: 0,
    raw_text: "test chunk",
    context_text: "context for test chunk",
    vector: [0.1, 0.2, 0.3, 0.4],
    model: "test-model",
    dimensions: dims,
    text_hash: "abc123",
    generated_at: new Date().toISOString(),
    ...overrides,
  };
}

let tmpDir: string;

beforeEach(async () => {
  tmpDir = await mkdtemp(join(tmpdir(), "kdd-test-"));
});

afterEach(async () => {
  await rm(tmpDir, { recursive: true, force: true });
});

describe("binary embeddings (json+f32)", () => {
  test("round-trip: write → load → vectors match within Float32 precision", async () => {
    const writer = new ArtifactWriter(tmpDir);
    const emb1 = makeEmbedding({ id: "emb-001-0", chunk_index: 0, vector: [0.123456789, 0.987654321, -0.5, 0.0] });
    const emb2 = makeEmbedding({ id: "emb-001-1", chunk_index: 1, vector: [1.0, -1.0, 0.0, 0.5] });

    await writer.writeEmbeddings([emb1, emb2]);

    const loaded = await loadAllEmbeddings(tmpDir);
    expect(loaded).toHaveLength(2);

    // Vectors should match within Float32 precision (~7 significant digits)
    for (let i = 0; i < emb1.vector.length; i++) {
      expect(loaded[0]!.vector[i]).toBeCloseTo(emb1.vector[i]!, 6);
    }
    for (let i = 0; i < emb2.vector.length; i++) {
      expect(loaded[1]!.vector[i]).toBeCloseTo(emb2.vector[i]!, 6);
    }

    // Metadata should be exact
    expect(loaded[0]!.id).toBe(emb1.id);
    expect(loaded[0]!.raw_text).toBe(emb1.raw_text);
    expect(loaded[1]!.chunk_index).toBe(1);
  });

  test("JSON file does not contain vector field", async () => {
    const writer = new ArtifactWriter(tmpDir);
    await writer.writeEmbeddings([makeEmbedding()]);

    const jsonPath = join(tmpDir, "embeddings", "entity", "DOC-001.json");
    const content = await Bun.file(jsonPath).json();
    expect(content[0]).not.toHaveProperty("vector");
    expect(content[0]).toHaveProperty("id");
    expect(content[0]).toHaveProperty("dimensions");
  });

  test(".f32 file has correct byte size", async () => {
    const writer = new ArtifactWriter(tmpDir);
    const dims = 4;
    const embs = [
      makeEmbedding({ id: "e-0", chunk_index: 0 }),
      makeEmbedding({ id: "e-1", chunk_index: 1 }),
      makeEmbedding({ id: "e-2", chunk_index: 2 }),
    ];
    await writer.writeEmbeddings(embs);

    const f32Path = join(tmpDir, "embeddings", "entity", "DOC-001.f32");
    const file = Bun.file(f32Path);
    expect(file.size).toBe(embs.length * dims * 4); // 3 vectors × 4 dims × 4 bytes
  });

  test("backward compat: legacy JSON with inline vector loads correctly", async () => {
    // Manually write legacy format (JSON with vector field)
    const { mkdir } = await import("node:fs/promises");
    const dir = join(tmpDir, "embeddings", "entity");
    await mkdir(dir, { recursive: true });

    const legacy = [makeEmbedding({ id: "legacy-0" }), makeEmbedding({ id: "legacy-1", chunk_index: 1 })];
    await Bun.write(join(dir, "DOC-001.json"), JSON.stringify(legacy, null, 2));
    // No .f32 file — legacy format

    const loaded = await loadAllEmbeddings(tmpDir);
    expect(loaded).toHaveLength(2);
    expect(loaded[0]!.id).toBe("legacy-0");
    expect(loaded[0]!.vector).toEqual([0.1, 0.2, 0.3, 0.4]);
    expect(loaded[1]!.id).toBe("legacy-1");
  });

  test("mixed format: some docs legacy, some binary", async () => {
    const { mkdir } = await import("node:fs/promises");

    // Legacy doc
    const legacyDir = join(tmpDir, "embeddings", "entity");
    await mkdir(legacyDir, { recursive: true });
    const legacyEmb = makeEmbedding({ id: "legacy-emb", document_id: "LEGACY-DOC" });
    await Bun.write(join(legacyDir, "LEGACY-DOC.json"), JSON.stringify([legacyEmb], null, 2));

    // Binary doc
    const writer = new ArtifactWriter(tmpDir);
    const binaryEmb = makeEmbedding({ id: "binary-emb", document_id: "BIN-DOC", vector: [0.5, 0.6, 0.7, 0.8] });
    await writer.writeEmbeddings([binaryEmb]);

    const loaded = await loadAllEmbeddings(tmpDir);
    expect(loaded).toHaveLength(2);

    const legacyLoaded = loaded.find((e) => e.id === "legacy-emb")!;
    const binaryLoaded = loaded.find((e) => e.id === "binary-emb")!;

    expect(legacyLoaded.vector).toEqual([0.1, 0.2, 0.3, 0.4]);
    for (let i = 0; i < binaryEmb.vector.length; i++) {
      expect(binaryLoaded.vector[i]).toBeCloseTo(binaryEmb.vector[i]!, 6);
    }
  });

  test("deleteDocumentArtifacts removes both .json and .f32", async () => {
    const writer = new ArtifactWriter(tmpDir);
    await writer.writeEmbeddings([makeEmbedding()]);

    const jsonPath = join(tmpDir, "embeddings", "entity", "DOC-001.json");
    const f32Path = join(tmpDir, "embeddings", "entity", "DOC-001.f32");

    expect(await Bun.file(jsonPath).exists()).toBe(true);
    expect(await Bun.file(f32Path).exists()).toBe(true);

    // Need a node so deleteDocumentArtifacts can find it
    const { mkdir } = await import("node:fs/promises");
    const nodeDir = join(tmpDir, "nodes", "entity");
    await mkdir(nodeDir, { recursive: true });
    await Bun.write(join(nodeDir, "DOC-001.json"), JSON.stringify({ id: "Entity:DOC-001" }));
    await mkdir(join(tmpDir, "edges"), { recursive: true });
    await Bun.write(join(tmpDir, "edges", "edges.jsonl"), "");

    await writer.deleteDocumentArtifacts("DOC-001");

    expect(await Bun.file(jsonPath).exists()).toBe(false);
    expect(await Bun.file(f32Path).exists()).toBe(false);
  });

  test("VectorStore with Float32 produces correct cosine similarity scores", () => {
    const store = new VectorStore();
    const embs: Embedding[] = [
      makeEmbedding({ id: "a", vector: [1, 0, 0, 0] }),
      makeEmbedding({ id: "b", vector: [0, 1, 0, 0] }),
      makeEmbedding({ id: "c", vector: [0.9, 0.1, 0, 0] }),
    ];
    store.load(embs);

    // Query vector identical to "a" — should score 1.0
    const results = store.search([1, 0, 0, 0], 10, 0);
    expect(results).toHaveLength(3);
    expect(results[0]![0]).toBe("a");
    expect(results[0]![1]).toBeCloseTo(1.0, 5);

    // "c" should be second (cos(a,c) ≈ 0.994)
    expect(results[1]![0]).toBe("c");
    expect(results[1]![1]).toBeGreaterThan(0.99);

    // "b" orthogonal → score 0
    expect(results[2]![0]).toBe("b");
    expect(results[2]![1]).toBeCloseTo(0, 5);
  });

  test("multiple documents with different kinds", async () => {
    const writer = new ArtifactWriter(tmpDir);
    const embEntity = makeEmbedding({ id: "e1", document_id: "DOC-A", document_kind: "entity" });
    const embRule = makeEmbedding({ id: "r1", document_id: "DOC-B", document_kind: "business-rule", vector: [0.9, 0.8, 0.7, 0.6] });

    await writer.writeEmbeddings([embEntity, embRule]);

    const loaded = await loadAllEmbeddings(tmpDir);
    expect(loaded).toHaveLength(2);

    const entityLoaded = loaded.find((e) => e.document_kind === "entity")!;
    const ruleLoaded = loaded.find((e) => e.document_kind === "business-rule")!;
    expect(entityLoaded.id).toBe("e1");
    expect(ruleLoaded.id).toBe("r1");
  });
});
