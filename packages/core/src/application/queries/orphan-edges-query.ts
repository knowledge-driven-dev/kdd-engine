/**
 * QRY-008 — Orphan edge detection.
 *
 * Reports edges whose source or target node was not loaded into the graph,
 * indicating broken references (typos in wiki links, missing specs, etc.).
 */

import type { OrphanEdge } from "../../domain/types.ts";
import type { GraphStore } from "../../infra/graph-store.ts";

export interface OrphanEdgesQueryInput {
  includeEdgeTypes?: string[];
}

export interface OrphanEdgesQueryResult {
  orphanEdges: OrphanEdge[];
  totalOrphan: number;
  totalEdgesOnDisk: number;
  orphanRate: number;
}

export function orphanEdgesQuery(
  input: OrphanEdgesQueryInput,
  graphStore: GraphStore,
): OrphanEdgesQueryResult {
  let orphans = graphStore.orphanEdges();

  if (input.includeEdgeTypes && input.includeEdgeTypes.length > 0) {
    const allowed = new Set(input.includeEdgeTypes);
    orphans = orphans.filter((e) => allowed.has(e.edge_type));
  }

  const loadedEdges = graphStore.edgeCount();
  const totalOnDisk = loadedEdges + graphStore.orphanEdges().length;
  const rate = totalOnDisk > 0
    ? Math.round((orphans.length / totalOnDisk) * 10000) / 100
    : 0;

  return {
    orphanEdges: orphans,
    totalOrphan: orphans.length,
    totalEdgesOnDisk: totalOnDisk,
    orphanRate: rate,
  };
}
