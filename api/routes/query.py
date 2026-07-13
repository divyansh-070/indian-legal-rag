"""
Query API Routes — Main research endpoint for legal research (citations, statutes, case law).
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from api.services.retriever import hybrid_retriever
from api.services.synthesizer import synthesizer_agent, AnswerFormat
from api.services.critic import critic_agent
from api.config import settings


router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000, description="Legal question to answer")
    format: AnswerFormat = Field(default=AnswerFormat.STRUCTURED, description="Response format")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters (act_name, doc_type, etc.)")
    use_graph: bool = Field(default=True, description="Enable GraphRAG retrieval")
    top_k: Optional[int] = Field(default=None, ge=1, le=50, description="Override default top-K")


class QueryResponse(BaseModel):
    answer: Dict[str, Any]
    retrieval_metadata: Dict[str, Any]
    critic_metadata: Optional[Dict[str, Any]] = None


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Main query endpoint — retrieves relevant legal sources and generates cited answer.
    """
    try:
        # Override top_k if provided
        if request.top_k:
            original_final = hybrid_retriever.top_k_final
            hybrid_retriever.top_k_final = request.top_k
        
        # Retrieve relevant chunks
        chunks = await hybrid_retriever.retrieve(
            query=request.question,
            filters=request.filters,
            use_graph=request.use_graph,
            graph_hops=settings.GRAPH_HOPS,
        )
        
        if not chunks:
            return QueryResponse(
                answer={
                    "query": request.question,
                    "summary": "No relevant legal sources found for this query.",
                    "sections": [],
                    "citations": [],
                    "confidence": 0.0,
                },
                retrieval_metadata={
                    "total_chunks": 0,
                    "message": "Try broadening your query or checking act/section names.",
                },
            )
        
        # Synthesize answer
        answer = await synthesizer_agent.synthesize(
            query=request.question,
            chunks=chunks,
            format=request.format,
        )
        
        # Restore top_k
        if request.top_k:
            hybrid_retriever.top_k_final = original_final
        
        # Build response
        response_data = {
            "query": answer.query,
            "summary": answer.summary,
            "sections": [
                {
                    "heading": sec.heading,
                    "content": sec.content,
                    "citations": [c.model_dump() for c in sec.citations],
                    "confidence": sec.confidence,
                }
                for sec in answer.sections
            ],
            "citations": [c.model_dump() for c in answer.citations],
            "confidence": answer.confidence,
            "format": answer.format.value,
        }
        
        critic_meta = None
        if answer.critic_result:
            critic_meta = {
                "overall_faithfulness": answer.critic_result.overall_faithfulness,
                "hallucination_count": answer.critic_result.hallucination_count,
                "missing_citation_count": answer.critic_result.missing_citation_count,
                "stale_law_warnings": answer.critic_result.stale_law_warnings,
                "summary": answer.critic_result.summary,
            }
        
        return QueryResponse(
            answer=response_data,
            retrieval_metadata=answer.retrieval_metadata,
            critic_metadata=critic_meta,
        )
    
    except Exception as e:
        if request.top_k:
            hybrid_retriever.top_k_final = original_final
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/retrieve-only")
async def retrieve_only(request: QueryRequest):
    """
    Retrieve chunks without synthesis — for debugging/inspection.
    """
    try:
        chunks = await hybrid_retriever.retrieve(
            query=request.question,
            filters=request.filters,
            use_graph=request.use_graph,
            graph_hops=settings.GRAPH_HOPS,
        )
        
        return {
            "query": request.question,
            "chunks": [
                {
                    "id": c.id,
                    "text": c.text[:500] + "..." if len(c.text) > 500 else c.text,
                    "score": c.score,
                    "source": c.source,
                    "act_name": c.act_name,
                    "section_number": c.section_number,
                    "chapter": c.chapter,
                    "doc_type": c.doc_type,
                    "citation": c.citation,
                    "court": c.court,
                }
                for c in chunks
            ],
            "count": len(chunks),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.get("/suggest")
async def suggest_queries(q: str = "", limit: int = 5):
    """
    Suggest related queries based on partial input.
    """
    # Simple suggestions based on common legal query patterns
    suggestions = [
        "What is the GST registration threshold for service providers?",
        "Section 44AD presumptive taxation eligibility criteria",
        "Director disqualification under Companies Act 2013",
        "Income Tax Section 80C deduction limits",
        "GST ITC reversal rules under Section 17(5)",
        "Supreme Court judgments on arbitration clause severability",
        "SEBI LODR compliance requirements for listed entities",
        "IBC CIRP timeline and extension rules",
        "Transfer pricing documentation requirements",
        "TDS rates for non-resident payments",
    ]
    
    # Filter by partial match
    if q:
        q_lower = q.lower()
        suggestions = [s for s in suggestions if q_lower in s.lower()]
    
    return {"suggestions": suggestions[:limit]}