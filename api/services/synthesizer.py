"""
Synthesizer Agent — Generates structured answers from retrieved chunks.
Integrates with Critic Agent for self-correction.
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from api.services.llm import llm_service
from api.services.retriever import RetrievedChunk
from api.services.critic import critic_agent, CriticResult, VerificationStatus
from api.config import settings
from pydantic import BaseModel, Field


class AnswerFormat(str, Enum):
    STRUCTURED = "structured"
    MARKDOWN = "markdown"
    JSON = "json"
    BRIEF = "brief"


@dataclass
class SourceCitation:
    """Citation for a source."""
    id: str
    score: float
    act_name: Optional[str] = None
    section_number: Optional[str] = None
    doc_type: Optional[str] = None
    citation: Optional[str] = None
    court: Optional[str] = None
    source_type: str = "vector"  # vector, graph, hybrid


@dataclass
class AnswerSection:
    """Structured answer section."""
    heading: str
    content: str
    citations: List[SourceCitation]
    confidence: float


@dataclass
class SynthesizedAnswer:
    """Final synthesized answer with full provenance."""
    query: str
    summary: str
    sections: List[AnswerSection]
    citations: List[SourceCitation]
    confidence: float
    critic_result: Optional[CriticResult] = None
    retrieval_metadata: Dict[str, Any] = None
    format: AnswerFormat = AnswerFormat.STRUCTURED


class SynthesizerAgent:
    """
    Generates final answer from retrieved chunks with critic feedback loop.
    """
    
    def __init__(
        self,
        max_iterations: int = 2,
        min_confidence: float = 0.6,
    ):
        self.max_iterations = max_iterations
        self.min_confidence = min_confidence
    
    async def synthesize(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        format: AnswerFormat = AnswerFormat.STRUCTURED,
        previous_critic: Optional[CriticResult] = None,
    ) -> SynthesizedAnswer:
        """Generate answer with optional critic-in-the-loop refinement."""
        
        # Build source map for citations
        source_map = {f"[{i+1}]": chunk for i, chunk in enumerate(chunks)}
        
        # Generate initial answer
        answer = await self._generate_answer(query, chunks, format, source_map, previous_critic)
        
        # Run critic
        critic_result = await critic_agent.verify_answer(
            self._flatten_answer(answer),
            chunks,
            query,
        )
        answer.critic_result = critic_result
        
        # If critic finds issues and we have iterations left, refine
        iteration = 0
        while (critic_result.hallucination_count > 0 or 
               critic_result.missing_citation_count > 0) and iteration < self.max_iterations:
            
            # Refine based on critic feedback
            answer = await self._refine_answer(
                query, chunks, format, source_map, answer, critic_result
            )
            
            # Re-verify
            critic_result = await critic_agent.verify_answer(
                self._flatten_answer(answer),
                chunks,
                query,
            )
            answer.critic_result = critic_result
            iteration += 1
        
        return answer
    
    async def _generate_answer(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        format: AnswerFormat,
        source_map: Dict[str, RetrievedChunk],
        critic_feedback: Optional[CriticResult] = None,
    ) -> SynthesizedAnswer:
        """Generate answer using LLM with context."""
        
        # Build context from chunks
        context = self._build_context(chunks)
        
        # Format-specific prompts
        if format == AnswerFormat.STRUCTURED:
            system_prompt = self._get_structured_system_prompt()
        elif format == AnswerFormat.MARKDOWN:
            system_prompt = self._get_markdown_system_prompt()
        elif format == AnswerFormat.BRIEF:
            system_prompt = self._get_brief_system_prompt()
        else:
            system_prompt = self._get_structured_system_prompt()
        
        critic_guidance = ""
        if critic_feedback:
            critic_guidance = f"""
PREVIOUS CRITIC FEEDBACK (MUST ADDRESS):
{critic_feedback.summary}
Specific issues:
{chr(10).join([f"- {v.claim_text}: {v.reasoning}" for v in critic_feedback.verifications if v.status != VerificationStatus.SUPPORTED])}
"""
        
        prompt = f"""You are an expert Indian legal researcher. Answer the query using ONLY the provided sources.

QUERY: {query}

SOURCES:
{context}

{system_prompt}

{critic_guidance}

