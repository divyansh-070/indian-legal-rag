"""
Critic Agent — Verifies claims against retrieved sources.
Flags hallucinations, missing citations, and stale law references.
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from api.services.llm import llm_service
from api.services.retriever import RetrievedChunk
from api.config import settings
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"
    STALE_LAW = "stale_law"
    MISSING_CITATION = "missing_citation"


class ClaimVerification(BaseModel):
    """Verification result for a single claim."""
    claim_text: str
    status: VerificationStatus
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_sources: List[str] = Field(default_factory=list)
    contradicting_sources: List[str] = Field(default_factory=list)
    reasoning: str
    suggested_correction: Optional[str] = None


class CriticResult(BaseModel):
    """Overall critic result for an answer."""
    verifications: List[ClaimVerification]
    overall_faithfulness: float = Field(ge=0.0, le=1.0)
    hallucination_count: int
    missing_citation_count: int
    stale_law_warnings: List[str]
    summary: str


class CriticAgent:
    """
    Verifies each claim in a generated answer against retrieved sources.
    Implements self-correction by flagging unsupported claims.
    """
    
    def __init__(
        self,
        verification_threshold: float = 0.7,
        max_retries: int = 2,
    ):
        self.verification_threshold = verification_threshold
        self.max_retries = max_retries
    
    async def verify_answer(
        self,
        answer: str,
        sources: List[RetrievedChunk],
        query: str = None,
    ) -> CriticResult:
        """
        Verify all claims in an answer against sources.
        Returns detailed verification results.
        """
        # Extract claims from answer
        claims = await self._extract_claims(answer, query)
        
        # Verify each claim
        verifications = []
        for claim in claims:
            verification = await self._verify_claim(claim, sources)
            verifications.append(verification)
        
        # Aggregate metrics
        hallucination_count = sum(
            1 for v in verifications
            if v.status in (VerificationStatus.CONTRADICTED, VerificationStatus.UNVERIFIABLE)
        )
        missing_citation_count = sum(
            1 for v in verifications
            if v.status == VerificationStatus.MISSING_CITATION
        )
        stale_law_warnings = [
            v.reasoning for v in verifications
            if v.status == VerificationStatus.STALE_LAW
        ]
        
        # Overall faithfulness: proportion of supported claims
        supported_count = sum(1 for v in verifications if v.status == VerificationStatus.SUPPORTED)
        overall_faithfulness = supported_count / len(verifications) if verifications else 1.0
        
        return CriticResult(
            verifications=verifications,
            overall_faithfulness=overall_faithfulness,
            hallucination_count=hallucination_count,
            missing_citation_count=missing_citation_count,
            stale_law_warnings=stale_law_warnings,
            summary=self._generate_summary(verifications),
        )
    
    async def _extract_claims(self, answer: str, query: str = None) -> List[str]:
        """Extract verifiable claims from answer using LLM."""
        from pydantic import BaseModel
        from typing import List
        
        class Claims(BaseModel):
            claims: List[str]
        
        prompt = f"""Extract all verifiable factual claims from this legal answer.

Query: {query or "N/A"}
Answer: {answer}

A verifiable claim is a specific statement about law that can be checked against sources:
- Section numbers and their content
- Legal principles/holdings
- Case law citations and ratios
- Definitions of legal terms
- Procedural requirements
- Dates, thresholds, penalties

Do NOT extract:
- General advice/disclaimers
- "Consult a lawyer" statements
- Structural phrases ("First, ..." "In conclusion, ...")

Return as JSON with claims array."""
        
        try:
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=Claims,
                system="You are a legal claim extractor. Be precise and conservative.",
            )
            return result.claims
        except Exception:
            # Fallback: split by sentences
            import re
            sentences = re.split(r'(?<=[.!?])\s+', answer)
            return [s.strip() for s in sentences if len(s.strip()) > 20]
    
    async def _verify_claim(
        self,
        claim: str,
        sources: List[RetrievedChunk],
    ) -> ClaimVerification:
        """Verify a single claim against sources."""
        from pydantic import BaseModel
        
        class Verification(BaseModel):
            status: VerificationStatus
            confidence: float
            supporting_sources: List[str]
            contradicting_sources: List[str]
            reasoning: str
            suggested_correction: Optional[str] = None
        
        # Prepare source text for verification
        source_texts = []
        for i, src in enumerate(sources):
            cite = f"[{i+1}] "
            if src.act_name:
                cite += f"{src.act_name} "
            if src.section_number:
                cite += f"§{src.section_number} "
            if src.citation:
                cite += f"{src.citation} "
            if src.court:
                cite += f"({src.court}) "
            cite += f": {src.text[:500]}"
            source_texts.append(cite)
        
        sources_block = "\n\n".join(source_texts)
        
        prompt = f"""Verify this legal claim against the provided sources.

CLAIM: {claim}

SOURCES:
{sources_block}

Determine if the claim is:
1. SUPPORTED - Sources directly confirm the claim
2. CONTRADICTED - Sources explicitly contradict the claim
3. UNVERIFIABLE - Sources don't contain enough information
4. STALE_LAW - Claim references law that may be amended/repealed (check dates)
5. MISSING_CITATION - Claim makes specific legal assertion but no source cited

For each source, note if it SUPPORTS or CONTRADICTS.
Provide confidence (0-1) and brief reasoning.
If CONTRADICTED or UNVERIFIABLE, suggest correction if possible.

Return as JSON."""
        
        try:
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=Verification,
                system="You are a legal fact-checker. Be rigorous. Err on the side of UNVERIFIABLE rather than SUPPORTED.",
            )
            
            return ClaimVerification(
                claim_text=claim,
                status=result.status,
                confidence=result.confidence,
                supporting_sources=result.supporting_sources,
                contradicting_sources=result.contradicting_sources,
                reasoning=result.reasoning,
                suggested_correction=result.suggested_correction,
            )
        except Exception as e:
            return ClaimVerification(
                claim_text=claim,
                status=VerificationStatus.UNVERIFIABLE,
                confidence=0.0,
                supporting_sources=[],
                contradicting_sources=[],
                reasoning=f"Verification failed: {e}",
                suggested_correction=None,
            )
    
    def _generate_summary(self, verifications: List[ClaimVerification]) -> str:
        """Generate human-readable summary of verification results."""
        total = len(verifications)
        if total == 0:
            return "No claims to verify."
        
        supported = sum(1 for v in verifications if v.status == VerificationStatus.SUPPORTED)
        contradicted = sum(1 for v in verifications if v.status == VerificationStatus.CONTRADICTED)
        unverifiable = sum(1 for v in verifications if v.status == VerificationStatus.UNVERIFIABLE)
        stale = sum(1 for v in verifications if v.status == VerificationStatus.STALE_LAW)
        missing = sum(1 for v in verifications if v.status == VerificationStatus.MISSING_CITATION)
        
        parts = []
        parts.append(f"Verified {total} claims: {supported} supported, {contradicted} contradicted, {unverifiable} unverifiable.")
        
        if stale:
            parts.append(f"⚠ {stale} potential stale law reference(s) — verify amendment status.")
        if missing:
            parts.append(f"⚠ {missing} claim(s) missing source citations.")
        
        return " ".join(parts)


# Global instance
critic_agent = CriticAgent(
    verification_threshold=settings.VERIFICATION_THRESHOLD,
)