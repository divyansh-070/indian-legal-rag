"""
Guide API Routes — Legal Guidance endpoint for plain-language interface.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from api.agents.pipeline import legal_guidance_pipeline, PipelineResult
from api.agents.situation_analyzer import SituationAnalysis
from api.agents.guidance_synthesizer import GuidanceResponse, ImmediateStep, LegalOption, RedFlag, WhenLawyerNeeded
from api.agents.clarification_agent import ClarificationResponse


router = APIRouter(tags=["guide"])


# ─── Request/Response Models ──────────────────────────────────────────────────

class GuideRequest(BaseModel):
    situation: str = Field(..., min_length=10, max_length=5000, description="Plain-language description of your legal situation")
    user_profile: Optional[Dict[str, Any]] = Field(default=None, description="Optional: role, location, budget, etc.")
    clarification_answers: Optional[Dict[str, str]] = Field(default=None, description="Answers to previous clarification questions")


class ClarificationQuestionsResponse(BaseModel):
    situation_analysis: Dict[str, Any]
    clarification_needed: bool
    questions: Optional[List[Dict[str, Any]]] = None
    can_proceed_without: bool = False
    missing_critical_info: Optional[List[str]] = None


class GuideResponse(BaseModel):
    situation_summary: str
    applicable_laws: List[str]
    immediate_steps: List[Dict[str, Any]]
    legal_options: List[Dict[str, Any]]
    red_flags: List[Dict[str, Any]]
    when_lawyer_needed: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    limitation_periods: List[Dict[str, str]]
    jurisdiction: str
    disclaimer: str


class FullGuideResponse(BaseModel):
    situation_analysis: Dict[str, Any]
    clarification_response: Optional[Dict[str, Any]] = None
    guidance: Optional[Dict[str, Any]] = None
    status: str  # "needs_clarification", "complete", "error"
    error: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=ClarificationQuestionsResponse)
async def analyze_situation(request: GuideRequest):
    """
    Analyze user's situation and return clarification questions if needed.
    First step in the guidance flow.
    """
    try:
        result = await legal_guidance_pipeline.run_with_clarification(
            situation=request.situation,
            user_profile=request.user_profile,
        )
        
        analysis_dict = {}
        if result.situation_analysis:
            s = result.situation_analysis
            analysis_dict = {
                "summary": s.summary or "",
                "user_role": s.user_role or "",
                "counterparty_role": s.counterparty_role or "",
                "location": s.location or "",
                "amount_involved": s.amount_involved or "",
                "has_written_contract": bool(s.has_written_contract) if s.has_written_contract is not None else False,
                "timeline": s.timeline or "",
                "legal_issues": [
                    {
                        "issue": li.issue or "",
                        "category": li.category or "",
                        "applicable_acts": li.applicable_acts or [],
                        "key_sections": li.key_sections or [],
                        "urgency": li.urgency or "Medium",
                    }
                    for li in (s.legal_issues or [])
                ],
                "missing_info": s.missing_info or [],
            }
        
        if result.status == "needs_clarification" and result.clarification_response:
            clar = result.clarification_response
            return ClarificationQuestionsResponse(
                situation_analysis=analysis_dict,
                clarification_needed=True,
                questions=[
                    {
                        "id": f"q_{i+1}",
                        "question": q.question or "",
                        "why_needed": getattr(q, 'reason', '') or getattr(q, 'why_needed', '') or "",
                        "critical": getattr(q, 'priority', '') == "high" or bool(getattr(q, 'critical', False)),
                    }
                    for i, q in enumerate(clar.questions or [])
                ],
                can_proceed_without=bool(clar.can_proceed_without),
                missing_critical_info=clar.missing_critical_info or [],
            )
        
        return ClarificationQuestionsResponse(
            situation_analysis=analysis_dict,
            clarification_needed=False,
            can_proceed_without=True,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("", response_model=FullGuideResponse)
async def get_guide(request: GuideRequest):
    """
    Main guidance endpoint.
    If clarification_answers provided, generates full guidance.
    If not, returns analysis + clarification questions.
    """
    try:
        result = await legal_guidance_pipeline.run(
            situation=request.situation,
            user_profile=request.user_profile,
            clarification_answers=request.clarification_answers,
        )
        
        analysis_dict = {}
        if result.situation_analysis:
            s = result.situation_analysis
            analysis_dict = {
                "summary": s.summary or "",
                "user_role": s.user_role or "",
                "counterparty_role": s.counterparty_role or "",
                "location": s.location or "",
                "amount_involved": s.amount_involved or "",
                "has_written_contract": bool(s.has_written_contract) if s.has_written_contract is not None else False,
                "timeline": s.timeline or "",
                "legal_issues": [
                    {
                        "issue": li.issue or "",
                        "category": li.category or "",
                        "applicable_acts": li.applicable_acts or [],
                        "key_sections": li.key_sections or [],
                        "urgency": li.urgency or "Medium",
                    }
                    for li in (s.legal_issues or [])
                ],
                "missing_info": s.missing_info or [],
            }
        
        clar_dict = None
        if result.clarification_response:
            clar = result.clarification_response
            clar_dict = {
                "questions": [
                    {
                        "id": f"q_{i+1}",
                        "question": q.question or "",
                        "why_needed": getattr(q, 'reason', '') or getattr(q, 'why_needed', '') or "",
                        "critical": getattr(q, 'priority', '') == "high" or bool(getattr(q, 'critical', False)),
                    }
                    for i, q in enumerate(clar.questions or [])
                ],
                "can_proceed_without": bool(clar.can_proceed_without),
                "missing_critical_info": clar.missing_critical_info or [],
            }
        
        guidance_dict = None
        if result.guidance:
            g = result.guidance
            guidance_dict = {
                "situation_summary": g.situation_summary or "",
                "applicable_laws": g.applicable_laws or [],
                "immediate_steps": [
                    {
                        "step": s.step or "",
                        "reason": s.reason or "",
                        "deadline": s.deadline,
                        "do_it_yourself": bool(s.do_it_yourself) if s.do_it_yourself is not None else True,
                    }
                    for s in (g.immediate_steps or [])
                ],
                "legal_options": [
                    {
                        "name": o.name or "",
                        "description": o.description or "",
                        "applicable_act": o.applicable_act or "",
                        "key_sections": o.key_sections or [],
                        "estimated_cost": o.estimated_cost or "low",
                        "estimated_time": o.estimated_time or "",
                        "success_likelihood": o.success_likelihood or "medium",
                        "pros": o.pros or [],
                        "cons": o.cons or [],
                        "prerequisites": o.prerequisites or [],
                    }
                    for o in (g.legal_options or [])
                ],
                "red_flags": [
                    {
                        "flag": r.flag or "",
                        "severity": r.severity or "medium",
                        "explanation": r.explanation or "",
                        "mitigation": r.mitigation or "",
                    }
                    for r in (g.red_flags or [])
                ],
                "when_lawyer_needed": [
                    {
                        "scenario": w.scenario or "",
                        "reason": w.reason or "",
                        "estimated_cost_range": w.estimated_cost_range or "",
                    }
                    for w in (g.when_lawyer_needed or [])
                ],
                "sources": g.sources or [],
                "limitation_periods": g.limitation_periods or [],
                "jurisdiction": g.jurisdiction or "",
            }
        
        return FullGuideResponse(
            situation_analysis=analysis_dict,
            clarification_response=clar_dict,
            guidance=guidance_dict,
            status=result.status,
            error=result.error,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Guidance generation failed: {str(e)}")


# ─── Convenience endpoint ────────────────────────────────────────────────────

@router.post("/quick")
async def quick_guide(request: GuideRequest):
    """
    Quick guidance without full structured response.
    Returns raw markdown for simple display.
    """
    result = await legal_guidance_pipeline.run(
        situation=request.situation,
        user_profile=request.user_profile,
        clarification_answers=request.clarification_answers,
    )
    
    if result.status == "needs_clarification":
        return {"status": "needs_clarification", "questions": result.clarification_response.questions}
    
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error)
    
    if not result.guidance:
        raise HTTPException(status_code=500, detail="No guidance generated")
    
    g = result.guidance
    
    # Build markdown
    md = f"""# Legal Guidance

