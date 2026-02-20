/**
 * Vector store — brute-force cosine similarity.
 */

import type { Embedding } from "../domain/types.ts";

export class VectorStore {
  private ids: string[] = [];
  private vectors: Float64Array[] = [];

  load(embeddings: Embedding[]): void {
    this.ids = embeddings.map((e) => e.id);
    this.vectors = embeddings.map((e) => new Float64Array(e.vector));
  }

  search(
    queryVector: number[],
    limit: number,
    minScore: number,
  ): Array<[string, number]> {
    if (this.ids.length === 0) return [];

    const qv = new Float64Array(queryVector);
    const qNorm = norm(qv);
    if (qNorm === 0) return [];

    const scored: Array<[string, number]> = [];

    for (let i = 0; i < this.vectors.length; i++) {
      const v = this.vectors[i]!;
      const sim = dot(qv, v) / (qNorm * norm(v));
      if (sim >= minScore) {
        scored.push([this.ids[i]!, sim]);
      }
    }

    scored.sort((a, b) => b[1] - a[1]);
    return scored.slice(0, limit);
  }

  get size(): number {
    return this.ids.length;
  }
}

function dot(a: Float64Array, b: Float64Array): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    sum += a[i]! * b[i]!;
  }
  return sum;
}

function norm(a: Float64Array): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    sum += a[i]! * a[i]!;
  }
  return Math.sqrt(sum);
}
