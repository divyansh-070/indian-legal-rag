"""
Legal Guidance Pipeline — Orchestrates the full flow:
Situation Analysis → Clarification Questions → Guidance Synthesis → Critic Verification
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from api.agents.situation_analyzer import SituationAnalyzerAgent, SituationAnalysis
from api.agents.clarification_agent import ClarificationAgent, ClarificationResponse
from api.agents.guidance_synthesizer import GuidanceSynthesizerAgent, GuidanceResponse
from api.config import settings


@dataclass
class PipelineResult:
    """Result of the full pipeline run."""
    status: str  # "needs_clarification", "complete", "error"
    situation_analysis: Optional[SituationAnalysis] = None
    clarification_response: Optional[ClarificationResponse] = None
    guidance: Optional[GuidanceResponse] = None
    error: Optional[str] = None


class LegalGuidancePipeline:
    """
    Full pipeline for converting user situation into actionable legal guidance.
    
    Flow:
    1. SituationAnalyzerAgent → extracts legal issues from plain language
    2. ClarificationAgent → generates targeted questions for critical gaps
    3. GuidanceSynthesizerAgent → produces actionable guidance with citations
    4. CriticAgent (inside synthesizer) → verifies and self-corrects
    """
    
    def __init__(self):
        self.situation_analyzer = SituationAnalyzerAgent()
        self.clarification_agent = ClarificationAgent()
        self.guidance_synthesizer = GuidanceSynthesizerAgent()
    
    async def run(
        self,
        situation: str,
        user_profile: Dict[str, Any] = None,
        clarification_answers: Dict[str, str] = None,
    ) -> PipelineResult:
        """
        Run full pipeline to completion.
        If clarification_answers provided, skips clarification step.
        """
        try:
            # Step 1: Analyze situation
            analysis = await self.situation_analyzer.analyze(situation, user_profile)
            
            # Step 2: If no clarification answers provided, generate questions
            if not clarification_answers:
                clarification = await self.clarification_agent.generate_questions(analysis)
                
                # Check if we can proceed without clarification
                if not clarification.can_proceed_without and clarification.missing_critical_info:
                    return PipelineResult(
                        status="needs_clarification",
                        situation_analysis=analysis,
                        clarification_response=clarification,
                    )
                
                # Can proceed without - use empty answers
                clarification_answers = {}
            
            # Step 3: Generate guidance with critic verification
            guidance = await self.guidance_synthesizer.synthesize(
                analysis=analysis,
                clarification_answers=clarification_answers,
            )
            
            return PipelineResult(
                status="complete",
                situation_analysis=analysis,
                guidance=guidance,
            )
            
        except Exception as e:
            return PipelineResult(
                status="error",
                error=str(e),
            )
    
    async def run_with_clarification(
        self,
        situation: str,
        user_profile: Dict[str, Any] = None,
    ) -> PipelineResult:
        """
        Run only analysis + clarification (for first API call).
        Returns analysis + questions, not full guidance.
        """
        try:
            analysis = await self.situation_analyzer.analyze(situation, user_profile)
            clarification = await self.clarification_agent.generate_questions(analysis)
            
            # Determine if we need clarification
            needs_clarification = (
                not clarification.can_proceed_without 
                or clarification.missing_critical_info
            )
            
            return PipelineResult(
                status="needs_clarification" if needs_clarification else "ready_for_guidance",
                situation_analysis=analysis,
                clarification_response=clarification if needs_clarification else None,
            )
        except Exception as e:
            return PipelineResult(
                status="error",
                error=str(e),
            )


# Global instance
legal_guidance_pipeline = LegalGuidancePipeline()