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
            analysis_dict = {
                "summary": result.situation_analysis.summary,
                "user_role": result.situation_analysis.user_role,
                "counterparty_role": result.situation_analysis.counterparty_role,
                "location": result.situation_analysis.location,
                "amount_involved": result.situation_analysis.amount_involved,
                "has_written_contract": result.situation_analysis.has_written_contract,
                "timeline": result.situation_analysis.timeline,
                "legal_issues": [
                    {
                        "issue": li.issue,
                        "category": li.category,
                        "applicable_acts": li.applicable_acts,
                        "key_sections": li.key_sections,
                        "urgency": li.urgency,
                    }
                    for li in result.situation_analysis.legal_issues
                ],
                "missing_info": result.situation_analysis.missing_info,
            }
        
        if result.status == "needs_clarification" and result.clarification_response:
            clar = result.clarification_response
            return ClarificationQuestionsResponse(
                situation_analysis=analysis_dict,
                clarification_needed=True,
                questions=[
                    {
                        "id": q.id,
                        "question": q.question,
                        "why_needed": q.why_needed,
                        "critical": q.critical,
                        "example_answer": q.example_answer,
                    }
                    for q in clar.questions
                ],
                can_proceed_without=clar.can_proceed_without,
                missing_critical_info=clar.missing_critical_info,
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
            analysis_dict = {
                "summary": result.situation_analysis.summary,
                "user_role": result.situation_analysis.user_role,
                "counterparty_role": result.situation_analysis.counterparty_role,
                "location": result.situation_analysis.location,
                "amount_involved": result.situation_analysis.amount_involved,
                "has_written_contract": result.situation_analysis.has_written_contract,
                "timeline": result.situation_analysis.timeline,
                "legal_issues": [
                    {
                        "issue": li.issue,
                        "category": li.category,
                        "applicable_acts": li.applicable_acts,
                        "key_sections": li.key_sections,
                        "urgency": li.urgency,
                    }
                    for li in result.situation_analysis.legal_issues
                ],
                "missing_info": result.situation_analysis.missing_info,
            }
        
        clar_dict = None
        if result.clarification_response:
            clar = result.clarification_response
            clar_dict = {
                "questions": [
                    {
                        "id": q.id,
                        "question": q.question,
                        "why_needed": q.why_needed,
                        "critical": q.critical,
                        "example_answer": q.example_answer,
                    }
                    for q in clar.questions
                ],
                "can_proceed_without": clar.can_proceed_without,
                "missing_critical_info": clar.missing_critical_info,
            }
        
        guidance_dict = None
        if result.guidance:
            g = result.guidance
            guidance_dict = {
                "situation_summary": g.situation_summary,
                "applicable_laws": g.applicable_laws,
                "immediate_steps": [
                    {
                        "step": s.step,
                        "reason": s.reason,
                        "deadline": s.deadline,
                        "do_it_yourself": s.do_it_yourself,
                    }
                    for s in g.immediate_steps
                ],
                "legal_options": [
                    {
                        "name": o.name,
                        "description": o.description,
                        "applicable_act": o.applicable_act,
                        "key_sections": o.key_sections,
                        "estimated_cost": o.estimated_cost,
                        "estimated_time": o.estimated_time,
                        "success_likelihood": o.success_likelihood,
                        "pros": o.pros,
                        "cons": o.cons,
                        "prerequisites": o.prerequisites,
                    }
                    for o in g.legal_options
                ],
                "red_flags": [
                    {
                        "flag": r.flag,
                        "severity": r.severity,
                        "explanation": r.explanation,
                        "mitigation": r.mitigation,
                    }
                    for r in g.red_flags
                ],
                "when_lawyer_needed": [
                    {
                        "scenario": w.scenario,
                        "reason": w.reason,
                        "estimated_cost_range": w.estimated_cost_range,
                    }
                    for w in g.when_lawyer_needed
                ],
                "sources": g.sources,
                "limitation_periods": g.limitation_periods,
                "jurisdiction": g.jurisdiction,
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