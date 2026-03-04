/**
 * Artifact writer — writes .kdd-index/ artifacts.
 */

import { join } from "node:path";
import { mkdir } from "node:fs/promises";
import type { Embedding, EmbeddingMeta, GraphEdge, GraphNode, Manifest } from "../domain/types.ts";

export class ArtifactWriter {
  constructor(private indexPath: string) {}

  async writeManifest(manifest: Manifest): Promise<void> {
    await mkdir(this.indexPath, { recursive: true });
    const path = join(this.indexPath, "manifest.json");
    await Bun.write(path, JSON.stringify(manifest, null, 2));
  }

  async writeNode(node: GraphNode): Promise<void> {
    const docId = node.id.includes(":") ? node.id.split(":").slice(1).join(":") : node.id;
    const dir = join(this.indexPath, "nodes", node.kind);
    await mkdir(dir, { recursive: true });
    const path = join(dir, `${docId}.json`);
    await Bun.write(path, JSON.stringify(node, null, 2));
  }

  async appendEdges(edges: GraphEdge[]): Promise<void> {
    const dir = join(this.indexPath, "edges");
    await mkdir(dir, { recursive: true });
    const path = join(dir, "edges.jsonl");
    const lines = edges.map((e) => JSON.stringify(e)).join("\n") + "\n";
    const file = Bun.file(path);
    if (await file.exists()) {
      const existing = await file.text();
      await Bun.write(path, existing + lines);
    } else {
      await Bun.write(path, lines);
    }
  }

  async writeEmbeddings(embeddings: Embedding[]): Promise<void> {
    if (embeddings.length === 0) return;
    // Group by (kind, document_id)
    const byDoc = new Map<string, Embedding[]>();
    for (const emb of embeddings) {
      const key = `${emb.document_kind}/${emb.document_id}`;
      const list = byDoc.get(key) ?? [];
      list.push(emb);
      byDoc.set(key, list);
    }

    for (const [key, docEmbeddings] of byDoc) {
      const [kind, docId] = key.split("/", 2) as [string, string];
      const dir = join(this.indexPath, "embeddings", kind);
      await mkdir(dir, { recursive: true });

      // Metadata JSON (without vector)
      const meta: EmbeddingMeta[] = docEmbeddings.map(({ vector: _, ...rest }) => rest);
      await Bun.write(join(dir, `${docId}.json`), JSON.stringify(meta, null, 2));

      // Binary vectors (contiguous Float32Array)
      const dims = docEmbeddings[0]!.dimensions;
      const buf = new Float32Array(docEmbeddings.length * dims);
      for (let i = 0; i < docEmbeddings.length; i++) {
        buf.set(docEmbeddings[i]!.vector, i * dims);
      }
      await Bun.write(join(dir, `${docId}.f32`), buf);
    }
  }

  async deleteDocumentArtifacts(documentId: string): Promise<void> {
    const { readdir, unlink, rmdir } = await import("node:fs/promises");
    const nodesDir = join(this.indexPath, "nodes");

    try {
      const kinds = await readdir(nodesDir);
      for (const kind of kinds) {
        const path = join(nodesDir, kind, `${documentId}.json`);
        const file = Bun.file(path);
        if (await file.exists()) {
          const data = await file.json();
          const nodeId = data.id ?? "";
          await unlink(path);
          await this.removeEdgesForNode(nodeId);
          break;
        }
      }
    } catch { /* nodes dir may not exist */ }

    // Delete embeddings (.json + .f32)
    const embDir = join(this.indexPath, "embeddings");
    try {
      const kinds = await readdir(embDir);
      for (const kind of kinds) {
        for (const ext of [".json", ".f32"]) {
          const path = join(embDir, kind, `${documentId}${ext}`);
          const file = Bun.file(path);
          if (await file.exists()) {
            await unlink(path);
          }
        }
      }
    } catch { /* embeddings dir may not exist */ }
  }

  async clearEdges(): Promise<void> {
    const path = join(this.indexPath, "edges", "edges.jsonl");
    const dir = join(this.indexPath, "edges");
    await mkdir(dir, { recursive: true });
    await Bun.write(path, "");
  }

  private async removeEdgesForNode(nodeId: string): Promise<void> {
    const path = join(this.indexPath, "edges", "edges.jsonl");
    const file = Bun.file(path);
    if (!(await file.exists())) return;
    const text = await file.text();
    const kept = text
      .split("\n")
      .filter((line) => {
        if (!line.trim()) return false;
        const data = JSON.parse(line);
        return data.from_node !== nodeId && data.to_node !== nodeId;
      })
      .join("\n");
    await Bun.write(path, kept + (kept ? "\n" : ""));
  }
}
