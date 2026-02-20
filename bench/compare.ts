/**
 * Benchmark — measures kdd-ts performance.
 */

import { resolve } from "node:path";
import { createContainer } from "../src/container.ts";
import { hybridSearch } from "../src/application/queries/hybrid-search.ts";
import { graphQuery } from "../src/application/queries/graph-query.ts";
import { impactQuery } from "../src/application/queries/impact-query.ts";

const INDEX_PATH = resolve(import.meta.dir, "../.kdd-index");
const QUERIES = [
  "documento KDD",
  "indexación incremental",
  "embedding modelo",
  "grafo nodos edges",
  "business rule validación",
];

interface BenchResult {
  label: string;
  ms: number;
}

const results: BenchResult[] = [];

function record(label: string, ms: number) {
  results.push({ label, ms });
  console.log(`  ${label}: ${ms.toFixed(1)}ms`);
}

console.log("\n=== KDD-TS Benchmark ===\n");

console.log("1. Index load (graph only, no embeddings):");
let t0 = performance.now();
const containerLight = await createContainer(INDEX_PATH, { skipEmbeddings: true });
record("index_load_graph_only", performance.now() - t0);
console.log(`   Nodes: ${containerLight.graphStore.nodeCount()}, Edges: ${containerLight.graphStore.edgeCount()}`);

console.log("\n2. Index load (with embeddings vectors):");
t0 = performance.now();
const containerFull = await createContainer(INDEX_PATH);
record("index_load_with_embeddings", performance.now() - t0);

console.log("\n3. Graph query latency:");
t0 = performance.now();
graphQuery({ rootNode: "Entity:KDDDocument", depth: 2 }, containerFull.graphStore);
record("graph_query_cold", performance.now() - t0);

const graphTimes: number[] = [];
for (let i = 0; i < 100; i++) {
  const t = performance.now();
  graphQuery({ rootNode: "Entity:KDDDocument", depth: 2 }, containerFull.graphStore);
  graphTimes.push(performance.now() - t);
}
record("graph_query_warm_avg_100", graphTimes.reduce((a, b) => a + b, 0) / graphTimes.length);

console.log("\n4. Impact query latency:");
t0 = performance.now();
impactQuery({ nodeId: "Entity:KDDDocument", depth: 3 }, containerFull.graphStore);
record("impact_query_cold", performance.now() - t0);

const impactTimes: number[] = [];
for (let i = 0; i < 100; i++) {
  const t = performance.now();
  impactQuery({ nodeId: "Entity:KDDDocument", depth: 3 }, containerFull.graphStore);
  impactTimes.push(performance.now() - t);
}
record("impact_query_warm_avg_100", impactTimes.reduce((a, b) => a + b, 0) / impactTimes.length);

console.log("\n5. Hybrid search latency:");
t0 = performance.now();
await hybridSearch(
  { queryText: QUERIES[0]!, minScore: 0.1, limit: 10 },
  containerFull.graphStore,
  containerFull.vectorStore,
  containerFull.encodeFn,
);
record("hybrid_search_cold_first_encode", performance.now() - t0);

const hybridTimes: number[] = [];
for (const q of QUERIES) {
  const t = performance.now();
  await hybridSearch(
    { queryText: q, minScore: 0.1, limit: 10 },
    containerFull.graphStore,
    containerFull.vectorStore,
    containerFull.encodeFn,
  );
  hybridTimes.push(performance.now() - t);
}
record("hybrid_search_warm_avg_5", hybridTimes.reduce((a, b) => a + b, 0) / hybridTimes.length);

console.log("\n6. Lexical-only search:");
const lexTimes: number[] = [];
for (const q of QUERIES) {
  const t = performance.now();
  await hybridSearch(
    { queryText: q, minScore: 0.01, limit: 10 },
    containerFull.graphStore,
    null,
    null,
  );
  lexTimes.push(performance.now() - t);
}
record("lexical_search_avg_5", lexTimes.reduce((a, b) => a + b, 0) / lexTimes.length);

console.log("\n\n=== Summary ===\n");
console.log("| Metric | Time (ms) |");
console.log("|--------|-----------|");
for (const r of results) {
  console.log(`| ${r.label} | ${r.ms.toFixed(1)} |`);
}
console.log("\nDone.");
