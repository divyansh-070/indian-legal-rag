"""
Guidance Synthesizer Agent — Produces actionable legal guidance from analyzed situation.
Integrates with Critic for self-correction and Retriever for statutory/case law citations.
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from api.services.llm import llm_service
from api.services.retriever import hybrid_retriever, RetrievedChunk
from api.services.critic import critic_agent, CriticResult, VerificationStatus
from api.agents.situation_analyzer import SituationAnalysis, LegalIssue
from api.config import settings
from pydantic import BaseModel, Field


class LegalOption(BaseModel):
    """A legal option with practical assessment."""
    name: str
    description: str
    applicable_act: str
    key_sections: List[str] = Field(default_factory=list)
    estimated_cost: str  # free, low (<10k), medium (10k-50k), high (50k-2L), very_high (>2L)
    estimated_time: str  # e.g., "30-60 days", "6-12 months"
    success_likelihood: str  # high, medium, low
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)  # what's needed to pursue this


class RedFlag(BaseModel):
    """A warning/red flag for the user."""
    flag: str
    severity: str  # critical, high, medium
    explanation: str
    mitigation: Optional[str] = None


class ImmediateStep(BaseModel):
    """An immediate actionable step."""
    step: str
    reason: str
    deadline: Optional[str] = None  # e.g., "within 15 days", "before limitation expires"
    do_it_yourself: bool = True  # can user do this without lawyer


class WhenLawyerNeeded(BaseModel):
    """Guidance on when to hire a lawyer."""
    scenario: str
    reason: str
    estimated_cost_range: str


class GuidanceResponse(BaseModel):
    """Complete actionable guidance response."""
    situation_summary: str
    applicable_laws: List[str]  # act names
    immediate_steps: List[ImmediateStep]
    legal_options: List[LegalOption]
    red_flags: List[RedFlag]
    when_lawyer_needed: List[WhenLawyerNeeded]
    sources: List[Dict[str, Any]]  # citations with act, section, description
    limitation_periods: List[Dict[str, str]]  # act, period, from_when
    jurisdiction: str
    disclaimer: str = "This is legal information based on your description, not legal advice. Consult a qualified advocate for your specific case. Laws may have changed; verify current provisions."


class GuidanceSynthesizerAgent:
    """
    Synthesizes actionable guidance from situation analysis.
    Uses retriever for relevant statutes/case law, critic for verification.
    """
    
    def __init__(self, max_iterations: int = 2):
        self.max_iterations = max_iterations
    
    async def synthesize(
        self,
        analysis: SituationAnalysis,
        clarification_answers: Dict[str, str] = None,
    ) -> GuidanceResponse:
        """Generate actionable guidance from analyzed situation."""
        
        # Enhance analysis with clarification answers
        if clarification_answers:
            analysis = self._merge_answers(analysis, clarification_answers)
        
        # Build retrieval queries from legal issues
        chunks = await self._retrieve_relevant_sources(analysis)
        
        # Generate initial guidance
        guidance = await self._generate_guidance(analysis, chunks)
        
        # Run critic verification
        guidance_text = self._flatten_guidance(guidance)
        critic_result = await critic_agent.verify_answer(guidance_text, chunks, analysis.summary)
        
        # Refine if critic finds issues
        iteration = 0
        while (critic_result.hallucination_count > 0 or 
               critic_result.missing_citation_count > 0) and iteration < self.max_iterations:
            
            guidance = await self._refine_guidance(
                analysis, chunks, guidance, critic_result
            )
            
            guidance_text = self._flatten_guidance(guidance)
            critic_result = await critic_agent.verify_answer(guidance_text, chunks, analysis.summary)
            iteration += 1
        
        # Attach critic result for transparency
        guidance.critic_metadata = {
            "faithfulness": critic_result.overall_faithfulness,
            "hallucinations": critic_result.hallucination_count,
            "missing_citations": critic_result.missing_citation_count,
        }
        
        return guidance
    
    def _merge_answers(self, analysis: SituationAnalysis, answers: Dict[str, str]) -> SituationAnalysis:
        """Merge clarification answers into analysis (simplified - in practice, update fields)."""
        # For now, just append to missing_info resolution
        # In production, would parse and update specific fields
        return analysis
    
    async def _retrieve_relevant_sources(self, analysis: SituationAnalysis) -> List[RetrievedChunk]:
        """Retrieve relevant statutes, sections, and case law for identified issues."""
        all_chunks = []
        
        # For each legal issue, retrieve relevant sources
        for issue in analysis.legal_issues:
            # Build query from issue
            query_parts = [issue.issue]
            if issue.applicable_acts:
                query_parts.extend(issue.applicable_acts)
            if issue.key_sections:
                query_parts.extend([f"Section {s}" for s in issue.key_sections])
            
            query = " ".join(query_parts)
            
            # Retrieve with filters for acts if specified
            filters = {}
            if issue.applicable_acts:
                # Use first act as filter
                filters["act_name"] = issue.applicable_acts[0]
            
            chunks = await hybrid_retriever.retrieve(
                query=query,
                filters=filters if filters else None,
                use_graph=True,
                graph_hops=2,
            )
            all_chunks.extend(chunks)
        
        # Also retrieve for jurisdiction-specific laws
        if analysis.location:
            jurisdiction_query = f"{analysis.location} state specific laws rent control shops establishments"
            jur_chunks = await hybrid_retriever.retrieve(
                query=jurisdiction_query,
                use_graph=True,
            )
            all_chunks.extend(jur_chunks)
        
        # Deduplicate by ID
        seen = set()
        unique_chunks = []
        for c in all_chunks:
            if c.id not in seen:
                seen.add(c.id)
                unique_chunks.append(c)
        
        return unique_chunks[:20]  # Limit total chunks
    
    async def _generate_guidance(
        self,
        analysis: SituationAnalysis,
        chunks: List[RetrievedChunk],
    ) -> GuidanceResponse:
        """Generate guidance using LLM with retrieved sources."""
        
        # Build context from chunks
        context = self._build_context(chunks)
        
        # Build issue summary
        issues_text = "\n".join([
            f"- {issue.issue} (Category: {issue.category}, Acts: {', '.join(issue.applicable_acts)}, Urgency: {issue.urgency})"
            for issue in analysis.legal_issues
        ])
        
        prompt = f"""You are an expert Indian legal guide for individuals and small businesses. Generate practical, actionable guidance.