## Summary
{g.situation_summary}

## Applicable Laws
{', '.join(g.applicable_laws)}

## Immediate Steps (Do These First)
"""
    for i, step in enumerate(g.immediate_steps, 1):
        md += f"{i}. **{step.step}** — {step.reason}"
        if step.deadline:
            md += f" (Deadline: {step.deadline})"
        md += f" {'✅ DIY' if step.do_it_yourself else '👨‍💼 May need help'}\n"
    
    md += "\n## Your Legal Options\n"
    for opt in g.legal_options:
        md += f"""
### {opt.name}
{opt.description}

**Law:** {opt.applicable_act} ({', '.join(opt.key_sections)})
**Cost:** {opt.estimated_cost} | **Time:** {opt.estimated_time} | **Success:** {opt.success_likelihood}

**Pros:** {', '.join(opt.pros)}
**Cons:** {', '.join(opt.cons)}
**Prerequisites:** {', '.join(opt.prerequisites)}
"""
    
    md += "\n## ⚠️ Red Flags\n"
    for flag in g.red_flags:
        md += f"- **{flag.flag}** ({flag.severity.upper()}): {flag.explanation} — *Mitigation: {flag.mitigation}*\n"
    
    md += "\n## When to Hire a Lawyer\n"
    for w in g.when_lawyer_needed:
        md += f"- **{w.scenario}** — {w.reason} (Est. cost: {w.estimated_cost_range})\n"
    
    md += "\n## Sources\n"
    for src in g.sources:
        md += f"- [{src['citation_id']}] {src['act']} §{src['section']}: {src['description']}\n"
    
    md += f"""
## Limitation Periods
{chr(10).join([f"- {lp['act']}: {lp['period']} (from {lp['from_when']})" for lp in g.limitation_periods])}

## Jurisdiction
{g.jurisdiction}

---
⚠️ **Disclaimer:** This is legal information, not legal advice. Always verify current law and consult a qualified advocate for your specific case.
"""
    
    return {"markdown": md, "structured": result.guidance}