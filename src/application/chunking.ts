/**
 * Hierarchical chunking for embedding generation (BR-EMBEDDING-001).
 */

import type { Chunk, KDDDocument, KDDKind } from "../domain/types.ts";
import { embeddableSections } from "../domain/rules.ts";

export function chunkDocument(
  document: KDDDocument,
  maxChunkChars = 1500,
  overlapChars = 200,
): Chunk[] {
  const allowed = embeddableSections(document.kind);
  if (allowed.size === 0) return [];

  const identity = buildIdentity(document);
  const chunks: Chunk[] = [];
  let chunkIdx = 0;

  for (const section of document.sections) {
    if (!allowed.has(section.heading.toLowerCase())) continue;
    if (!section.content.trim()) continue;

    const paragraphs = splitParagraphs(section.content, maxChunkChars, overlapChars);

    for (const [offset, text] of paragraphs) {
      const context = `${identity}\nSection: ${section.heading}\n\n${text}`;
      chunks.push({
        chunk_id: `${document.id}:chunk-${chunkIdx}`,
        document_id: document.id,
        section_heading: section.heading,
        content: text,
        context_text: context,
        char_offset: offset,
      });
      chunkIdx++;
    }
  }

  return chunks;
}

function buildIdentity(document: KDDDocument): string {
  const parts = [
    `Document: ${document.id}`,
    `Kind: ${document.kind}`,
    `Layer: ${document.layer}`,
  ];
  const title = document.front_matter.title;
  if (title) parts.push(`Title: ${title}`);
  return parts.join("\n");
}

function splitParagraphs(
  content: string,
  maxChars: number,
  overlap: number,
): [number, string][] {
  const paragraphs = content.split("\n\n");
  const results: [number, string][] = [];
  let currentParts: string[] = [];
  let currentLen = 0;
  let currentOffset = 0;
  let charPos = 0;

  for (const rawPara of paragraphs) {
    const para = rawPara.trim();
    if (!para) {
      charPos += 2;
      continue;
    }

    const paraLen = para.length;

    if (currentLen + paraLen + 2 > maxChars && currentParts.length > 0) {
      results.push([currentOffset, currentParts.join("\n\n")]);
      if (overlap > 0 && currentParts.length > 0) {
        const last = currentParts[currentParts.length - 1]!;
        if (last.length <= overlap) {
          currentParts = [last];
          currentLen = last.length;
          currentOffset = charPos - last.length - 2;
        } else {
          currentParts = [];
          currentLen = 0;
          currentOffset = charPos;
        }
      } else {
        currentParts = [];
        currentLen = 0;
        currentOffset = charPos;
      }
    }

    if (paraLen > maxChars && currentParts.length === 0) {
      const sentences = splitSentences(para);
      const sentBuf: string[] = [];
      let sentLen = 0;
      let sentOffset = charPos;

      for (const sent of sentences) {
        if (sentLen + sent.length + 1 > maxChars && sentBuf.length > 0) {
          results.push([sentOffset, sentBuf.join(" ")]);
          sentBuf.length = 0;
          sentLen = 0;
          sentOffset = charPos;
        }
        sentBuf.push(sent);
        sentLen += sent.length + 1;
      }

      if (sentBuf.length > 0) {
        currentParts = sentBuf;
        currentLen = sentLen;
        currentOffset = sentOffset;
      }
    } else {
      if (currentParts.length === 0) currentOffset = charPos;
      currentParts.push(para);
      currentLen += paraLen + 2;
    }

    charPos += paraLen + 2;
  }

  if (currentParts.length > 0) {
    results.push([currentOffset, currentParts.join("\n\n")]);
  }

  return results;
}

function splitSentences(text: string): string[] {
  return text
    .split(/(?<=\.)\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}
