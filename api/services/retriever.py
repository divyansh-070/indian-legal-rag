"""
Hybrid Retriever — Combines Qdrant vector search with Neo4j graph traversal.
Implements reciprocal rank fusion for merging results.
"""

import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from collections import defaultdict

from api.services.vector_store import vector_store, SearchResult
from api.services.graph_store import graph_store, GraphPath
from api.config import settings
from api.services.llm import llm_service


@dataclass
class RetrievedChunk:
    """Unified retrieved chunk with metadata."""
    id: str
    text: str
    score: float
    source: str  # "vector" | "graph" | "hybrid"
    act_name: Optional[str] = None
    section_number: Optional[str] = None
    chapter: Optional[str] = None
    doc_type: Optional[str] = None
    citation: Optional[str] = None
    court: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class HybridRetriever:
    """
    Combines vector similarity search with graph-based retrieval.
    Uses Reciprocal Rank Fusion (RRF) for result merging.
    """
    
    def __init__(
        self,
        top_k_vector: int = 20,
        top_k_graph: int = 10,
        top_k_final: int = 8,
        rrf_k: int = 60,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
    ):
        self.top_k_vector = top_k_vector
        self.top_k_graph = top_k_graph
        self.top_k_final = top_k_final
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
    
    async def retrieve(
        self,
        query: str,
        filters: Dict[str, Any] = None,
        use_graph: bool = True,
        graph_hops: int = 2,
    ) -> List[RetrievedChunk]:
        """
        Main retrieval entry point.
        1. Vector search in Qdrant
        2. Graph traversal in Neo4j (if enabled)
        3. Merge via RRF
        4. Return top-K fused results
        """
        # Run vector and graph retrieval in parallel
        vector_task = self._vector_search(query, filters)
        graph_task = self._graph_search(query, graph_hops) if use_graph else asyncio.sleep(0, result=[])
        
        vector_results, graph_results = await asyncio.gather(vector_task, graph_task)
        
        # Fuse results
        fused = self._reciprocal_rank_fusion(vector_results, graph_results)
        
        return fused[:self.top_k_final]
    
    async def _vector_search(
        self,
        query: str,
        filters: Dict[str, Any] = None,
    ) -> List[RetrievedChunk]:
        """Semantic vector search via Qdrant."""
        results = await vector_store.search(
            query=query,
            limit=self.top_k_vector,
            filters=filters,
            score_threshold=0.55,
        )
        
        chunks = []
        for r in results:
            payload = r.payload
            chunks.append(RetrievedChunk(
                id=r.id,
                text=payload.get("text", ""),
                score=r.score,
                source="vector",
                act_name=payload.get("act_name"),
                section_number=payload.get("section_number"),
                chapter=payload.get("chapter"),
                doc_type=payload.get("doc_type"),
                citation=payload.get("citation"),
                court=payload.get("court"),
                metadata=payload.get("metadata", {}),
            ))
        
        return chunks
    
    async def _graph_search(
        self,
        query: str,
        max_hops: int = 2,
    ) -> List[RetrievedChunk]:
        """Graph-based retrieval via Neo4j."""
        # Extract key entities from query
        entities = await self._extract_entities(query)
        
        graph_chunks = []
        
        # For each detected entity, traverse graph
        for entity in entities:
            if entity["type"] == "section":
                paths = await graph_store.find_related_sections(
                    act_name=entity["act"],
                    section_number=entity["section"],
                    max_hops=max_hops,
                )
                
                for path in paths:
                    for node in path.nodes:
                        if node.labels and "Section" in node.labels:
                            props = node.properties
                            graph_chunks.append(RetrievedChunk(
                                id=node.id,
                                text=props.get("text", ""),
                                score=1.0 / (path.length + 1),  # Decay by hop distance
                                source="graph",
                                act_name=props.get("act_name"),
                                section_number=props.get("number"),
                                chapter=props.get("chapter"),
                                doc_type="act",
                                metadata={"graph_hops": path.length, "path_type": "citation"},
                            ))
            
            elif entity["type"] == "case_law":
                interpretations = await graph_store.find_interpretations(
                    act_name=entity.get("act"),
                    section_number=entity.get("section"),
                )
                
                for interp in interpretations:
                    graph_chunks.append(RetrievedChunk(
                        id=interp.get("citation", ""),
                        text=f"{interp.get('title', '')}\nHolding: {interp.get('holding', '')}\nRatio: {interp.get('ratio', '')}",
                        score=0.9,
                        source="graph",
                        doc_type="case_law",
                        citation=interp.get("citation"),
                        court=interp.get("court"),
                        metadata={"graph_path": "interpretation"},
                    ))
        
        # Also search for definitions
        definitions = await graph_store.find_definitions_for_term(query)
        for defn in definitions:
            graph_chunks.append(RetrievedChunk(
                id=f"def_{defn.get('term', '')}_{defn.get('act_name', '')}",
                text=f"Definition of '{defn.get('term')}': {defn.get('definition')}",
                score=0.85,
                source="graph",
                act_name=defn.get("act_name"),
                section_number=defn.get("section_number"),
                doc_type="definition",
                metadata={"graph_path": "definition"},
            ))
        
        return graph_chunks
    
    async def _extract_entities(self, query: str) -> List[Dict[str, Any]]:
        """Extract legal entities from query using LLM."""
        from pydantic import BaseModel
        from typing import List, Optional
        
        class Entity(BaseModel):
            type: str  # "act" | "section" | "case_law" | "term"
            act: Optional[str] = None
            section: Optional[str] = None
            citation: Optional[str] = None
            term: Optional[str] = None
        
        class EntityList(BaseModel):
            entities: List[Entity]
        
        prompt = f"""Extract legal entities from this query about Indian law:

Query: "{query}"

Identify:
1. Acts mentioned (e.g., "GST Act", "Companies Act 2013", "Income Tax Act")
2. Specific sections (e.g., "Section 16", "Section 44AD(1)")
3. Case law citations (e.g., "2023 SCC 5 123", "AIR 2022 SC 456")
4. Key legal terms for definition lookup

Return as JSON with entities array."""
        
        try:
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=EntityList,
                system="You are a legal entity extractor for Indian law. Be precise.",
            )
            return [e.model_dump() for e in result.entities]
        except Exception:
            # Fallback: simple regex extraction
            return self._fallback_entity_extraction(query)
    
    def _fallback_entity_extraction(self, query: str) -> List[Dict[str, Any]]:
        """Regex-based fallback entity extraction."""
        import re
        entities = []
        
        # Common Indian acts
        acts_pattern = r"(GST|Goods and Services Tax|Companies Act|Income Tax Act|Constitution|IPC|CrPC|CPC|SEBI|FEMA|Arbitration|Contract Act|Transfer of Property|Specific Relief|Limitation Act|Negotiable Instruments|Partnership Act|Sale of Goods|Consumer Protection|RTI|Right to Information|Motor Vehicles|Environment Protection|Air Prevention|Water Prevention|Factories Act|Industrial Disputes|Trade Marks|Patents|Copyright|Designs|Geographical Indications|Semiconductor|Plant Varieties|Biological Diversity|Competition Act|Insolvency|Bankruptcy|NCLT|NCLAT|SEBI LODR|LODR)[\s\w]*"
        
        for match in re.finditer(acts_pattern, query, re.IGNORECASE):
            entities.append({"type": "act", "act": match.group(0).strip()})
        
        # Section references
        section_pattern = r"(?:Section|Sec\.?|§)\s*(\d+[A-Z]?(?:\(\d+\))?(?:\(\w+\))?)"
        for match in re.finditer(section_pattern, query, re.IGNORECASE):
            entities.append({"type": "section", "section": match.group(1)})
        
        # Case citations
        citation_pattern = r"(?:\d{4}\s+)?(?:SCC|SCR|AIR|SC|HC|NCLT|NCLAT|SAT|CESTAT|ITAT|GSTAT)\s+\d+\s+\d+"
        for match in re.finditer(citation_pattern, query, re.IGNORECASE):
            entities.append({"type": "case_law", "citation": match.group(0).strip()})
        
        return entities
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievedChunk],
        graph_results: List[RetrievedChunk],
    ) -> List[RetrievedChunk]:
        """
        Merge results using Reciprocal Rank Fusion.
        RRF score = sum(1 / (k + rank)) for each result list.
        """
        # Track scores by chunk ID
        rrf_scores = defaultdict(float)
        chunk_map = {}
        
        # Process vector results
        for rank, chunk in enumerate(vector_results):
            rrf_scores[chunk.id] += self.vector_weight * (1.0 / (self.rrf_k + rank + 1))
            chunk_map[chunk.id] = chunk
        
        # Process graph results
        for rank, chunk in enumerate(graph_results):
            rrf_scores[chunk.id] += self.graph_weight * (1.0 / (self.rrf_k + rank + 1))
            # Merge metadata if chunk already exists
            if chunk.id in chunk_map:
                existing = chunk_map[chunk.id]
                existing.source = "hybrid"
                existing.score = max(existing.score, chunk.score)
                existing.metadata.update(chunk.metadata)
            else:
                chunk_map[chunk.id] = chunk
        
        # Sort by RRF score
        sorted_chunks = sorted(
            chunk_map.values(),
            key=lambda c: rrf_scores[c.id],
            reverse=True,
        )
        
        # Update scores to RRF scores
        for chunk in sorted_chunks:
            chunk.score = rrf_scores[chunk.id]
        
        return sorted_chunks
    
    async def retrieve_by_section(
        self,
        act_name: str,
        section_number: str,
        include_interpretations: bool = True,
        include_amendments: bool = True,
    ) -> List[RetrievedChunk]:
        """Direct section lookup with graph enrichment."""
        # Exact vector lookup
        vector_results = await vector_store.search_by_section(
            act_name=act_name,
            section_number=section_number,
            limit=5,
        )
        
        chunks = []
        for r in vector_results:
            payload = r.payload
            chunks.append(RetrievedChunk(
                id=r.id,
                text=payload.get("text", ""),
                score=r.score,
                source="vector",
                act_name=payload.get("act_name"),
                section_number=payload.get("section_number"),
                chapter=payload.get("chapter"),
                doc_type=payload.get("doc_type"),
            ))
        
        # Graph enrichment
        if include_interpretations:
            interpretations = await graph_store.find_interpretations(act_name, section_number)
            for interp in interpretations:
                chunks.append(RetrievedChunk(
                    id=interp.get("citation", ""),
                    text=f"{interp.get('title', '')}\nHolding: {interp.get('holding', '')}\nRatio: {interp.get('ratio', '')}",
                    score=0.9,
                    source="graph",
                    doc_type="case_law",
                    citation=interp.get("citation"),
                    court=interp.get("court"),
                    metadata={"graph_path": "interpretation"},
                ))
        
        if include_amendments:
            amendments = await graph_store.get_amendment_chain(act_name, section_number)
            for amend in amendments:
                if amend["type"] != "original":
                    props = amend["section"].get("properties", {})
                    chunks.append(RetrievedChunk(
                        id=amend["section"].get("id", ""),
                        text=props.get("text", ""),
                        score=0.8,
                        source="graph",
                        act_name=props.get("act_name"),
                        section_number=props.get("number"),
                        metadata={"graph_path": f"amendment_{amend['type']}"},
                    ))
        
        return chunks


# Global instance
hybrid_retriever = HybridRetriever(
    top_k_vector=settings.TOP_K_VECTOR,
    top_k_graph=settings.TOP_K_GRAPH,
    top_k_final=settings.TOP_K_FINAL,
)