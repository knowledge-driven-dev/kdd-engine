"""Entity extraction for FalkorDB graph storage."""

import structlog

from kb_engine.smart.stores.falkordb_graph import FalkorDBGraphStore
from kb_engine.smart.types import ExtractedEntityInfo, ParsedDocument

logger = structlog.get_logger(__name__)


class EntityGraphExtractor:
    """Extracts and stores entity graph data in FalkorDB.

    Extracts:
    - Document node for provenance tracking
    - Main entity as Entity node
    - Attributes as Concept nodes (linked to entity via CONTAINS)
    - States as Concept nodes
    - Related entities as Entity nodes (linked via REFERENCES)
    - Events as Event nodes (linked via PRODUCES/CONSUMES)
    - EXTRACTED_FROM edges from every domain node to the Document
    """

    def __init__(self, graph_store: FalkorDBGraphStore) -> None:
        """Initialize extractor with graph store.

        Args:
            graph_store: FalkorDB graph store instance.
        """
        self.graph_store = graph_store

    def extract_and_store(
        self,
        parsed: ParsedDocument,
        entity_info: ExtractedEntityInfo,
    ) -> tuple[int, int]:
        """Extract entities and store in graph.

        Args:
            parsed: Parsed document.
            entity_info: Extracted entity information.

        Returns:
            Tuple of (nodes_created, edges_created).
        """
        log = logger.bind(entity_name=entity_info.name)
        log.debug("extractor.start")

        doc_id = parsed.frontmatter.get("id", entity_info.name)
        doc_path = parsed.frontmatter.get("path", "")
        doc_kind = parsed.kind.value if hasattr(parsed.kind, "value") else ""
        nodes_created = 0
        edges_created = 0

        # 0. Document node for provenance
        self.graph_store.upsert_document(
            doc_id=doc_id,
            title=entity_info.name,
            path=doc_path,
            kind=doc_kind,
        )
        nodes_created += 1

        # 1. Main entity node
        entity_id = f"entity:{entity_info.name}"
        self.graph_store.upsert_entity(
            entity_id=entity_id,
            name=entity_info.name,
            description=entity_info.description[:500] if entity_info.description else "",
            code_class=entity_info.code_class,
            code_table=entity_info.code_table,
            confidence=1.0,
        )
        nodes_created += 1
        self.graph_store.add_extracted_from(entity_id, "Entity", doc_id, "primary", 1.0)
        edges_created += 1
        log.debug("extractor.entity_created", entity_id=entity_id)

        # 2. Attribute nodes
        for attr in entity_info.attributes:
            concept_id = f"concept:{entity_info.name}.{attr.name}"
            self.graph_store.upsert_concept(
                concept_id=concept_id,
                name=attr.name,
                concept_type="attribute",
                description=attr.description,
                parent_entity=entity_info.name,
                properties={
                    "code": attr.code,
                    "type": attr.type,
                    "is_reference": attr.is_reference,
                    "reference_entity": attr.reference_entity,
                },
                confidence=0.95,
            )
            nodes_created += 1
            self.graph_store.add_extracted_from(concept_id, "Concept", doc_id, "primary", 0.95)
            edges_created += 1

            # CONTAINS edge
            self.graph_store.add_contains(
                entity_id=entity_id,
                concept_id=concept_id,
                confidence=1.0,
                source_doc_id=doc_id,
            )
            edges_created += 1

            # If attribute references another entity
            if attr.is_reference and attr.reference_entity:
                ref_entity_id = f"entity:{attr.reference_entity}"
                # Ensure referenced entity exists (stub)
                self.graph_store.upsert_entity(
                    entity_id=ref_entity_id,
                    name=attr.reference_entity,
                    description=f"Referenced by {entity_info.name}.{attr.name}",
                    confidence=0.7,  # Lower confidence for inferred entities
                )
                nodes_created += 1
                self.graph_store.add_extracted_from(
                    ref_entity_id, "Entity", doc_id, "referenced", 0.7
                )
                edges_created += 1

                # REFERENCES edge
                self.graph_store.add_references(
                    from_entity_id=entity_id,
                    to_entity_id=ref_entity_id,
                    via_attribute=attr.name,
                    confidence=0.9,
                    source_doc_id=doc_id,
                )
                edges_created += 1

        log.debug("extractor.attributes_created", count=len(entity_info.attributes))

        # 3. State nodes
        for state in entity_info.states:
            concept_id = f"concept:{entity_info.name}::{state.name}"
            self.graph_store.upsert_concept(
                concept_id=concept_id,
                name=state.name,
                concept_type="state",
                description=state.description,
                parent_entity=entity_info.name,
                properties={
                    "is_initial": state.is_initial,
                    "is_final": state.is_final,
                    "entry_conditions": state.entry_conditions,
                },
                confidence=0.95,
            )
            nodes_created += 1
            self.graph_store.add_extracted_from(concept_id, "Concept", doc_id, "primary", 0.95)
            edges_created += 1

            # CONTAINS edge
            self.graph_store.add_contains(
                entity_id=entity_id,
                concept_id=concept_id,
                confidence=1.0,
                source_doc_id=doc_id,
            )
            edges_created += 1

        log.debug("extractor.states_created", count=len(entity_info.states))

        # 4. Relations (to other entities)
        for rel in entity_info.relations:
            ref_entity_id = f"entity:{rel.target_entity}"

            # Ensure referenced entity exists (stub)
            self.graph_store.upsert_entity(
                entity_id=ref_entity_id,
                name=rel.target_entity,
                description=f"Related to {entity_info.name} via {rel.name}",
                confidence=0.7,
            )
            nodes_created += 1
            self.graph_store.add_extracted_from(
                ref_entity_id, "Entity", doc_id, "referenced", 0.7
            )
            edges_created += 1

            # REFERENCES edge
            self.graph_store.add_references(
                from_entity_id=entity_id,
                to_entity_id=ref_entity_id,
                via_attribute=rel.code or rel.name,
                cardinality=rel.cardinality,
                description=rel.description,
                confidence=0.95,
                source_doc_id=doc_id,
            )
            edges_created += 1

        log.debug("extractor.relations_created", count=len(entity_info.relations))

        # 5. Events emitted
        for event_name in entity_info.events_emitted:
            event_id = f"event:{event_name}"
            self.graph_store.upsert_event(
                event_id=event_id,
                name=event_name,
                description=f"Emitted by {entity_info.name}",
                confidence=0.9,
            )
            nodes_created += 1
            self.graph_store.add_extracted_from(event_id, "Event", doc_id, "primary", 0.9)
            edges_created += 1

            self.graph_store.add_produces(
                entity_id=entity_id,
                event_id=event_id,
                confidence=0.9,
                source_doc_id=doc_id,
            )
            edges_created += 1

        log.debug("extractor.events_emitted", count=len(entity_info.events_emitted))

        # 6. Events consumed
        for event_name in entity_info.events_consumed:
            event_id = f"event:{event_name}"
            self.graph_store.upsert_event(
                event_id=event_id,
                name=event_name,
                description=f"Consumed by {entity_info.name}",
                confidence=0.9,
            )
            nodes_created += 1
            self.graph_store.add_extracted_from(event_id, "Event", doc_id, "primary", 0.9)
            edges_created += 1

            self.graph_store.add_consumes(
                entity_id=entity_id,
                event_id=event_id,
                confidence=0.9,
                source_doc_id=doc_id,
            )
            edges_created += 1

        log.debug("extractor.events_consumed", count=len(entity_info.events_consumed))

        log.info(
            "extractor.complete",
            nodes_created=nodes_created,
            edges_created=edges_created,
        )

        return nodes_created, edges_created
