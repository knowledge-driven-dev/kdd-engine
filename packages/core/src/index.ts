// Domain
export * from "./domain/types.ts";
export * from "./domain/rules.ts";

// Infra
export { GraphStore } from "./infra/graph-store.ts";
export { VectorStore } from "./infra/vector-store.ts";
export { ArtifactWriter } from "./infra/artifact-writer.ts";
export { createEncoder } from "./infra/embedding-model.ts";
export { extractFrontmatter, parseMarkdownSections, headingToAnchor, extractSnippet } from "./infra/markdown-parser.ts";
export { extractWikiLinks, extractWikiLinkTargets } from "./infra/wiki-links.ts";
export type { WikiLink } from "./infra/wiki-links.ts";
export { loadManifest, loadAllNodes, loadEdges, loadAllEmbeddings } from "./infra/artifact-loader.ts";

// Application — queries
export { hybridSearch } from "./application/queries/hybrid-search.ts";
export type { HybridSearchInput, HybridSearchResult } from "./application/queries/hybrid-search.ts";
export { graphQuery } from "./application/queries/graph-query.ts";
export type { GraphQueryInput, GraphQueryResult } from "./application/queries/graph-query.ts";
export { impactQuery } from "./application/queries/impact-query.ts";
export type { ImpactQueryInput, ImpactQueryResult } from "./application/queries/impact-query.ts";
export { semanticQuery } from "./application/queries/semantic-query.ts";
export type { SemanticQueryInput, SemanticQueryResult } from "./application/queries/semantic-query.ts";
export { coverageQuery } from "./application/queries/coverage-query.ts";
export type { CoverageQueryInput, CoverageQueryResult } from "./application/queries/coverage-query.ts";
export { violationsQuery } from "./application/queries/violations-query.ts";
export type { ViolationsQueryInput, ViolationsQueryResult } from "./application/queries/violations-query.ts";
export { orphanEdgesQuery } from "./application/queries/orphan-edges-query.ts";
export type { OrphanEdgesQueryInput, OrphanEdgesQueryResult } from "./application/queries/orphan-edges-query.ts";
export { contextQuery } from "./application/queries/context-query.ts";
export type { ContextQueryInput, ContextResult } from "./application/queries/context-query.ts";

// Application — commands
export { indexDocument } from "./application/commands/index-document.ts";

// Application — extractors
export { createDefaultRegistry, ExtractorRegistry } from "./application/extractors/registry.ts";

// Application — chunking
export { chunkDocument } from "./application/chunking.ts";

// Container
export { createContainer, type Container } from "./container.ts";
