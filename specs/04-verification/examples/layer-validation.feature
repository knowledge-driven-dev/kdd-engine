# language: es
Característica: Validación de dependencias de capa
  Como motor de indexación
  Quiero detectar referencias que violan las dependencias de capa KDD
  Para que los desarrolladores y agentes puedan corregir violaciones

  Antecedentes:
    Dado un repositorio con estructura KDD

  Escenario: SCN-LayerValidation-001 — Referencia válida de capa superior a inferior
    Dado un fichero "specs/02-behavior/use-cases/UC-001-IndexDocument.md" que referencia "[[KDDDocument]]"
    Cuando indexo el fichero
    Entonces se genera un edge "WIKI_LINK" de "UC:UC-001" a "Entity:KDDDocument"
    Y el edge tiene layer_violation false

  Escenario: SCN-LayerValidation-002 — Referencia inválida de capa inferior a superior
    Dado un fichero "specs/01-domain/entities/MiEntidad.md" que referencia "[[UC-001-IndexDocument]]"
    Cuando indexo el fichero
    Entonces se genera un edge "WIKI_LINK" de "Entity:MiEntidad" a "UC:UC-001"
    Y el edge tiene layer_violation true

  Escenario: SCN-LayerValidation-003 — Requirements exentos de validación
    Dado un fichero "specs/00-requirements/PRD-KDDEngine.md" que referencia "[[UC-001-IndexDocument]]"
    Cuando indexo el fichero
    Entonces se genera un edge "WIKI_LINK" de "PRD:PRD-KDDEngine" a "UC:UC-001"
    Y el edge tiene layer_violation false

  Escenario: SCN-LayerValidation-004 — Referencia entre misma capa es válida
    Dado un fichero "specs/01-domain/entities/KDDDocument.md" que referencia "[[GraphNode]]"
    Cuando indexo el fichero
    Entonces se genera un edge "WIKI_LINK" de "Entity:KDDDocument" a "Entity:GraphNode"
    Y el edge tiene layer_violation false

  Escenario: SCN-LayerValidation-005 — Query de violaciones detecta todas las marcadas
    Dado un índice con 2 edges marcados con layer_violation true
    Cuando consulto "retrieve layer-violations"
    Entonces recibo 2 violaciones con detalle de nodos, capas y edge_type
