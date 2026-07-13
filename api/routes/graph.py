"""
Graph API Routes — Direct graph queries and exploration endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional

from api.services.graph_store import graph_store
from api.config import settings


router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/section/{act_name}/{section_number}/neighborhood")
async def get_section_neighborhood(
    act_name: str,
    section_number: str,
    max_hops: int = Query(2, ge=1, le=3),
    relationship_types: Optional[str] = None,
):
    """Get graph neighborhood around a section (citations, definitions, amendments)."""
    rel_types = relationship_types.split(",") if relationship_types else None
    
    paths = await graph_store.find_related_sections(
        act_name=act_name,
        section_number=section_number,
        max_hops=max_hops,
        relationship_types=rel_types,
    )
    
    return {
        "center": {"act_name": act_name, "section_number": section_number},
        "paths": [
            {
                "length": p.length,
                "nodes": [{"id": n.id, "labels": n.labels, "props": n.properties} for n in p.nodes],
                "relationships": [
                    {"id": r.id, "type": r.type, "start": r.start_node_id, "end": r.end_node_id, "props": r.properties}
                    for r in p.relationships
                ],
            }
            for p in paths
        ],
    }


@router.get("/section/{act_name}/{section_number}/interpretations")
async def get_interpretations(
    act_name: str,
    section_number: str,
    limit: int = Query(20, ge=1, le=50),
):
    """Get case law interpretations of a specific section."""
    interpretations = await graph_store.find_interpretations(
        act_name=act_name,
        section_number=section_number,
    )
    
    return {
        "act_name": act_name,
        "section_number": section_number,
        "interpretations": interpretations[:limit],
    }


@router.get("/section/{act_name}/{section_number}/amendments")
async def get_amendment_chain(
    act_name: str,
    section_number: str,
):
    """Get amendment history for a section."""
    chain = await graph_store.get_amendment_chain(
        act_name=act_name,
        section_number=section_number,
    )
    
    return {
        "act_name": act_name,
        "section_number": section_number,
        "amendment_chain": chain,
    }


@router.post("/definitions")
async def get_definitions(term: str, act_name: str = None):
    """Search definitions across acts."""
    definitions = await graph_store.find_definitions_for_term(
        term=term,
        act_name=act_name,
    )
    
    return {
        "term": term,
        "act_filter": act_name,
        "definitions": definitions,
    }


@router.get("/act/{act_name}/stats")
async def get_act_stats(act_name: str):
    """Get graph statistics for an act."""
    result = await graph_store.run_cypher(
        f"""
        MATCH (a:Act {{name: $act_name}})
        OPTIONAL MATCH (a)-[:HAS_SECTION]->(s:Section)
        OPTIONAL MATCH (s)-[:DEFINES]->(d:Definition)
        OPTIONAL MATCH (s)<-[:INTERPRETS]-(cl:CaseLaw)
        OPTIONAL MATCH (s)-[:CITES|REFERS_TO|AMENDS|OVERRIDES]->(s2:Section)
        RETURN 
            count(DISTINCT s) as sections,
            count(DISTINCT d) as definitions,
            count(DISTINCT cl) as interpretations,
            count(DISTINCT s2) as cross_references
        """,
        {"act_name": act_name},
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Act not found")
    
    return {"act_name": act_name, **result[0]}


@router.get("/search")
async def search_graph(
    q: str = Query(..., min_length=2),
    node_types: str = "Section,CaseLaw,Definition",
    limit: int = Query(20, ge=1, le=100),
):
    """Full-text search across graph nodes."""
    types = node_types.split(",")
    
    result = await graph_store.run_cypher(
        f"""
        CALL db.index.fulltext.queryNodes('fulltext_index', $q)
        YIELD node, score
        WHERE any(label IN labels(node) WHERE label IN $labels)
        RETURN node, score, labels(node) as labels
        LIMIT $limit
        """,
        {"q": q, "labels": types, "limit": limit},
    )
    
    return {
        "query": q,
        "results": [
            {
                "id": str(r["node"].id),
                "labels": r["labels"],
                "score": r["score"],
                "properties": dict(r["node"]),
            }
            for r in result
        ],
    }