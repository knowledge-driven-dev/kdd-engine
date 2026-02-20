/**
 * Wiki-link extraction from markdown content.
 *
 * Handles: [[Target]], [[domain::Target]], [[Target|Display]]
 */

const WIKI_LINK_RE = /\[\[([^\]]+)\]\]/g;

export interface WikiLink {
  raw: string;
  target: string;
  domain: string | null;
  alias: string | null;
}

export function extractWikiLinks(content: string): WikiLink[] {
  const results: WikiLink[] = [];
  for (const match of content.matchAll(WIKI_LINK_RE)) {
    const raw = match[1]!.trim();
    if (!raw) continue;

    let domain: string | null = null;
    let alias: string | null = null;
    let target = raw;

    // Cross-domain: [[domain::Target]]
    if (target.includes("::")) {
      const parts = target.split("::", 2);
      domain = parts[0]!.trim();
      target = parts[1]!.trim();
    }

    // Display alias: [[Target|Alias]]
    if (target.includes("|")) {
      const parts = target.split("|", 2);
      target = parts[0]!.trim();
      alias = parts[1]!.trim();
    }

    results.push({ raw, target, domain, alias });
  }
  return results;
}

export function extractWikiLinkTargets(content: string): string[] {
  return extractWikiLinks(content).map((link) => link.target);
}
