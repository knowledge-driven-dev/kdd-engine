/**
 * MCP server — exposes KDD search tools.
 *
 * Tools: kdd_search, kdd_find_spec, kdd_related, kdd_impact,
 *        kdd_read_section, kdd_list, kdd_stats
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { resolve } from "node:path";
import { createContainer, type Container } from "./container.ts";
import { hybridSearch } from "./application/queries/hybrid-search.ts";
import { graphQuery } from "./application/queries/graph-query.ts";
import { impactQuery } from "./application/queries/impact-query.ts";
import type { KDDKind } from "./domain/types.ts";

const INDEX_PATH = resolve(process.env.KDD_INDEX_PATH ?? ".kdd-index");
const SPECS_PATH = resolve(process.env.KDD_SPECS_PATH ?? "specs");

let container: Container;

async function getContainer(): Promise<Container> {
  if (!container) {
    container = await createContainer(INDEX_PATH);
  }
  return container;
}

const server = new Server(
  { name: "kdd", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "kdd_search",
      description: "Search KDD specifications using hybrid retrieval (semantic + graph + lexical). Returns scored results with snippets.",
      inputSchema: {
        type: "object" as const,
        properties: {
          query: { type: "string", description: "Search query text (min 3 chars)" },
          kind: { type: "string", description: "Filter by kind (comma-separated: entity, command, use-case, etc.)" },
          limit: { type: "number", description: "Max results (default: 10)" },
          min_score: { type: "number", description: "Minimum score threshold (default: 0.3)" },
        },
        required: ["query"],
      },
    },
    {
      name: "kdd_find_spec",
      description: "Quick lookup of a specific KDD spec by name or ID. Convenience wrapper for search with limit=5.",
      inputSchema: {
        type: "object" as const,
        properties: {
          name: { type: "string", description: "Spec name or ID to find" },
        },
        required: ["name"],
      },
    },
    {
      name: "kdd_related",
      description: "Find related specs via knowledge graph traversal (BFS from root node).",
      inputSchema: {
        type: "object" as const,
        properties: {
          node_id: { type: "string", description: "Root node ID (e.g. Entity:KDDDocument)" },
          depth: { type: "number", description: "Traversal depth (default: 2)" },
          kind: { type: "string", description: "Filter by kind (comma-separated)" },
        },
        required: ["node_id"],
      },
    },
    {
      name: "kdd_impact",
      description: "Impact analysis: what breaks if this spec changes? Uses reverse BFS to find dependents.",
      inputSchema: {
        type: "object" as const,
        properties: {
          node_id: { type: "string", description: "Node ID to analyze" },
          depth: { type: "number", description: "Analysis depth (default: 3)" },
        },
        required: ["node_id"],
      },
    },
    {
      name: "kdd_read_section",
      description: "Read the raw markdown content of a spec file, optionally a specific section by anchor.",
      inputSchema: {
        type: "object" as const,
        properties: {
          file: { type: "string", description: "Relative path within specs/ (e.g. 01-domain/entities/KDDDocument.md)" },
          anchor: { type: "string", description: "Section anchor to jump to (e.g. #descripción)" },
        },
        required: ["file"],
      },
    },
    {
      name: "kdd_list",
      description: "List all indexed KDD nodes, optionally filtered by kind or domain.",
      inputSchema: {
        type: "object" as const,
        properties: {
          kind: { type: "string", description: "Filter by kind (comma-separated)" },
          domain: { type: "string", description: "Filter by domain" },
        },
      },
    },
    {
      name: "kdd_stats",
      description: "Get index statistics: node count, edge count, embedding count, etc.",
      inputSchema: { type: "object" as const, properties: {} },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const c = await getContainer();

  try {
    switch (name) {
      case "kdd_search": {
        const query = String(args?.query ?? "");
        const includeKinds = args?.kind
          ? String(args.kind).split(",") as KDDKind[]
          : undefined;
        const result = await hybridSearch(
          {
            queryText: query,
            limit: Number(args?.limit ?? 10),
            minScore: Number(args?.min_score ?? 0.3),
            includeKinds,
          },
          c.graphStore,
          c.vectorStore,
          c.encodeFn,
        );
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "kdd_find_spec": {
        const query = String(args?.name ?? "");
        const result = await hybridSearch(
          { queryText: query, limit: 5, minScore: 0.1 },
          c.graphStore,
          c.vectorStore,
          c.encodeFn,
        );
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "kdd_related": {
        const nodeId = String(args?.node_id ?? "");
        const includeKinds = args?.kind
          ? String(args.kind).split(",") as KDDKind[]
          : undefined;
        const result = graphQuery(
          {
            rootNode: nodeId,
            depth: Number(args?.depth ?? 2),
            includeKinds,
          },
          c.graphStore,
        );
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "kdd_impact": {
        const nodeId = String(args?.node_id ?? "");
        const result = impactQuery(
          { nodeId, depth: Number(args?.depth ?? 3) },
          c.graphStore,
        );
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "kdd_read_section": {
        const filePath = resolve(SPECS_PATH, String(args?.file ?? ""));
        const file = Bun.file(filePath);
        if (!(await file.exists())) {
          return { content: [{ type: "text", text: `File not found: ${args?.file}` }], isError: true };
        }
        let text = await file.text();

        // If anchor specified, extract that section
        const anchor = args?.anchor ? String(args.anchor).replace(/^#/, "") : null;
        if (anchor) {
          const lines = text.split("\n");
          let start = -1;
          let end = lines.length;
          let headingLevel = 0;

          for (let i = 0; i < lines.length; i++) {
            const line = lines[i]!;
            if (line.startsWith("#")) {
              const slug = line
                .replace(/^#+\s*/, "")
                .normalize("NFKD")
                .toLowerCase()
                .replace(/[^\w\s-]/g, "")
                .replace(/\s+/g, "-")
                .replace(/^-+|-+$/g, "");
              if (slug === anchor && start === -1) {
                start = i;
                headingLevel = line.length - line.replace(/^#+/, "").length;
              } else if (start !== -1) {
                const level = line.length - line.replace(/^#+/, "").length;
                if (level <= headingLevel) {
                  end = i;
                  break;
                }
              }
            }
          }

          if (start >= 0) {
            text = lines.slice(start, end).join("\n");
          }
        }

        return { content: [{ type: "text", text }] };
      }

      case "kdd_list": {
        const allNodes = c.graphStore.allNodes();
        let filtered = allNodes;

        if (args?.kind) {
          const kinds = new Set(String(args.kind).split(","));
          filtered = filtered.filter((n) => kinds.has(n.kind));
        }
        if (args?.domain) {
          filtered = filtered.filter((n) => n.domain === String(args!.domain));
        }

        const items = filtered.map((n) => ({
          id: n.id,
          kind: n.kind,
          layer: n.layer,
          source_file: n.source_file,
          title: n.indexed_fields.title ?? n.id,
        }));
        return { content: [{ type: "text", text: JSON.stringify(items, null, 2) }] };
      }

      case "kdd_stats": {
        const stats = {
          manifest: c.manifest,
          nodes: c.graphStore.nodeCount(),
          edges: c.graphStore.edgeCount(),
          embeddings: c.vectorStore?.size ?? 0,
        };
        return { content: [{ type: "text", text: JSON.stringify(stats, null, 2) }] };
      }

      default:
        return { content: [{ type: "text", text: `Unknown tool: ${name}` }], isError: true };
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
