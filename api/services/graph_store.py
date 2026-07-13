"""
Graph Store Service — Neo4j wrapper for legal knowledge graph.
Handles section↔act relationships, citations, definitions, and multi-hop queries.
"""

import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import Neo4jError

from api.config import settings


@dataclass
class GraphNode:
    """Graph node representation."""
    id: str
    labels: List[str]
    properties: Dict[str, Any]


@dataclass
class GraphRelationship:
    """Graph relationship representation."""
    id: str
    type: str
    start_node_id: str
    end_node_id: str
    properties: Dict[str, Any]


@dataclass
class GraphPath:
    """Graph path for multi-hop queries."""
    nodes: List[GraphNode]
    relationships: List[GraphRelationship]
    length: int


class GraphStore:
    """Async Neo4j wrapper for legal knowledge graph."""
    
    # Node labels
    ACT = "Act"
    SECTION = "Section"
    RULE = "Rule"
    NOTIFICATION = "Notification"
    CIRCULAR = "Circular"
    CASE_LAW = "CaseLaw"
    DEFINITION = "Definition"
    CONCEPT = "Concept"
    COURT = "Court"
    JUDGE = "Judge"
    
    # Relationship types
    HAS_SECTION = "HAS_SECTION"
    HAS_SUBSECTION = "HAS_SUBSECTION"
    HAS_CHAPTER = "HAS_CHAPTER"
    CITES = "CITES"
    DEFINES = "DEFINES"
    AMENDS = "AMENDS"
    OVERRIDES = "OVERRIDES"
    REFERS_TO = "REFERS_TO"
    INTERPRETS = "INTERPRETS"
    DECIDED_BY = "DECIDED_BY"
    DELIVERED_BY = "DELIVERED_BY"
    RELATED_TO = "RELATED_TO"
    
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None,
    ):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.database = database or settings.NEO4J_DATABASE
        self._driver: Optional[AsyncDriver] = None
    
    async def connect(self):
        """Initialize Neo4j driver and create constraints/indexes."""
        self._driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
        )
        
        # Verify connectivity
        await self._driver.verify_connectivity()
        
        # Create constraints and indexes
        await self._create_schema()
    
    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None
    
    def _get_session(self) -> AsyncSession:
        if not self._driver:
            raise RuntimeError("GraphStore not connected. Call connect() first.")
        return self._driver.session(database=self.database)
    
    async def _create_schema(self):
        """Create constraints and indexes."""
        async with self._get_session() as session:
            # Unique constraints
            constraints = [
                f"CREATE CONSTRAINT act_id_unique IF NOT EXISTS FOR (a:{self.ACT}) REQUIRE a.id IS UNIQUE",
                f"CREATE CONSTRAINT section_id_unique IF NOT EXISTS FOR (s:{self.SECTION}) REQUIRE s.id IS UNIQUE",
                f"CREATE CONSTRAINT case_id_unique IF NOT EXISTS FOR (c:{self.CASE_LAW}) REQUIRE c.id IS UNIQUE",
                f"CREATE CONSTRAINT notification_id_unique IF NOT EXISTS FOR (n:{self.NOTIFICATION}) REQUIRE n.id IS UNIQUE",
                f"CREATE CONSTRAINT definition_id_unique IF NOT EXISTS FOR (d:{self.DEFINITION}) REQUIRE d.id IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    await session.run(constraint)
                except Neo4jError:
                    pass  # May already exist
            
            # Indexes for common lookups
            indexes = [
                f"CREATE INDEX act_name_idx IF NOT EXISTS FOR (a:{self.ACT}) ON (a.name)",
                f"CREATE INDEX section_number_idx IF NOT EXISTS FOR (s:{self.SECTION}) ON (s.number)",
                f"CREATE INDEX section_act_idx IF NOT EXISTS FOR (s:{self.SECTION}) ON (s.act_name)",
                f"CREATE INDEX case_citation_idx IF NOT EXISTS FOR (c:{self.CASE_LAW}) ON (c.citation)",
                f"CREATE INDEX notification_date_idx IF NOT EXISTS FOR (n:{self.NOTIFICATION}) ON (n.effective_date)",
                f"CREATE FULLTEXT INDEX section_text_fulltext IF NOT EXISTS FOR (s:{self.SECTION}) ON EACH [s.text]",
                f"CREATE FULLTEXT INDEX case_text_fulltext IF NOT EXISTS FOR (c:{self.CASE_LAW}) ON EACH [c.facts, c.holding, c.ratio]",
                f"CREATE FULLTEXT INDEX fulltext_index IF NOT EXISTS FOR (n:{self.ACT}|{self.SECTION}|{self.CASE_LAW}|{self.NOTIFICATION}|{self.DEFINITION}) ON EACH [n.text, n.title, n.citation, n.name, n.number]",
            ]
            
            for index in indexes:
                try:
                    await session.run(index)
                except Neo4jError:
                    pass
    
    # ─── Act Operations ──────────────────────────────────────────────────────
    
    async def upsert_act(
        self,
        act_name: str,
        act_type: str = "Principal",
        year: int = None,
        ministry: str = None,
        description: str = None,
        effective_date: str = None,
    ) -> str:
        """Create or update an Act node."""
        async with self._get_session() as session:
            result = await session.run(
                f"""
                MERGE (a:{self.ACT} {{name: $act_name}})
                SET a.act_type = $act_type,
                    a.year = $year,
                    a.ministry = $ministry,
                    a.description = $description,
                    a.effective_date = $effective_date,
                    a.updated_at = datetime()
                RETURN a.id as id
                """,
                act_name=act_name,
                act_type=act_type,
                year=year,
                ministry=ministry,
                description=description,
                effective_date=effective_date,
            )
            record = await result.single()
            return record["id"]
    
    # ─── Section Operations ──────────────────────────────────────────────────
    
    async def upsert_section(
        self,
        act_name: str,
        section_number: str,
        text: str,
        subsection: str = None,
        chapter: str = None,
        marginal_note: str = None,
        is_amended: bool = False,
        amendment_date: str = None,
    ) -> str:
        """Create or update a Section node and link to Act."""
        async with self._get_session() as session:
            # Ensure act exists
            await session.run(
                f"MERGE (a:{self.ACT} {{name: $act_name}})",
                act_name=act_name,
            )
            
            # Upsert section
            result = await session.run(
                f"""
                MATCH (a:{self.ACT} {{name: $act_name}})
                MERGE (s:{self.SECTION} {{act_name: $act_name, number: $section_number}})
                SET s.text = $text,
                    s.subsection = $subsection,
                    s.chapter = $chapter,
                    s.marginal_note = $marginal_note,
                    s.is_amended = $is_amended,
                    s.amendment_date = $amendment_date,
                    s.updated_at = datetime()
                MERGE (a)-[:{self.HAS_SECTION}]->(s)
                RETURN s.id as id
                """,
                act_name=act_name,
                section_number=section_number,
                text=text,
                subsection=subsection,
                chapter=chapter,
                marginal_note=marginal_note,
                is_amended=is_amended,
                amendment_date=amendment_date,
            )
            record = await result.single()
            return record["id"]
    
    # ─── Citation Relationships ──────────────────────────────────────────────
    
    async def add_citation(
        self,
        citing_act: str,
        citing_section: str,
        cited_act: str,
        cited_section: str,
        citation_type: str = "REFERS_TO",
    ):
        """Add citation relationship between sections."""
        async with self._get_session() as session:
            await session.run(
                f"""
                MATCH (citing:{self.SECTION} {{act_name: $citing_act, number: $citing_section}})
                MATCH (cited:{self.SECTION} {{act_name: $cited_act, number: $cited_section}})
                MERGE (citing)-[r:{citation_type}]->(cited)
                SET r.created_at = datetime()
                """,
                citing_act=citing_act,
                citing_section=citing_section,
                cited_act=cited_act,
                cited_section=cited_section,
            )
    
    # ─── Definition Extraction ───────────────────────────────────────────────
    
    async def upsert_definition(
        self,
        term: str,
        defined_in_act: str,
        defined_in_section: str,
        definition_text: str,
        scope: str = "Act",
    ) -> str:
        """Create or update a Definition node."""
        async with self._get_session() as session:
            result = await session.run(
                f"""
                MERGE (d:{self.DEFINITION} {{term: $term, act_name: $defined_in_act}})
                SET d.definition_text = $definition_text,
                    d.scope = $scope,
                    d.section_number = $defined_in_section,
                    d.updated_at = datetime()
                WITH d
                MATCH (s:{self.SECTION} {{act_name: $defined_in_act, number: $defined_in_section}})
                MERGE (s)-[:{self.DEFINES}]->(d)
                RETURN d.id as id
                """,
                term=term,
                defined_in_act=defined_in_act,
                defined_in_section=defined_in_section,
                definition_text=definition_text,
                scope=scope,
            )
            record = await result.single()
            return record["id"]
    
    # ─── Case Law Operations ─────────────────────────────────────────────────
    
    async def upsert_case_law(
        self,
        citation: str,
        title: str,
        court: str,
        date: str,
        facts: str = None,
        holding: str = None,
        ratio: str = None,
        judges: List[str] = None,
        acts_referred: List[str] = None,
        sections_referred: List[Dict[str, str]] = None,
    ) -> str:
        """Create or update a CaseLaw node."""
        async with self._get_session() as session:
            # Upsert court
            await session.run(
                f"MERGE (c:{self.COURT} {{name: $court}})",
                court=court,
            )
            
            # Upsert case
            result = await session.run(
                f"""
                MERGE (cl:{self.CASE_LAW} {{citation: $citation}})
                SET cl.title = $title,
                    cl.date = $date,
                    cl.facts = $facts,
                    cl.holding = $holding,
                    cl.ratio = $ratio,
                    cl.updated_at = datetime()
                WITH cl
                MATCH (c:{self.COURT} {{name: $court}})
                MERGE (cl)-[:{self.DECIDED_BY}]->(c)
                RETURN cl.id as id
                """,
                citation=citation,
                title=title,
                court=court,
                date=date,
                facts=facts,
                holding=holding,
                ratio=ratio,
            )
            
            record = await result.single()
            case_id = record["id"]
            
            # Link judges
            if judges:
                for judge in judges:
                    await session.run(
                        f"""
                        MERGE (j:{self.JUDGE} {{name: $judge}})
                        WITH j
                        MATCH (cl:{self.CASE_LAW} {{citation: $citation}})
                        MERGE (cl)-[:{self.DELIVERED_BY}]->(j)
                        """,
                        judge=judge,
                        citation=citation,
                    )
            
            # Link sections referred
            if sections_referred:
                for sec in sections_referred:
                    await session.run(
                        f"""
                        MATCH (cl:{self.CASE_LAW} {{citation: $citation}})
                        MATCH (s:{self.SECTION} {{act_name: $act_name, number: $section_number}})
                        MERGE (cl)-[:{self.INTERPRETS}]->(s)
                        """,
                        citation=citation,
                        act_name=sec.get("act_name"),
                        section_number=sec.get("section_number"),
                    )
            
            return case_id
    
    # ─── Multi-hop Queries (GraphRAG) ────────────────────────────────────────
    
    async def find_related_sections(
        self,
        act_name: str,
        section_number: str,
        max_hops: int = 2,
        relationship_types: List[str] = None,
    ) -> List[GraphPath]:
        """Find sections connected via citations, definitions, amendments."""
        rel_types = relationship_types or [
            self.CITES, self.REFERS_TO, self.INTERPRETS,
            self.AMENDS, self.OVERRIDES, self.DEFINES,
        ]
        rel_filter = "|".join(rel_types)
        
        async with self._get_session() as session:
            result = await session.run(
                f"""
                MATCH (start:{self.SECTION} {{act_name: $act_name, number: $section_number}})
                CALL apoc.path.expandConfig(start, {{
                    relationshipFilter: $rel_filter,
                    minLevel: 1,
                    maxLevel: $max_hops,
                    labelFilter: +{self.SECTION},
                    uniqueness: 'NODE_GLOBAL'
                }}) YIELD path
                RETURN path
                LIMIT 50
                """,
                act_name=act_name,
                section_number=section_number,
                max_hops=max_hops,
                rel_filter=rel_filter,
            )
            
            paths = []
            async for record in result:
                path = record["path"]
                paths.append(self._convert_path(path))
            
            return paths
    
    async def find_interpretations(
        self,
        act_name: str,
        section_number: str,
    ) -> List[Dict[str, Any]]:
        """Find case law interpreting a specific section."""
        async with self._get_session() as session:
            result = await session.run(
                f"""
                MATCH (s:{self.SECTION} {{act_name: $act_name, number: $section_number}})
                <-[:{self.INTERPRETS}]-(cl:{self.CASE_LAW})
                OPTIONAL MATCH (cl)-[:{self.DECIDED_BY}]->(c:{self.COURT})
                RETURN cl.citation as citation,
                       cl.title as title,
                       cl.holding as holding,
                       cl.ratio as ratio,
                       cl.date as date,
                       c.name as court
                ORDER BY cl.date DESC
                LIMIT 20
                """,
                act_name=act_name,
                section_number=section_number,
            )
            
            interpretations = []
            async for record in result:
                interpretations.append(dict(record))
            
            return interpretations
    
    async def find_definitions_for_term(
        self,
        term: str,
        act_name: str = None,
    ) -> List[Dict[str, Any]]:
        """Find definitions of a term across acts."""
        async with self._get_session() as session:
            query = f"""
                MATCH (d:{self.DEFINITION})
                WHERE toLower(d.term) CONTAINS toLower($term)
            """
            params = {"term": term}
            
            if act_name:
                query += " AND d.act_name = $act_name"
                params["act_name"] = act_name
            
            query += """
                OPTIONAL MATCH (s:Section)-[:DEFINES]->(d)
                RETURN d.term as term,
                       d.definition_text as definition,
                       d.act_name as act_name,
                       d.section_number as section_number,
                       d.scope as scope
                LIMIT 20
            """
            
            result = await session.run(query, params)
            
            definitions = []
            async for record in result:
                definitions.append(dict(record))
            
            return definitions
    
    async def get_amendment_chain(
        self,
        act_name: str,
        section_number: str,
    ) -> List[Dict[str, Any]]:
        """Get amendment history for a section."""
        async with self._get_session() as session:
            result = await session.run(
                f"""
                MATCH (s:{self.SECTION} {{act_name: $act_name, number: $section_number}})
                OPTIONAL MATCH (s)<-[:{self.AMENDS}*1..5]-(amended:{self.SECTION})
                OPTIONAL MATCH (s)-[:{self.AMENDS}*1..5]->(amending:{self.SECTION})
                RETURN s as original,
                       collect(DISTINCT amended) as amended_by,
                       collect(DISTINCT amending) as amends
                """,
                act_name=act_name,
                section_number=section_number,
            )
            
            record = await result.single()
            if not record:
                return []
            
            chain = []
            if record["original"]:
                chain.append({"section": dict(record["original"]), "type": "original"})
            
            for am in record["amended_by"] or []:
                chain.append({"section": dict(am), "type": "amended_by"})
            
            for am in record["amends"] or []:
                chain.append({"section": dict(am), "type": "amends"})
            
            return chain
    
    # ─── Notification/Circular Linking ───────────────────────────────────────
    
    async def link_notification_to_sections(
        self,
        notification_id: str,
        notification_title: str,
        act_name: str,
        section_numbers: List[str],
        notification_type: str = "Notification",
    ):
        """Link a notification to sections it affects."""
        async with self._get_session() as session:
            # Create notification node
            await session.run(
                f"""
                MERGE (n:{self.NOTIFICATION} {{id: $notification_id}})
                SET n.title = $title,
                    n.type = $type,
                    n.updated_at = datetime()
                """,
                notification_id=notification_id,
                title=notification_title,
                type=notification_type,
            )
            
            # Link to sections
            for sec_num in section_numbers:
                await session.run(
                    f"""
                    MATCH (n:{self.NOTIFICATION} {{id: $notification_id}})
                    MATCH (s:{self.SECTION} {{act_name: $act_name, number: $section_number}})
                    MERGE (n)-[:{self.REFERS_TO}]->(s)
                    """,
                    notification_id=notification_id,
                    act_name=act_name,
                    section_number=sec_num,
                )
    
    # ─── Utility ─────────────────────────────────────────────────────────────
    
    def _convert_path(self, path) -> GraphPath:
        """Convert Neo4j path to GraphPath."""
        nodes = []
        relationships = []
        
        for node in path.nodes:
            nodes.append(GraphNode(
                id=str(node.id),
                labels=list(node.labels),
                properties=dict(node),
            ))
        
        for rel in path.relationships:
            relationships.append(GraphRelationship(
                id=str(rel.id),
                type=rel.type,
                start_node_id=str(rel.start_node.id),
                end_node_id=str(rel.end_node.id),
                properties=dict(rel),
            ))
        
        return GraphPath(
            nodes=nodes,
            relationships=relationships,
            length=len(relationships),
        )
    
    async def run_cypher(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute arbitrary Cypher query."""
        async with self._get_session() as session:
            result = await session.run(query, params or {})
            records = []
            async for record in result:
                records.append(dict(record))
            return records


# Global instance
graph_store = GraphStore()