USER SITUATION:
{analysis.summary}

USER PROFILE:
- Role: {analysis.user_role}
- Location: {analysis.location}
- Counterparty: {analysis.counterparty_role} in {analysis.counterparty_location or 'unknown'}
- Amount: {analysis.amount_involved or 'Not specified'}
- Written Contract: {'Yes' if analysis.has_written_contract else 'No'}
- Documentation: {', '.join(analysis.documentation_details) if analysis.documentation_details else 'Limited/None'}
- Timeline: {analysis.timeline}

IDENTIFIED LEGAL ISSUES:
{issues_text}

RELEVANT LEGAL SOURCES (cite these using [1], [2] format):
{context}

Generate guidance in this EXACT JSON structure:
{{
  "situation_summary": "2-3 sentence plain-language summary",
  "applicable_laws": ["Act Name 1", "Act Name 2"],
  "immediate_steps": [
    {{"step": "action", "reason": "why", "deadline": "timeframe or null", "do_it_yourself": true/false}}
  ],
  "legal_options": [
    {{
      "name": "Option name",
      "description": "What this entails",
      "applicable_act": "Act name",
      "key_sections": ["Section X", "Section Y"],
      "estimated_cost": "free/low/medium/high/very_high",
      "estimated_time": "e.g., 30-60 days",
      "success_likelihood": "high/medium/low",
      "pros": ["pro1", "pro2"],
      "cons": ["con1", "con2"],
      "prerequisites": ["what's needed to pursue"]
    }}
  ],
  "red_flags": [
    {{"flag": "warning", "severity": "critical/high/medium", "explanation": "why", "mitigation": "what to do"}}
  ],
  "when_lawyer_needed": [
    {{"scenario": "when", "reason": "why", "estimated_cost_range": "range"}}
  ],
  "sources": [
    {{"act": "Act Name", "section": "Section X", "description": "what it covers", "citation_id": "[1]"}}
  ],
  "limitation_periods": [
    {{"act": "Act Name", "period": "e.g., 3 years", "from_when": "e.g., date of breach"}}
  ],
  "jurisdiction": "City, State (court forum)"
}}

