/**
 * Business rules as pure functions.
 *
 * BR-DOCUMENT-001, BR-EMBEDDING-001, BR-INDEX-001, BR-LAYER-001
 */

import { IndexLevel, KDDKind, KDDLayer, LAYER_NUMERIC } from "./types.ts";

// ── BR-DOCUMENT-001 — Kind Router ────────────────────────────────────

export const KIND_LOOKUP: Record<string, KDDKind> = Object.fromEntries(
  Object.values(KDDKind).map((k) => [k, k]),
);

export const KIND_EXPECTED_PATH: Partial<Record<KDDKind, string>> = {
  [KDDKind.ENTITY]: "01-domain/entities/",
  [KDDKind.EVENT]: "01-domain/events/",
  [KDDKind.BUSINESS_RULE]: "01-domain/rules/",
  [KDDKind.BUSINESS_POLICY]: "02-behavior/policies/",
  [KDDKind.CROSS_POLICY]: "02-behavior/policies/",
  [KDDKind.COMMAND]: "02-behavior/commands/",
  [KDDKind.QUERY]: "02-behavior/queries/",
  [KDDKind.PROCESS]: "02-behavior/processes/",
  [KDDKind.USE_CASE]: "02-behavior/use-cases/",
  [KDDKind.UI_VIEW]: "03-experience/views/",
  [KDDKind.UI_COMPONENT]: "03-experience/views/",
  [KDDKind.REQUIREMENT]: "04-verification/criteria/",
  [KDDKind.OBJECTIVE]: "00-requirements/objectives/",
  [KDDKind.PRD]: "00-requirements/",
  [KDDKind.ADR]: "00-requirements/decisions/",
  [KDDKind.GLOSSARY]: "01-domain/glossary/",
};

export interface RouteResult {
  kind: KDDKind | null;
  warning: string | null;
}

export function routeDocument(
  frontMatter: Record<string, unknown> | null,
  sourcePath: string,
): RouteResult {
  if (!frontMatter) return { kind: null, warning: null };

  const kindStr = String(frontMatter.kind ?? "").toLowerCase().trim();
  if (!kindStr || !(kindStr in KIND_LOOKUP)) return { kind: null, warning: null };

  const kind = KIND_LOOKUP[kindStr]!;
  const expected = KIND_EXPECTED_PATH[kind] ?? "";
  let warning: string | null = null;
  if (expected && !sourcePath.includes(expected)) {
    warning = `${kind} '${sourcePath}' found outside expected path '${expected}'`;
  }

  return { kind, warning };
}

// ── BR-EMBEDDING-001 — Embedding Strategy ────────────────────────────

export const EMBEDDABLE_SECTIONS: Record<KDDKind, Set<string>> = {
  [KDDKind.ENTITY]: new Set(["descripción", "description"]),
  [KDDKind.EVENT]: new Set(),
  [KDDKind.BUSINESS_RULE]: new Set(["declaración", "declaration", "cuándo aplica", "when applies"]),
  [KDDKind.BUSINESS_POLICY]: new Set(["declaración", "declaration"]),
  [KDDKind.CROSS_POLICY]: new Set(["propósito", "purpose", "declaración", "declaration"]),
  [KDDKind.COMMAND]: new Set(["purpose", "propósito"]),
  [KDDKind.QUERY]: new Set(["purpose", "propósito"]),
  [KDDKind.PROCESS]: new Set(["participantes", "participants", "pasos", "steps"]),
  [KDDKind.USE_CASE]: new Set(["descripción", "description", "flujo principal", "main flow"]),
  [KDDKind.UI_VIEW]: new Set(["descripción", "description", "comportamiento", "behavior"]),
  [KDDKind.UI_COMPONENT]: new Set(["descripción", "description"]),
  [KDDKind.REQUIREMENT]: new Set(["descripción", "description"]),
  [KDDKind.OBJECTIVE]: new Set(["objetivo", "objective"]),
  [KDDKind.PRD]: new Set(["problema / oportunidad", "problem / opportunity"]),
  [KDDKind.ADR]: new Set(["contexto", "context", "decisión", "decision"]),
  [KDDKind.GLOSSARY]: new Set(["definición", "definition"]),
};

export function embeddableSections(kind: KDDKind): Set<string> {
  return EMBEDDABLE_SECTIONS[kind] ?? new Set();
}

// ── BR-INDEX-001 — Index Level detection ────────────────────────────

export function detectIndexLevel(
  embeddingModelAvailable: boolean,
  agentApiAvailable: boolean,
): IndexLevel {
  if (agentApiAvailable && embeddingModelAvailable) return IndexLevel.L3;
  if (embeddingModelAvailable) return IndexLevel.L2;
  return IndexLevel.L1;
}

// ── BR-LAYER-001 — Layer Validation ─────────────────────────────────

const LAYER_BY_PREFIX: Record<string, KDDLayer> = {
  "00-requirements": KDDLayer.REQUIREMENTS,
  "01-domain": KDDLayer.DOMAIN,
  "02-behavior": KDDLayer.BEHAVIOR,
  "03-experience": KDDLayer.EXPERIENCE,
  "04-verification": KDDLayer.VERIFICATION,
};

export function detectLayer(sourcePath: string): KDDLayer | null {
  for (const [prefix, layer] of Object.entries(LAYER_BY_PREFIX)) {
    if (sourcePath.includes(prefix)) return layer;
  }
  return null;
}

export function isLayerViolation(
  originLayer: KDDLayer,
  destinationLayer: KDDLayer,
): boolean {
  if (originLayer === KDDLayer.REQUIREMENTS) return false;
  return LAYER_NUMERIC[originLayer] < LAYER_NUMERIC[destinationLayer];
}
