/**
 * Extractor registry — maps KDDKind to extractor instances.
 */

import type { KDDKind } from "../../domain/types.ts";
import type { Extractor } from "./base.ts";
import { EntityExtractor } from "./kinds/entity.ts";
import { EventExtractor } from "./kinds/event.ts";
import { BusinessRuleExtractor } from "./kinds/business-rule.ts";
import { BusinessPolicyExtractor } from "./kinds/business-policy.ts";
import { CrossPolicyExtractor } from "./kinds/cross-policy.ts";
import { CommandExtractor } from "./kinds/command.ts";
import { QueryExtractor } from "./kinds/query.ts";
import { ProcessExtractor } from "./kinds/process.ts";
import { UseCaseExtractor } from "./kinds/use-case.ts";
import { UIViewExtractor } from "./kinds/ui-view.ts";
import { UIComponentExtractor } from "./kinds/ui-component.ts";
import { RequirementExtractor } from "./kinds/requirement.ts";
import { ObjectiveExtractor } from "./kinds/objective.ts";
import { PRDExtractor } from "./kinds/prd.ts";
import { ADRExtractor } from "./kinds/adr.ts";
import { GlossaryExtractor } from "./kinds/glossary.ts";

export class ExtractorRegistry {
  private extractors = new Map<KDDKind, Extractor>();

  register(extractor: Extractor): void {
    this.extractors.set(extractor.kind, extractor);
  }

  get(kind: KDDKind): Extractor | undefined {
    return this.extractors.get(kind);
  }

  get registeredKinds(): Set<KDDKind> {
    return new Set(this.extractors.keys());
  }

  get size(): number {
    return this.extractors.size;
  }
}

export function createDefaultRegistry(): ExtractorRegistry {
  const registry = new ExtractorRegistry();
  registry.register(new EntityExtractor());
  registry.register(new EventExtractor());
  registry.register(new BusinessRuleExtractor());
  registry.register(new BusinessPolicyExtractor());
  registry.register(new CrossPolicyExtractor());
  registry.register(new CommandExtractor());
  registry.register(new QueryExtractor());
  registry.register(new ProcessExtractor());
  registry.register(new UseCaseExtractor());
  registry.register(new UIViewExtractor());
  registry.register(new UIComponentExtractor());
  registry.register(new RequirementExtractor());
  registry.register(new ObjectiveExtractor());
  registry.register(new PRDExtractor());
  registry.register(new ADRExtractor());
  registry.register(new GlossaryExtractor());
  return registry;
}
