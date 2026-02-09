"""FalkorDB graph store for knowledge graph storage."""

from pathlib import Path
from typing import Any

import structlog
from redislite.falkordb_client import FalkorDB

logger = structlog.get_logger(__name__)


class FalkorDBGraphStore:
    """Graph store backed by FalkorDB (FalkorDBLite) embedded database.

    Provides storage for:
    - Document nodes (provenance tracking)
    - Entity nodes (domain entities)
    - Concept nodes (attributes, states)
    - Event nodes (domain events)
    - EXTRACTED_FROM relationships (node-to-document provenance)
    - Domain relationships (CONTAINS, REFERENCES, PRODUCES, CONSUMES)

    FalkorDB is schema-less and supports full MERGE...ON CREATE SET...ON MATCH SET syntax,
    making upserts much simpler than Kuzu.

    Usage:
        store = FalkorDBGraphStore("./kb-graph.db")
        store.initialize()

        # Add document provenance
        store.upsert_document("doc-1", "User Entity", "entities/User.md", "entity")

        # Add nodes
        store.upsert_entity("entity:User", "User", "Domain user")
        store.add_extracted_from("entity:User", "Entity", "doc-1", "primary", 1.0)

        # Query provenance
        impact = store.get_document_impact("doc-1")
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize FalkorDB graph store.

        Args:
            db_path: Path to the FalkorDB database file.
        """
        self.db_path = Path(db_path)
        self._db: FalkorDB | None = None
        self._graph: Any = None  # FalkorDB Graph object
        self._initialized = False

    def initialize(self, reset: bool = False) -> None:
        """Initialize the database.

        Args:
            reset: If True, delete existing database and start fresh.
        """
        log = logger.bind(db_path=str(self.db_path))

        if reset and self.db_path.exists():
            log.info("falkordb.reset", action="deleting existing database")
            self.db_path.unlink()

        log.debug("falkordb.initialize.start")

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize FalkorDB with file path
        self._db = FalkorDB(str(self.db_path))
        self._graph = self._db.select_graph("knowledge")

        if not self._initialized or reset:
            self._create_indexes()
            self._initialized = True

        log.info("falkordb.initialize.complete")

    def _create_indexes(self) -> None:
        """Create indexes for better query performance.

        FalkorDB is schema-less, so we only create indexes, not schema.
        """
        log = logger.bind(db_path=str(self.db_path))
        log.debug("falkordb.indexes.create")

        for label in ["Entity", "Concept", "Event", "Document"]:
            try:
                self._graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
            except Exception:
                pass  # Index may already exist

        log.debug("falkordb.indexes.created")

    @property
    def graph(self) -> Any:
        """Get graph instance, initializing if needed."""
        if self._graph is None:
            self.initialize()
        return self._graph

    def close(self) -> None:
        """Close database connection."""
        # FalkorDBLite doesn't have an explicit close method
        # Just release the references
        self._graph = None
        self._db = None

    # === Document Node Operations ===

    def upsert_document(
        self,
        doc_id: str,
        title: str,
        path: str = "",
        kind: str = "",
    ) -> None:
        """Insert or update a Document node for provenance tracking.

        Args:
            doc_id: Unique document identifier.
            title: Document title.
            path: File path or URL of the document.
            kind: Document kind (entity, use-case, etc.).
        """
        log = logger.bind(doc_id=doc_id, title=title)
        params = {
            "id": doc_id,
            "title": title,
            "path": path,
            "kind": kind,
        }

        try:
            self.graph.query(
                """
                MERGE (d:Document {id: $id})
                ON CREATE SET d.title = $title, d.path = $path, d.kind = $kind
                ON MATCH SET d.title = $title, d.path = $path, d.kind = $kind
                """,
                params=params,
            )
            log.debug("falkordb.document.upserted")
        except Exception as e:
            log.warning("falkordb.document.upsert_failed", error=str(e))
            raise

    def add_extracted_from(
        self,
        node_id: str,
        node_label: str,
        doc_id: str,
        role: str = "primary",
        confidence: float = 1.0,
    ) -> None:
        """Create EXTRACTED_FROM edge from a domain node to a Document.

        Args:
            node_id: ID of the source node (Entity, Concept, or Event).
            node_label: Label of the source node ("Entity", "Concept", or "Event").
            doc_id: ID of the target Document node.
            role: Role of the extraction ("primary" or "referenced").
            confidence: Confidence score of the extraction.
        """
        params = {
            "nid": node_id,
            "did": doc_id,
            "role": role,
            "conf": confidence,
        }
        try:
            self.graph.query(
                f"""
                MATCH (n:{node_label} {{id: $nid}}), (d:Document {{id: $did}})
                MERGE (n)-[r:EXTRACTED_FROM]->(d)
                ON CREATE SET r.role = $role, r.confidence = $conf
                ON MATCH SET r.role = $role, r.confidence = $conf
                """,
                params=params,
            )
        except Exception as e:
            logger.warning(
                "falkordb.extracted_from.failed",
                node_id=node_id,
                doc_id=doc_id,
                error=str(e),
            )

    # === Node Operations ===

    def upsert_entity(
        self,
        entity_id: str,
        name: str,
        description: str = "",
        code_class: str | None = None,
        code_table: str | None = None,
        confidence: float = 1.0,
    ) -> None:
        """Insert or update an Entity node.

        Uses a confidence guard: on update, only overwrites if the new
        confidence is >= the existing confidence. This prevents a stub
        reference (0.7) from overwriting a fully-defined entity (1.0).
        """
        log = logger.bind(entity_id=entity_id, name=name)
        params = {
            "id": entity_id,
            "name": name,
            "descr": description[:500] if description else "",
            "code_class": code_class or "",
            "code_table": code_table or "",
            "confidence": confidence,
        }

        try:
            # Step 1: Create if not exists
            self.graph.query(
                """
                MERGE (e:Entity {id: $id})
                ON CREATE SET e.name = $name, e.description = $descr, e.code_class = $code_class,
                    e.code_table = $code_table, e.confidence = $confidence
                """,
                params=params,
            )
            # Step 2: Update only if new confidence >= existing
            self.graph.query(
                """
                MATCH (e:Entity {id: $id}) WHERE e.confidence <= $confidence
                SET e.name = $name, e.description = $descr, e.code_class = $code_class,
                    e.code_table = $code_table, e.confidence = $confidence
                """,
                params=params,
            )
            log.debug("falkordb.entity.upserted")
        except Exception as e:
            log.warning("falkordb.entity.upsert_failed", error=str(e))
            raise

    def upsert_concept(
        self,
        concept_id: str,
        name: str,
        concept_type: str,
        description: str = "",
        parent_entity: str | None = None,
        properties: dict[str, Any] | None = None,
        confidence: float = 1.0,
    ) -> None:
        """Insert or update a Concept node.

        Uses a confidence guard: on update, only overwrites if the new
        confidence is >= the existing confidence.
        """
        import json

        log = logger.bind(concept_id=concept_id, concept_type=concept_type)
        params = {
            "id": concept_id,
            "name": name,
            "ctype": concept_type,
            "descr": description[:500] if description else "",
            "parent": parent_entity or "",
            "props": json.dumps(properties) if properties else "{}",
            "confidence": confidence,
        }

        try:
            # Step 1: Create if not exists
            self.graph.query(
                """
                MERGE (c:Concept {id: $id})
                ON CREATE SET c.name = $name, c.concept_type = $ctype, c.description = $descr,
                    c.parent_entity = $parent, c.properties = $props, c.confidence = $confidence
                """,
                params=params,
            )
            # Step 2: Update only if new confidence >= existing
            self.graph.query(
                """
                MATCH (c:Concept {id: $id}) WHERE c.confidence <= $confidence
                SET c.name = $name, c.concept_type = $ctype, c.description = $descr,
                    c.parent_entity = $parent, c.properties = $props, c.confidence = $confidence
                """,
                params=params,
            )
            log.debug("falkordb.concept.upserted")
        except Exception as e:
            log.warning("falkordb.concept.upsert_failed", error=str(e))
            raise

    def upsert_event(
        self,
        event_id: str,
        name: str,
        description: str = "",
        confidence: float = 1.0,
    ) -> None:
        """Insert or update an Event node.

        Uses a confidence guard: on update, only overwrites if the new
        confidence is >= the existing confidence.
        """
        log = logger.bind(event_id=event_id, name=name)
        params = {
            "id": event_id,
            "name": name,
            "descr": description[:500] if description else "",
            "confidence": confidence,
        }

        try:
            # Step 1: Create if not exists
            self.graph.query(
                """
                MERGE (e:Event {id: $id})
                ON CREATE SET e.name = $name, e.description = $descr, e.confidence = $confidence
                """,
                params=params,
            )
            # Step 2: Update only if new confidence >= existing
            self.graph.query(
                """
                MATCH (e:Event {id: $id}) WHERE e.confidence <= $confidence
                SET e.name = $name, e.description = $descr, e.confidence = $confidence
                """,
                params=params,
            )
            log.debug("falkordb.event.upserted")
        except Exception as e:
            log.warning("falkordb.event.upsert_failed", error=str(e))
            raise

    # === Relationship Operations ===

    def add_contains(
        self,
        entity_id: str,
        concept_id: str,
        confidence: float = 1.0,
        source_doc_id: str | None = None,
    ) -> None:
        """Add CONTAINS relationship from Entity to Concept."""
        params = {
            "eid": entity_id,
            "cid": concept_id,
            "conf": confidence,
            "source": source_doc_id or "",
        }
        try:
            self.graph.query(
                """
                MATCH (e:Entity {id: $eid}), (c:Concept {id: $cid})
                MERGE (e)-[r:CONTAINS]->(c)
                ON CREATE SET r.confidence = $conf, r.source_doc_id = $source
                """,
                params=params,
            )
        except Exception as e:
            logger.warning(
                "falkordb.contains.failed", entity=entity_id, concept=concept_id, error=str(e)
            )

    def add_references(
        self,
        from_entity_id: str,
        to_entity_id: str,
        via_attribute: str | None = None,
        cardinality: str | None = None,
        description: str = "",
        confidence: float = 1.0,
        source_doc_id: str | None = None,
    ) -> None:
        """Add REFERENCES relationship between Entities."""
        params = {
            "eid1": from_entity_id,
            "eid2": to_entity_id,
            "via": via_attribute or "",
            "card": cardinality or "",
            "descr": description,
            "conf": confidence,
            "source": source_doc_id or "",
        }
        try:
            self.graph.query(
                """
                MATCH (e1:Entity {id: $eid1}), (e2:Entity {id: $eid2})
                MERGE (e1)-[r:REFERENCES]->(e2)
                ON CREATE SET r.via_attribute = $via, r.cardinality = $card,
                    r.description = $descr, r.confidence = $conf, r.source_doc_id = $source
                """,
                params=params,
            )
        except Exception as e:
            logger.warning(
                "falkordb.references.failed",
                from_id=from_entity_id,
                to_id=to_entity_id,
                error=str(e),
            )

    def add_produces(
        self,
        entity_id: str,
        event_id: str,
        confidence: float = 1.0,
        source_doc_id: str | None = None,
    ) -> None:
        """Add PRODUCES relationship from Entity to Event."""
        params = {
            "eid": entity_id,
            "evid": event_id,
            "conf": confidence,
            "source": source_doc_id or "",
        }
        try:
            self.graph.query(
                """
                MATCH (e:Entity {id: $eid}), (ev:Event {id: $evid})
                MERGE (e)-[r:PRODUCES]->(ev)
                ON CREATE SET r.confidence = $conf, r.source_doc_id = $source
                """,
                params=params,
            )
        except Exception as e:
            logger.warning(
                "falkordb.produces.failed", entity=entity_id, event=event_id, error=str(e)
            )

    def add_consumes(
        self,
        entity_id: str,
        event_id: str,
        confidence: float = 1.0,
        source_doc_id: str | None = None,
    ) -> None:
        """Add CONSUMES relationship from Entity to Event."""
        params = {
            "eid": entity_id,
            "evid": event_id,
            "conf": confidence,
            "source": source_doc_id or "",
        }
        try:
            self.graph.query(
                """
                MATCH (e:Entity {id: $eid}), (ev:Event {id: $evid})
                MERGE (e)-[r:CONSUMES]->(ev)
                ON CREATE SET r.confidence = $conf, r.source_doc_id = $source
                """,
                params=params,
            )
        except Exception as e:
            logger.warning(
                "falkordb.consumes.failed", entity=entity_id, event=event_id, error=str(e)
            )

    # === Query Operations ===

    def execute_cypher(self, query: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Execute a Cypher query and return results as list of dicts."""
        result = self.graph.query(query, params=params or {})
        if not result.result_set:
            return []
        # Extract column names from header
        headers = [col[1] if isinstance(col, (list, tuple)) else str(col) for col in result.header]
        return [dict(zip(headers, row)) for row in result.result_set]

    def get_entity(self, entity_id: str) -> dict | None:
        """Get an entity by ID."""
        results = self.execute_cypher(
            "MATCH (e:Entity {id: $id}) RETURN e", {"id": entity_id}
        )
        return results[0] if results else None

    def get_entity_graph(self, entity_id: str, depth: int = 2) -> dict:
        """Get an entity and all related nodes up to depth.

        Filters out EXTRACTED_FROM edges to only return domain relationships.
        """
        # Domain relationship types only (exclude EXTRACTED_FROM)
        domain_rels = "CONTAINS|REFERENCES|PRODUCES|CONSUMES"
        nodes = self.execute_cypher(
            f"""
            MATCH (e:Entity {{id: $id}})-[:{domain_rels}*1..{depth}]-(n)
            RETURN DISTINCT labels(n)[0] as node_type, n.id as id, n.name as name
            """,
            {"id": entity_id},
        )

        edges = self.execute_cypher(
            f"""
            MATCH (e:Entity {{id: $id}})-[r:{domain_rels}]-()
            RETURN DISTINCT type(r) as rel_type
            """,
            {"id": entity_id},
        )
        edge_types = [e["rel_type"] for e in edges]

        return {
            "center": entity_id,
            "nodes": nodes,
            "edge_types": edge_types,
        }

    def get_all_entities(self) -> list[dict]:
        """Get all entities."""
        return self.execute_cypher(
            "MATCH (e:Entity) RETURN e.id as id, e.name as name, e.code_class as code_class"
        )

    def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 5,
    ) -> list[dict]:
        """Find path between two nodes."""
        return self.execute_cypher(
            f"""
            MATCH (a {{id: $from}})-[*1..{max_depth}]-(b {{id: $to}})
            RETURN a.name as start_name, b.name as end_name
            """,
            {"from": from_id, "to": to_id},
        )

    # === Provenance Queries ===

    def get_document_impact(self, doc_id: str) -> list[dict]:
        """Get all nodes extracted from a given document.

        Args:
            doc_id: Document identifier.

        Returns:
            List of dicts with node_type, id, name, role, confidence.
        """
        return self.execute_cypher(
            """
            MATCH (n)-[r:EXTRACTED_FROM]->(d:Document {id: $did})
            RETURN labels(n)[0] as node_type, n.id as id, n.name as name,
                   r.role as role, r.confidence as confidence
            """,
            {"did": doc_id},
        )

    def get_node_provenance(self, node_id: str) -> list[dict]:
        """Get all documents that contributed to a given node.

        Args:
            node_id: Node identifier.

        Returns:
            List of dicts with doc_id, title, path, role, confidence.
        """
        return self.execute_cypher(
            """
            MATCH (n {id: $nid})-[r:EXTRACTED_FROM]->(d:Document)
            RETURN d.id as doc_id, d.title as title, d.path as path,
                   r.role as role, r.confidence as confidence
            """,
            {"nid": node_id},
        )

    # === Utility ===

    def delete_by_source_doc(self, source_doc_id: str) -> None:
        """Delete a document and its exclusive nodes using cascade.

        Steps:
        1. Delete EXTRACTED_FROM edges pointing to the Document
        2. Delete domain relationships with source_doc_id = X
        3. Delete orphan nodes (no remaining EXTRACTED_FROM to any Document)
        4. Delete the Document node
        """
        log = logger.bind(source_doc_id=source_doc_id)
        log.debug("falkordb.delete_by_source.start")

        # Step 1: Delete EXTRACTED_FROM edges to this document
        try:
            self.graph.query(
                """
                MATCH (n)-[r:EXTRACTED_FROM]->(d:Document {id: $doc_id})
                DELETE r
                """,
                params={"doc_id": source_doc_id},
            )
        except Exception:
            pass

        # Step 2: Delete domain relationships with source_doc_id
        for rel_type in ["CONTAINS", "REFERENCES", "PRODUCES", "CONSUMES", "RELATED_TO"]:
            try:
                self.graph.query(
                    f"""
                    MATCH ()-[r:{rel_type}]->()
                    WHERE r.source_doc_id = $doc_id
                    DELETE r
                    """,
                    params={"doc_id": source_doc_id},
                )
            except Exception:
                pass

        # Step 3: Delete orphan nodes (no EXTRACTED_FROM to any Document)
        for node_type in ["Entity", "Concept", "Event"]:
            try:
                self.graph.query(
                    f"""
                    MATCH (n:{node_type})
                    OPTIONAL MATCH (n)-[r:EXTRACTED_FROM]->(:Document)
                    WITH n WHERE r IS NULL
                    DETACH DELETE n
                    """,
                )
            except Exception:
                pass

        # Step 4: Delete the Document node
        try:
            self.graph.query(
                """
                MATCH (d:Document {id: $doc_id})
                DETACH DELETE d
                """,
                params={"doc_id": source_doc_id},
            )
        except Exception:
            pass

        log.info("falkordb.delete_by_source.complete")

    def get_stats(self) -> dict:
        """Get database statistics."""
        stats = {}

        for node_type in ["Entity", "Concept", "Event", "Document"]:
            try:
                result = self.execute_cypher(f"MATCH (n:{node_type}) RETURN count(n) as cnt")
                stats[f"{node_type.lower()}_count"] = result[0]["cnt"] if result else 0
            except Exception:
                stats[f"{node_type.lower()}_count"] = 0

        return stats
