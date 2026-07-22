"""
Clarification Agent — Generates targeted follow-up questions to fill critical gaps.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from api.services.llm import llm_service
from api.agents.situation_analyzer import SituationAnalysis, LegalIssue
from api.config import settings


class ClarificationQuestion(BaseModel):
    """A targeted clarification question."""
    id: Optional[str] = None
    question: str
    reason: str  # why this matters legally
    field: str  # which field in analysis this fills
    priority: str  # high, medium, low


class ClarificationResponse(BaseModel):
    """Response with clarification questions."""
    questions: List[ClarificationQuestion]
    can_proceed_without: bool  # whether we can give preliminary guidance
    missing_critical_info: Optional[List[str]] = None


CLARIFICATION_SYSTEM = """You are a legal intake specialist. Given an initial situation analysis with gaps, generate targeted follow-up questions.

Rules:
1. Only ask what's legally necessary — don't be exhaustive
2. Explain WHY each question matters (legal relevance)
3. Prioritize: limitation periods, jurisdiction, written evidence, party capacity
4. Max 5 questions
5. If analysis has enough for preliminary guidance, set can_proceed_without=true

Output valid JSON matching the schema."""


CLARIFICATION_USER = """SITUATION ANALYSIS:
{analysis_json}

Identify critical gaps and generate clarification questions."""


class ClarificationAgent:
    """Generates targeted follow-up questions for missing critical information."""
    
    def __init__(self):
        self.model = settings.OLLAMA_MODEL
        self.fallback_model = settings.OLLAMA_FALLBACK_MODEL
    
    async def generate_questions(self, analysis: SituationAnalysis) -> ClarificationResponse:
        """Generate clarification questions for missing critical info."""
        
        prompt = CLARIFICATION_USER.format(
            analysis_json=analysis.model_dump_json(indent=2)
        )
        
        try:
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=ClarificationResponse,
                system=CLARIFICATION_SYSTEM,
                model=self.model,
                use_fallback=True,
            )
            return result
        except Exception as e:
            # Fallback: basic questions based on common gaps
            return self._fallback_questions(analysis)
    
    def _fallback_questions(self, analysis: SituationAnalysis) -> ClarificationResponse:
        """Basic fallback questions based on common missing fields."""
        questions = []
        missing = analysis.missing_info
        
        field_questions = {
            "Written contract details": ClarificationQuestion(
                question="Do you have a written contract, signed agreement, or formal offer letter? If yes, what key terms does it cover (payment, timeline, termination, dispute resolution)?",
                reason="Written contracts determine applicable sections (e.g., Specific Relief Act for specific performance, arbitration clause for jurisdiction)",
                field="has_written_contract",
                priority="high"
            ),
            "Documentation evidence": ClarificationQuestion(
                question="What evidence do you have? (emails, WhatsApp, invoices, payment records, screenshots, witnesses)",
                reason="Evidence strength determines viable legal paths — summary suit needs written proof, arbitration needs agreement",
                field="has_documentation",
                priority="high"
            ),
            "Counterparty location": ClarificationQuestion(
                question="Where is the other party located (city, state)? Are they an individual or company?",
                reason="Determines jurisdiction for filing, applicable state laws (rent control, shops act), and service of notice",
                field="counterparty_location",
                priority="high"
            ),
            "Exact amounts and dates": ClarificationQuestion(
                question="What is the exact amount involved? When was payment due / when did issue start? Any partial payments?",
                reason="Affects limitation period (3 years from acknowledgment), court fees, and forum (small claims vs regular)",
                field="amount_involved",
                priority="high"
            ),
            "Counterparty type": ClarificationQuestion(
                question="Is the other party an individual, partnership, LLP, private limited company, or government entity?",
                reason="Different entities have different liability, service of process rules, and enforcement mechanisms",
                field="counterparty_type",
                priority="medium"
            ),
        }
        
        for info in missing:
            if info in field_questions:
                q = field_questions[info]
                q.id = info.lower().replace(" ", "_")
                questions.append(q)
        
        # Add category-specific questions
        for issue in analysis.legal_issues:
            if issue.category == "employment" and "notice period" not in str(missing).lower():
                        questions.append(ClarificationQuestion(
                            id="employment_terms",
                            question="What does your appointment letter/employment contract say about notice period and termination?",
                            reason="Employment contracts govern termination; statutory minimums apply if contract silent",
                            field="employment_terms",
                            priority="high"
                        ))
            elif issue.category == "consumer" and "product details" not in str(missing).lower():
                        questions.append(ClarificationQuestion(
                            id="consumer_details",
                            question="What product/service did you purchase? Price? Platform (online/offline)? Any warranty/guarantee?",
                            reason="Consumer Protection Act remedies depend on defect type, value, and platform liability",
                            field="consumer_details",
                            priority="high"
                        ))
        
        return ClarificationResponse(
            questions=questions[:5],  # Max 5
            can_proceed_without=len(questions) < 3,
            missing_critical_info=[q.field for q in questions if q.priority == "high"]
        )
        )