RULES:
1. Every legal assertion MUST have a citation [1], [2], etc. from sources
2. If source doesn't support a claim, say "Sources do not specify..." or omit
3. Distinguish between: statutory text, case law interpretation, notifications
4. Flag if law may be amended (check effective dates)
4. Use precise legal terminology
5. No hallucination - if not in sources, don't state it
6. Include disclaimer: "This is legal information, not advice. Verify current law and consult a qualified advocate."
"""
        
        # Use structured output for structured format
        if format == AnswerFormat.STRUCTURED:
            from pydantic import create_model
            from typing import List
            
            class StructuredResponse(BaseModel):
                summary: str
                sections: List[Dict[str, Any]]
            
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=StructuredResponse,
                system="You are a precise Indian legal researcher. Cite every claim. No hallucination.",
            )
            
            # Convert to SynthesizedAnswer
            citations = []
            for i, chunk in enumerate(chunks):
                citations.append(SourceCitation(
                    id=f"[{i+1}]",
                    act_name=chunk.act_name,
                    section_number=chunk.section_number,
                    doc_type=chunk.doc_type,
                    citation=chunk.citation,
                    court=chunk.court,
                    score=chunk.score,
                    source_type=chunk.source,
                ))
            
            sections = []
            for sec in result.sections:
                sec_citations = []
                for c in sec.get("citations", []):
                    if c in source_map:
                        idx = int(c.strip("[]")) - 1
                        if 0 <= idx < len(chunks):
                            ch = chunks[idx]
                            sec_citations.append(SourceCitation(
                                id=c,
                                act_name=ch.act_name,
                                section_number=ch.section_number,
                                doc_type=ch.doc_type,
                                citation=ch.citation,
                                court=ch.court,
                                score=ch.score,
                                source_type=ch.source,
                            ))
                
                sections.append(AnswerSection(
                    heading=sec.get("heading", ""),
                    content=sec.get("content", ""),
                    citations=sec_citations,
                    confidence=sec.get("confidence", 0.8),
                ))
            
            return SynthesizedAnswer(
                query=query,
                summary=result.summary,
                sections=sections,
                citations=citations,
                confidence=0.85,
                retrieval_metadata={
                    "total_chunks": len(chunks),
                    "vector_chunks": sum(1 for c in chunks if c.source == "vector"),
                    "graph_chunks": sum(1 for c in chunks if c.source == "graph"),
                    "hybrid_chunks": sum(1 for c in chunks if c.source == "hybrid"),
                },
                format=format,
            )
        
        else:
            # Free-form generation for markdown/brief
            response = await llm_service.generate(
                prompt=prompt,
                system="You are a precise Indian legal researcher. Cite every claim. No hallucination.",
            )
            
            citations = []
            for i, chunk in enumerate(chunks):
                citations.append(SourceCitation(
                    id=f"[{i+1}]",
                    act_name=chunk.act_name,
                    section_number=chunk.section_number,
                    doc_type=chunk.doc_type,
                    citation=chunk.citation,
                    court=chunk.court,
                    score=chunk.score,
                    source_type=chunk.source,
                ))
            
            return SynthesizedAnswer(
                query=query,
                summary=response[:500],
                sections=[AnswerSection(
                    heading="Answer",
                    content=response,
                    citations=[c for c in citations if f"[{i+1}]" in response for i, _ in enumerate(chunks)],
                    confidence=0.8,
                )],
                citations=[c for i, c in enumerate(citations) if f"[{i+1}]" in response],
                confidence=0.8,
                retrieval_metadata={
                    "total_chunks": len(chunks),
                },
                format=format,
            )
    
    async def _refine_answer(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        format: AnswerFormat,
        source_map: Dict[str, RetrievedChunk],
        previous_answer: SynthesizedAnswer,
        critic_result: CriticResult,
    ) -> SynthesizedAnswer:
        """Refine answer based on critic feedback."""
        
        issues = []
        for v in critic_result.verifications:
            if v.status != VerificationStatus.SUPPORTED:
                issues.append({
                    "claim": v.claim_text,
                    "issue": v.status.value,
                    "reasoning": v.reasoning,
                    "correction": v.suggested_correction,
                })
        
        context = self._build_context(chunks)
        
        prompt = f"""Refine this legal answer to fix the identified issues.

ORIGINAL QUERY: {query}

PREVIOUS ANSWER:
{self._flatten_answer(previous_answer)}

CRITIC ISSUES TO FIX:
{issues}

SOURCES (same as before):
{self._build_context(chunks)}

Generate corrected answer in the same format. Specifically:
- Remove or correct contradicted claims
- Add citations for missing-citation claims
- Mark stale law references with "⚠ Check current amendment status"
- Only include claims supported by sources