RULES:
1. Every legal assertion MUST cite sources using [1], [2] matching the provided sources
2. Options must be PRACTICAL for an individual/small business (consider cost, time, complexity)
3. Include at least one "free/low cost" option if possible
4. Red flags must include limitation periods, jurisdiction issues, evidence gaps
5. Immediate steps should be DIY where possible (send notice, preserve evidence)
6. Cost categories: free, low (<10k), medium (10k-50k), high (50k-2L), very_high (>2L)
7. Be honest about success likelihood - don't overpromise
8. Jurisdiction = where user can file based on their location/counterparty location
"""
        
        try:
            # Use structured output for guidance
            from pydantic import create_model
            from typing import List
            
            class GuidanceModel(BaseModel):
                situation_summary: str
                applicable_laws: List[str]
                immediate_steps: List[Dict[str, Any]]
                legal_options: List[Dict[str, Any]]
                red_flags: List[Dict[str, Any]]
                when_lawyer_needed: List[Dict[str, Any]]
                sources: List[Dict[str, Any]]
                limitation_periods: List[Dict[str, str]]
                jurisdiction: str
            
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=GuidanceModel,
                system="You are an expert Indian legal guide. Practical, honest, citation-rich. No hallucination.",
            )
            
            return GuidanceResponse(
                situation_summary=result.situation_summary,
                applicable_laws=result.applicable_laws,
                immediate_steps=[ImmediateStep(**s) for s in result.immediate_steps],
                legal_options=[LegalOption(**o) for o in result.legal_options],
                red_flags=[RedFlag(**r) for r in result.red_flags],
                when_lawyer_needed=[WhenLawyerNeeded(**w) for w in result.when_lawyer_needed],
                sources=result.sources,
                limitation_periods=result.limitation_periods,
                jurisdiction=result.jurisdiction,
            )
            
        except Exception as e:
            # Fallback guidance
            return self._fallback_guidance(analysis, chunks)
    
    def _build_context(self, chunks: List[RetrievedChunk]) -> str:
        """Build context string from retrieved chunks."""
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
    
    def _flatten_guidance(self, guidance: GuidanceResponse) -> str:
        """Flatten guidance to text for critic."""
        text = f"Summary: {guidance.situation_summary}\n\n"
        text += f"Applicable Laws: {', '.join(guidance.applicable_laws)}\n\n"
        for step in guidance.immediate_steps:
            text += f"Step: {step.step} - {step.reason}\n"
        for opt in guidance.legal_options:
            text += f"Option: {opt.name} - {opt.description}\n"
        for flag in guidance.red_flags:
            text += f"Red Flag: {flag.flag} - {flag.explanation}\n"
        return text
    
    async def _refine_guidance(
        self,
        analysis: SituationAnalysis,
        chunks: List[RetrievedChunk],
        previous_guidance: GuidanceResponse,
        critic_result: CriticResult,
    ) -> GuidanceResponse:
        """Refine guidance based on critic feedback."""
        
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
        
        prompt = f"""Refine this legal guidance to fix the identified issues.

PREVIOUS GUIDANCE:
{self._flatten_guidance(previous_guidance)}

CRITIC ISSUES TO FIX:
{issues}

SOURCES:
{context}

