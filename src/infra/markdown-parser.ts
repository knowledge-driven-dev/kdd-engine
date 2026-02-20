/**
 * Markdown parsing — frontmatter extraction and section parsing.
 */

import matter from "gray-matter";
import type { Section } from "../domain/types.ts";

export function extractFrontmatter(content: string): [Record<string, unknown>, string] {
  try {
    const { data, content: body } = matter(content);
    return [data as Record<string, unknown>, body];
  } catch {
    return [{}, content];
  }
}

export function parseMarkdownSections(content: string): Section[] {
  const sections: Section[] = [];
  const currentHeadings: string[] = [];
  const currentLevels: number[] = [];
  let currentLines: string[] = [];

  function flush(): void {
    const text = currentLines.join("\n").trim();
    if (currentHeadings.length > 0) {
      const path = currentHeadings.map(headingToAnchor).join(".");
      sections.push({
        heading: currentHeadings[currentHeadings.length - 1]!,
        level: currentLevels[currentLevels.length - 1] ?? 1,
        content: text,
        path,
      });
    }
  }

  for (const line of content.split("\n")) {
    if (line.startsWith("#")) {
      flush();
      currentLines = [];

      const level = line.length - line.replace(/^#+/, "").length;
      const headingText = line.replace(/^#+\s*/, "");

      // Maintain hierarchy: pop deeper or equal headings
      while (currentLevels.length > 0 && currentLevels[currentLevels.length - 1]! >= level) {
        currentLevels.pop();
        if (currentHeadings.length > 0) currentHeadings.pop();
      }

      currentHeadings.push(headingText);
      currentLevels.push(level);
    } else {
      currentLines.push(line);
    }
  }

  flush();
  return sections;
}

export function headingToAnchor(heading: string): string {
  let text = heading.normalize("NFKD").toLowerCase();
  text = text.replace(/[^\w\s-]/g, "");
  text = text.replace(/\s+/g, "-");
  text = text.replace(/^-+|-+$/g, "");
  return text;
}

export function extractSnippet(content: string, maxLength = 200): string {
  let text = content.trim();
  text = text.replace(/^#+\s+/gm, "");
  text = text.replace(/\*\*([^*]+)\*\*/g, "$1");
  text = text.replace(/\*([^*]+)\*/g, "$1");
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  text = text.replace(/\s+/g, " ").trim();

  if (text.length <= maxLength) return text;

  const truncated = text.slice(0, maxLength);
  const lastPeriod = truncated.lastIndexOf(". ");
  if (lastPeriod > maxLength / 2) return truncated.slice(0, lastPeriod + 1);

  const lastSpace = truncated.lastIndexOf(" ");
  if (lastSpace > maxLength / 2) return truncated.slice(0, lastSpace) + "...";

  return truncated + "...";
}
