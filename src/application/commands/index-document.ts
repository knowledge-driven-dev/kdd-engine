/**
 * CMD-001 — IndexDocument command.
 *
 * Processes a single KDD spec file through the full indexing pipeline.
 */

import { basename, relative } from "node:path";
import { createHash } from "node:crypto";
import type { Embedding, IndexResult, KDDDocument, KDDLayer } from "../../domain/types.ts";
import { IndexLevel } from "../../domain/types.ts";
import { detectLayer, routeDocument } from "../../domain/rules.ts";
import { extractFrontmatter, parseMarkdownSections } from "../../infra/markdown-parser.ts";
import { extractWikiLinkTargets } from "../../infra/wiki-links.ts";
import { chunkDocument } from "../chunking.ts";
import type { ExtractorRegistry } from "../extractors/registry.ts";
import type { ArtifactWriter } from "../../infra/artifact-writer.ts";

export async function indexDocument(
  filePath: string,
  opts: {
    specsRoot: string;
    registry: ExtractorRegistry;
    artifactWriter: ArtifactWriter;
    encodeFn?: ((texts: string[]) => Promise<number[][]>) | null;
    modelName?: string;
    modelDimensions?: number;
    indexLevel?: string;
    domain?: string | null;
  },
): Promise<IndexResult> {
  const {
    specsRoot,
    registry,
    artifactWriter,
    encodeFn,
    modelName,
    modelDimensions,
    indexLevel = IndexLevel.L1,
    domain = null,
  } = opts;

  // 1. Read file
  const file = Bun.file(filePath);
  let content: string;
  try {
    content = await file.text();
  } catch (e) {
    return { success: false, edge_count: 0, embedding_count: 0, skipped_reason: `File error: ${e}` };
  }

  // 2. Extract front-matter and route
  const [frontMatter, body] = extractFrontmatter(content);
  const relativePath = relative(specsRoot, filePath);
  const route = routeDocument(frontMatter, relativePath);

  if (!route.kind) {
    return { success: false, edge_count: 0, embedding_count: 0, skipped_reason: "No valid kind in front-matter" };
  }

  // 3. Find extractor
  const extractor = registry.get(route.kind);
  if (!extractor) {
    return { success: false, edge_count: 0, embedding_count: 0, skipped_reason: `No extractor for kind '${route.kind}'` };
  }

  // 4. Build KDDDocument
  const sections = parseMarkdownSections(body);
  const wikiLinks = extractWikiLinkTargets(body);
  const layer: KDDLayer = detectLayer(relativePath) ?? "01-domain";
  const docId = (frontMatter.id as string) ?? basename(filePath, ".md");
  const sourceHash = createHash("sha256").update(content).digest("hex");

  const document: KDDDocument = {
    id: docId,
    kind: route.kind,
    source_path: relativePath,
    source_hash: sourceHash,
    layer,
    front_matter: frontMatter,
    sections,
    wiki_links: wikiLinks,
    domain,
  };

  // 5. Extract node + edges
  const node = extractor.extractNode(document);
  const edges = extractor.extractEdges(document);

  // 6. Write artifacts
  await artifactWriter.writeNode(node);
  if (edges.length > 0) {
    await artifactWriter.appendEdges(edges);
  }

  // 7. Optional L2: chunk + embed
  let embeddingCount = 0;
  if ((indexLevel === IndexLevel.L2 || indexLevel === IndexLevel.L3) && encodeFn) {
    const chunks = chunkDocument(document);
    if (chunks.length > 0) {
      const texts = chunks.map((c) => c.context_text);
      const vectors = await encodeFn(texts);
      const now = new Date().toISOString();
      const embeddings: Embedding[] = chunks.map((chunk, i) => ({
        id: chunk.chunk_id,
        document_id: docId,
        document_kind: route.kind!,
        section_path: chunk.section_heading,
        chunk_index: i,
        raw_text: chunk.content,
        context_text: chunk.context_text,
        vector: vectors[i]!,
        model: modelName ?? "unknown",
        dimensions: modelDimensions ?? vectors[i]!.length,
        text_hash: createHash("sha256").update(chunk.content).digest("hex"),
        generated_at: now,
      }));
      await artifactWriter.writeEmbeddings(embeddings);
      embeddingCount = embeddings.length;
    }
  }

  return {
    success: true,
    node_id: node.id,
    edge_count: edges.length,
    embedding_count: embeddingCount,
    warning: route.warning ?? undefined,
  };
}