Generate corrected guidance in the same JSON structure. Specifically:
- Remove or correct contradicted claims
- Add citations for missing-citation claims
- Mark stale law references with "⚠ Check current amendment status"
- Only include claims supported by sources
"""
        
        from pydantic import create_model
        from typing import List
        
        class GuidanceModel(BaseModel):
            situation_summary: str
            applicable_laws: List[str]
            immediate_steps: List[Dict[str, Any]]
            legal_options: List[Dict[str, Any]]
            red_flags: List[Dict[str, Any]]
            when_lawyer_needed: List[Dict[str, Any]]
            sources: List[Dict[str, Any]]
            limitation_periods: List[Dict[str, str]]
            jurisdiction: str
        
        result = await llm_service.generate_structured(
            prompt=prompt,
            response_model=GuidanceModel,
            system="You are correcting legal guidance based on fact-checking feedback. Be precise.",
        )
        
        return GuidanceResponse(
            situation_summary=result.situation_summary,
            applicable_laws=result.applicable_laws,
            immediate_steps=[ImmediateStep(**s) for s in result.immediate_steps],
            legal_options=[LegalOption(**o) for o in result.legal_options],
            red_flags=[RedFlag(**r) for r in result.red_flags],
            when_lawyer_needed=[WhenLawyerNeeded(**w) for w in result.when_lawyer_needed],
            sources=result.sources,
            limitation_periods=result.limitation_periods,
            jurisdiction=result.jurisdiction,
        )
    
    def _fallback_guidance(self, analysis: SituationAnalysis, chunks: List[RetrievedChunk]) -> GuidanceResponse:
        """Basic fallback guidance when LLM fails."""
        
        immediate_steps = [
            ImmediateStep(
                step="Send a formal written demand (legal notice) via registered post and email",
                reason="Creates evidence of demand, may trigger acknowledgment extending limitation period",
                deadline="Within 30 days",
                do_it_yourself=True,
            ),
            ImmediateStep(
                step="Preserve all evidence (contracts, emails, WhatsApp, invoices, payment records)",
                reason="Evidence is critical for any legal proceeding; screenshots and backups essential",
                deadline="Immediately",
                do_it_yourself=True,
            ),
        ]
        
        legal_options = [
            LegalOption(
                name="Legal Notice + Negotiation",
                description="Send formal notice demanding resolution; often leads to settlement without court",
                applicable_act="Indian Contract Act 1872 / Specific Relief Act 1963",
                key_sections=["Section 73", "Section 74"],
                estimated_cost="low",
                estimated_time="15-30 days",
                success_likelihood="medium",
                pros=["Low cost", "Preserves relationship", "May resolve quickly"],
                cons=["No guarantee of response", "Not legally binding"],
                prerequisites=["Counterparty address", "Clear demand amount"],
            ),
            LegalOption(
                name="MSME Samadhaan (if applicable)",
                description="File online complaint for delayed payments from MSME-registered buyers",
                applicable_act="MSME Development Act 2006",
                key_sections=["Section 15-18"],
                estimated_cost="free",
                estimated_time="60-90 days",
                success_likelihood="high" if "MSME" in str([c.act_name for c in chunks]) else "medium",
                pros=["Free", "Statutory timeline", "Interest on delayed payment"],
                cons=["Only if buyer is MSME registered", "Limited to goods/services"],
                prerequisites=["Buyer MSME registration", "Invoice >45 days old"],
            ),
        ]
        
        red_flags = [
            RedFlag(
                flag="Limitation Period",
                severity="critical",
                explanation=f"Most civil claims have 3-year limitation from breach/acknowledgment. Check when cause of action arose.",
                mitigation="Send legal notice immediately to create fresh acknowledgment",
            ),
        ]
        
        sources = []
        for i, chunk in enumerate(chunks[:5]):
            if chunk.act_name:
                sources.append({
                    "act": chunk.act_name,
                    "section": chunk.section_number or "N/A",
                    "description": chunk.text[:150],
                    "citation_id": f"[{i+1}]",
                })
        
        return GuidanceResponse(
            situation_summary=analysis.summary[:200],
            applicable_laws=list(set().union(*[issue.applicable_acts for issue in analysis.legal_issues])),
            immediate_steps=immediate_steps,
            legal_options=legal_options,
            red_flags=red_flags,
            when_lawyer_needed=[
                WhenLawyerNeeded(
                    scenario="Counterparty disputes existence of contract/debt",
                    reason="Requires evidence evaluation and potentially summary suit",
                    estimated_cost_range="₹20,000 - ₹1,00,000+",
                ),
                WhenLawyerNeeded(
                    scenario="Amount exceeds ₹10 lakh or complex corporate/commercial dispute",
                    reason="High stakes justify professional representation",
                    estimated_cost_range="₹50,000 - ₹5,00,000+",
                ),
            ],
            sources=sources,
            limitation_periods=[
                {"act": "Indian Contract Act / Civil Procedure Code", "period": "3 years", "from_when": "Date of breach or last acknowledgment"},
                {"act": "MSME Development Act", "period": "Application within 90 days of due date", "from_when": "Due date of payment"},
            ],
            jurisdiction=f"{analysis.location} (user's location typically determines forum for individuals)",
        )


# Global instance
guidance_synthesizer_agent = GuidanceSynthesizerAgent(max_iterations=2)