Output the complete corrected answer."""
        
        if format == AnswerFormat.STRUCTURED:
            from pydantic import create_model
            from typing import List
            
            class StructuredResponse(BaseModel):
                summary: str
                sections: List[Dict[str, Any]]
            
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=StructuredResponse,
                system="You are correcting a legal answer based on fact-checking feedback. Be precise.",
            )
            
            # Convert similar to _generate_answer
            citations = []
            for i, chunk in enumerate(chunks):
                citations.append(SourceCitation(
                    id=f"[{i+1}]",
                    act_name=chunk.act_name,
                    section_number=chunk.section_number,
                    doc_type=chunk.doc_type,
                    citation=chunk.citation,
                    court=chunk.court,
                    score=chunk.score,
                    source_type=chunk.source,
                ))
            
            sections = []
            for sec in result.sections:
                sec_citations = []
                for c in sec.get("citations", []):
                    if c in source_map:
                        idx = int(c.strip("[]")) - 1
                        if 0 <= idx < len(chunks):
                            ch = chunks[idx]
                            sec_citations.append(SourceCitation(
                                id=c,
                                act_name=ch.act_name,
                                section_number=ch.section_number,
                                doc_type=ch.doc_type,
                                citation=ch.citation,
                                court=ch.court,
                                score=ch.score,
                                source_type=ch.source,
                            ))
                
                sections.append(AnswerSection(
                    heading=sec.get("heading", ""),
                    content=sec.get("content", ""),
                    citations=sec_citations,
                    confidence=sec.get("confidence", 0.8),
                ))
            
            return SynthesizedAnswer(
                query=query,
                summary=result.summary,
                sections=sections,
                citations=citations,
                confidence=0.85,
                retrieval_metadata={
                    "total_chunks": len(chunks),
                    "vector_chunks": sum(1 for c in chunks if c.source == "vector"),
                    "graph_chunks": sum(1 for c in chunks if c.source == "graph"),
                    "hybrid_chunks": sum(1 for c in chunks if c.source == "hybrid"),
                },
                format=format,
            )
        
        else:
            response = await llm_service.generate(
                prompt=prompt,
                system="You are correcting a legal answer based on fact-checking feedback. Be precise.",
            )
            
            citations = []
            for i, chunk in enumerate(chunks):
                citations.append(SourceCitation(
                    id=f"[{i+1}]",
                    act_name=chunk.act_name,
                    section_number=chunk.section_number,
                    doc_type=chunk.doc_type,
                    citation=chunk.citation,
                    court=chunk.court,
                    score=chunk.score,
                    source_type=chunk.source,
                ))
            
            return SynthesizedAnswer(
                query=query,
                summary=response[:500],
                sections=[AnswerSection(
                    heading="Answer",
                    content=response,
                    citations=[c for c in citations if f"[{i+1}]" in response for i, _ in enumerate(chunks)],
                    confidence=0.8,
                )],
                citations=[c for i, c in enumerate(citations) if f"[{i+1}]" in response],
                confidence=0.8,
                retrieval_metadata={
                    "total_chunks": len(chunks),
                },
                format=format,
            )
    
    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        """Build context string from retrieved chunks with citation markers."""
        parts = []
        for i, chunk in enumerate(chunks):
            cite_id = f"[{i+1}]"
            header = f"{cite_id} "
            if chunk.act_name:
                header += f"{chunk.act_name} "
            if chunk.section_number:
                header += f"§{chunk.section_number} "
            if chunk.chapter:
                header += f"(Ch. {chunk.chapter}) "
            if chunk.citation:
                header += f"— {chunk.citation} "
            if chunk.court:
                header += f"({chunk.court}) "
            header += f"({chunk.source}, score: {chunk.score:.2f}):\n"
            
            parts.append(f"{header}{chunk.text}\n")
        
        return "\n---\n\n".join(parts)
    
    def _flatten_answer(self, answer: SynthesizedAnswer) -> str:
        """Convert structured answer to text for critic."""
        text = f"Summary: {answer.summary}\n\n"
        for sec in answer.sections:
            text += f"{sec.heading}\n{sec.content}\n\n"
        return text
    
    def _get_structured_system_prompt(self) -> str:
        return """OUTPUT FORMAT (JSON):
{
  "summary": "2-3 sentence executive summary",
  "sections": [
    {
      "heading": "Applicable Law",
      "content": "Detailed explanation with [1], [2] citations",
      "citations": ["[1]", "[2]"],
      "confidence": 0.9
    },
    {
      "heading": "Key Sections",
      "content": "Section-by-section analysis with citations",
      "citations": ["[1]", "[3]"],
      "confidence": 0.85
    },
    {
      "heading": "Case Law Interpretations",
      "content": "Relevant judgments with holdings",
      "citations": ["[4]", "[5]"],
      "confidence": 0.8
    },
    {
      "heading": "Compliance / Practical Implications",
      "content": "What this means in practice",
      "citations": ["[1]", "[2]"],
      "confidence": 0.75
    }
  ]
}

RULES:
- Every factual claim MUST end with citation like [1], [2]
- If sources contradict, present both views with citations
- Distinguish: statutory text vs case law vs notifications
- Confidence reflects source support (1.0 = directly quoted, 0.5 = inferred)
- Include "Limitations" section if law may be amended or jurisdiction-specific"""
    
    def _get_markdown_system_prompt(self) -> str:
        return """OUTPUT FORMAT (Markdown):
## Executive Summary
2-3 sentences.

## Applicable Statutory Provisions
| Act | Section | Key Point | Source |
|-----|---------|-----------|--------|
| ... | ... | ... | [1] |

## Case Law Interpretations
### *Case Name* (Citation)
**Holding:** ...
**Ratio:** ...
**Source:** [2]

## Practical Implications
- Point 1 [1]
- Point 2 [3]

## Notes
- Effective dates, amendments, etc.

RULES:
- Every claim cited with [1], [2]...
- Use tables for statutory provisions
- Bold case names
- Separate statute from case law"""
    
    def _get_brief_system_prompt(self) -> str:
        return """OUTPUT FORMAT:
**Answer:** [Direct answer with citations]

**Sources:** [1] Act §X, [2] Case citation, ...

**Confidence:** X%

RULES:
- Maximum 3 sentences in answer
- Only cite sources provided
- If uncertain, say so"""


# Global instance
synthesizer_agent = SynthesizerAgent(
    max_iterations=settings.MAX_VERIFICATION_RETRIES,
)