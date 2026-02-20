/**
 * Domain types for KDD.
 *
 * Ported from: src/kdd/domain/enums.py + src/kdd/domain/entities.py
 */

// ── Enums (as const objects for runtime + type safety) ──────────────

export const KDDKind = {
  ENTITY: "entity",
  EVENT: "event",
  BUSINESS_RULE: "business-rule",
  BUSINESS_POLICY: "business-policy",
  CROSS_POLICY: "cross-policy",
  COMMAND: "command",
  QUERY: "query",
  PROCESS: "process",
  USE_CASE: "use-case",
  UI_VIEW: "ui-view",
  UI_COMPONENT: "ui-component",
  REQUIREMENT: "requirement",
  OBJECTIVE: "objective",
  PRD: "prd",
  ADR: "adr",
  GLOSSARY: "glossary",
} as const;
export type KDDKind = (typeof KDDKind)[keyof typeof KDDKind];

export const KDDLayer = {
  REQUIREMENTS: "00-requirements",
  DOMAIN: "01-domain",
  BEHAVIOR: "02-behavior",
  EXPERIENCE: "03-experience",
  VERIFICATION: "04-verification",
} as const;
export type KDDLayer = (typeof KDDLayer)[keyof typeof KDDLayer];

/** Numeric ordering for layer violation checks. */
export const LAYER_NUMERIC: Record<KDDLayer, number> = {
  "00-requirements": 0,
  "01-domain": 1,
  "02-behavior": 2,
  "03-experience": 3,
  "04-verification": 4,
};

export const EdgeType = {
  WIKI_LINK: "WIKI_LINK",
  DOMAIN_RELATION: "DOMAIN_RELATION",
  ENTITY_RULE: "ENTITY_RULE",
  ENTITY_POLICY: "ENTITY_POLICY",
  EMITS: "EMITS",
  CONSUMES: "CONSUMES",
  UC_APPLIES_RULE: "UC_APPLIES_RULE",
  UC_EXECUTES_CMD: "UC_EXECUTES_CMD",
  UC_STORY: "UC_STORY",
  VIEW_TRIGGERS_UC: "VIEW_TRIGGERS_UC",
  VIEW_USES_COMPONENT: "VIEW_USES_COMPONENT",
  COMPONENT_USES_ENTITY: "COMPONENT_USES_ENTITY",
  REQ_TRACES_TO: "REQ_TRACES_TO",
  VALIDATES: "VALIDATES",
  DECIDES_FOR: "DECIDES_FOR",
  CROSS_DOMAIN_REF: "CROSS_DOMAIN_REF",
  GLOSSARY_DEFINES: "GLOSSARY_DEFINES",
} as const;
export type EdgeType = (typeof EdgeType)[keyof typeof EdgeType];

export const IndexLevel = { L1: "L1", L2: "L2", L3: "L3" } as const;
export type IndexLevel = (typeof IndexLevel)[keyof typeof IndexLevel];

// ── Kind → Node ID prefix mapping ──────────────────────────────────

export const KIND_PREFIX: Record<KDDKind, string> = {
  entity: "Entity",
  event: "Event",
  "business-rule": "BR",
  "business-policy": "BP",
  "cross-policy": "XP",
  command: "CMD",
  query: "QRY",
  process: "PROC",
  "use-case": "UC",
  "ui-view": "UIView",
  "ui-component": "UIComp",
  requirement: "REQ",
  objective: "OBJ",
  prd: "PRD",
  adr: "ADR",
  glossary: "GLOSS",
};

// ── Data interfaces ─────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  kind: KDDKind;
  source_file: string;
  source_hash: string;
  layer: KDDLayer;
  status: string;
  aliases: string[];
  domain: string | null;
  indexed_fields: Record<string, unknown>;
  indexed_at: string;
}

export interface GraphEdge {
  from_node: string;
  to_node: string;
  edge_type: string;
  source_file: string;
  extraction_method: string;
  metadata: Record<string, unknown>;
  layer_violation: boolean;
  bidirectional: boolean;
}

export interface Embedding {
  id: string;
  document_id: string;
  document_kind: KDDKind;
  section_path: string;
  chunk_index: number;
  raw_text: string;
  context_text: string;
  vector: number[];
  model: string;
  dimensions: number;
  text_hash: string;
  generated_at: string;
}

export interface Manifest {
  version: string;
  kdd_version: string;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  indexed_at: string;
  indexed_by: string;
  structure: string;
  index_level: IndexLevel;
  stats: {
    nodes: number;
    edges: number;
    embeddings: number;
    enrichments: number;
  };
  domains: string[];
  git_commit: string | null;
}

export interface ScoredNode {
  node_id: string;
  score: number;
  snippet: string;
  match_source: string;
}

// ── Document model (for indexing pipeline) ──────────────────────────

export interface Section {
  heading: string;
  level: number;
  content: string;
  path: string;
}

export interface KDDDocument {
  id: string;
  kind: KDDKind;
  source_path: string;
  source_hash: string;
  layer: KDDLayer;
  front_matter: Record<string, unknown>;
  sections: Section[];
  wiki_links: string[];
  domain: string | null;
}

export interface Chunk {
  chunk_id: string;
  document_id: string;
  section_heading: string;
  content: string;
  context_text: string;
  char_offset: number;
}

export interface IndexResult {
  success: boolean;
  node_id?: string;
  edge_count: number;
  embedding_count: number;
  skipped_reason?: string;
  warning?: string;
}

export interface LayerViolation {
  from_node: string;
  to_node: string;
  from_layer: KDDLayer;
  to_layer: KDDLayer;
  edge_type: string;
}

export interface CoverageCategory {
  name: string;
  description: string;
  edge_type: string;
  status: "covered" | "missing" | "partial";
  found: string[];
}
