---
id: BR-DOCUMENT-001
kind: business-rule
title: Kind Router
category: validation
severity: high
status: draft
---

# BR-DOCUMENT-001 — Kind Router

## Declaración

Dado un fichero dentro de `/specs`, el sistema debe determinar el `kind` del [[KDDDocument]] y seleccionar el extractor correcto. La detección se basa en una combinación del campo `kind` del front-matter y la ubicación del fichero en la estructura de carpetas.

### Tabla de decisión

| Condición front-matter `kind` | Ubicación esperada | `kind` asignado | Extractor |
|-------------------------------|-------------------|-----------------|-----------|
| `entity` | `01-domain/entities/` | `entity` | EntityExtractor |
| `event` | `01-domain/events/` | `event` | EventExtractor |
| `business-rule` | `01-domain/rules/` | `business-rule` | RuleExtractor |
| `business-policy` | `02-behavior/policies/` | `business-policy` | PolicyExtractor |
| `cross-policy` | `02-behavior/policies/` | `cross-policy` | CrossPolicyExtractor |
| `command` | `02-behavior/commands/` | `command` | CommandExtractor |
| `query` | `02-behavior/queries/` | `query` | QueryExtractor |
| `process` | `02-behavior/processes/` | `process` | ProcessExtractor |
| `use-case` | `02-behavior/use-cases/` | `use-case` | UseCaseExtractor |
| `ui-view` | `03-experience/views/` | `ui-view` | UIViewExtractor |
| `ui-component` | `03-experience/views/` | `ui-component` | UIComponentExtractor |
| `requirement` | `04-verification/criteria/` | `requirement` | RequirementExtractor |
| `objective` | `00-requirements/objectives/` | `objective` | ObjectiveExtractor |
| `prd` | `00-requirements/` | `prd` | PRDExtractor |
| `adr` | `00-requirements/decisions/` | `adr` | ADRExtractor |

### Prioridad de detección

1. **Front-matter `kind`** tiene prioridad absoluta. Si está presente y es un valor reconocido, se usa directamente.
2. **Ubicación del fichero** se usa como validación: si el `kind` del front-matter no corresponde a la carpeta esperada, se emite un warning pero se respeta el front-matter.
3. **Ficheros sin front-matter** o con `kind` no reconocido se ignoran (no producen [[KDDDocument]]).

## Por qué existe

El KDD Engine indexa múltiples tipos de artefactos KDD, cada uno con una estructura de secciones y campos indexables diferente. Sin un router que seleccione el extractor correcto, el sistema no puede parsear los campos específicos de cada tipo (e.g. `## Atributos` para entities vs. `## Input` para commands).

## Cuándo aplica

En cada fichero `.md` o `.yaml` encontrado dentro de `/specs` durante la fase de detección del pipeline de indexación ([[EVT-KDDDocument-Detected]]).

## Qué pasa si se incumple

- Si un fichero tiene un `kind` no reconocido, se ignora silenciosamente y no produce artefactos en el índice.
- Si un fichero no tiene front-matter, se ignora.
- Si el `kind` no coincide con la ubicación esperada, se indexa según el `kind` declarado pero se registra un warning en el log de indexación.

## Ejemplos

**Caso válido — entity en ubicación correcta:**
```
Fichero: specs/01-domain/entities/Pedido.md
Front-matter: kind: entity
→ Kind asignado: entity
→ Extractor: EntityExtractor
→ Resultado: OK
```

**Caso válido — kind en ubicación inesperada (warning):**
```
Fichero: specs/02-behavior/MiEntidad.md
Front-matter: kind: entity
→ Kind asignado: entity (front-matter tiene prioridad)
→ Extractor: EntityExtractor
→ Warning: "entity 'MiEntidad' found outside expected path 01-domain/entities/"
```

**Caso ignorado — sin front-matter:**
```
Fichero: specs/01-domain/entities/README.md
Front-matter: (ausente)
→ Resultado: fichero ignorado, no produce KDDDocument
```
