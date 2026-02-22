import { KDDKind, type GraphEdge, type GraphNode, type KDDDocument } from "../../../domain/types.ts";
import { buildWikiLinkEdges, deduplicateEdges, findSection, findSectionWithChildren, makeNodeId, type Extractor } from "../base.ts";

export class PRDExtractor implements Extractor {
  kind: KDDKind = KDDKind.PRD;

  extractNode(document: KDDDocument): GraphNode {
    const nodeId = makeNodeId(KDDKind.PRD, document.id);
    const fields: Record<string, unknown> = {};

    const problem = findSection(document.sections, "Problema / Oportunidad", "Problem / Opportunity", "Problema", "Problem");
    if (problem) fields.problem = problem.content;
    const scope = findSectionWithChildren(document.sections, "Alcance", "Scope");
    if (scope) fields.scope = scope;
    const users = findSectionWithChildren(document.sections, "Usuarios y Jobs-to-be-done", "Users and Jobs-to-be-done");
    if (users) fields.users = users;
    const metrics = findSection(document.sections, "Métricas de éxito y telemetría", "Success Metrics");
    if (metrics) fields.metrics = metrics.content;
    const deps = findSection(document.sections, "Dependencias", "Dependencies");
    if (deps) fields.dependencies = deps.content;

    return {
      id: nodeId, kind: KDDKind.PRD, source_file: document.source_path,
      source_hash: document.source_hash, layer: document.layer,
      status: String(document.front_matter.status ?? "draft"),
      aliases: (document.front_matter.aliases as string[]) ?? [],
      domain: document.domain, indexed_fields: fields,
      indexed_at: new Date().toISOString(),
    };
  }

  extractEdges(document: KDDDocument): GraphEdge[] {
    const nodeId = makeNodeId(KDDKind.PRD, document.id);
    return deduplicateEdges(buildWikiLinkEdges(document, nodeId, document.layer));
  }
}
