"""
Situation Analyzer Agent — Extracts legal issues from user's plain-language situation.
"""

import json
from typing import List, Optional
from pydantic import BaseModel, Field

from api.services.llm import llm_service
from api.config import settings


class LegalIssue(BaseModel):
    """A legal issue identified from the situation."""
    issue: str
    category: str  # contract, employment, consumer, property, tax, corporate, family, criminal, ip, other
    applicable_acts: List[str] = Field(default_factory=list)
    key_sections: List[str] = Field(default_factory=list)
    urgency: str  # high, medium, low
    confidence: float = Field(ge=0.0, le=1.0)


class SituationAnalysis(BaseModel):
    """Complete analysis of user's situation."""
    summary: str
    user_role: str  # freelancer, employee, employer, consumer, business_owner, tenant, landlord, etc.
    counterparty_role: str
    location: str  # user's city/state
    counterparty_location: Optional[str] = None
    amount_involved: Optional[str] = None
    has_written_contract: bool = False
    has_documentation: bool = False
    documentation_details: List[str] = Field(default_factory=list)
    timeline: str  # when did issue start
    legal_issues: List[LegalIssue]
    missing_info: List[str] = Field(default_factory=list)  # what we need to clarify


SITUATION_ANALYSIS_SYSTEM = """You are an expert Indian legal intake analyst. A user describes their situation in plain language. Your job:

1. Extract structured facts (roles, locations, amounts, contracts, documentation, timeline)
2. Identify ALL potential legal issues with applicable Indian acts and sections
3. Flag what critical information is missing

Be thorough but practical. Think like a lawyer doing initial client intake.

Output valid JSON matching the schema exactly."""


SITUATION_ANALYSIS_USER = """USER SITUATION:
{situation}

USER PROFILE:
{user_profile}

Analyze and extract legal issues."""


class SituationAnalyzerAgent:
    """Analyzes plain-language situation to extract legal issues."""
    
    def __init__(self):
        self.model = settings.OLLAMA_MODEL
        self.fallback_model = settings.OLLAMA_FALLBACK_MODEL
    
    async def analyze(self, situation: str, user_profile: dict = None) -> SituationAnalysis:
        """Analyze user's situation and return structured legal issues."""
        
        profile_text = json.dumps(user_profile or {}, indent=2)
        
        prompt = SITUATION_ANALYSIS_USER.format(
            situation=situation,
            user_profile=profile_text
        )
        
        try:
            result = await llm_service.generate_structured(
                prompt=prompt,
                response_model=SituationAnalysis,
                system=SITUATION_ANALYSIS_SYSTEM,
                model=self.model,
                use_fallback=True,
            )
            return result
        except Exception as e:
            # Fallback: basic keyword-based analysis
            return self._fallback_analysis(situation, user_profile)
    
    def _fallback_analysis(self, situation: str, user_profile: dict = None) -> SituationAnalysis:
        """Keyword-based fallback when LLM fails."""
        situation_lower = situation.lower()
        
        # Detect category from keywords
        category_keywords = {
            "contract": ["contract", "agreement", "deal", "promise", "breach", "not paid", "payment", "invoice", "client", "freelance"],
            "employment": ["employer", "employee", "salary", "termination", "fired", "resign", "notice period", "appointment letter"],
            "consumer": ["product", "service", "defective", "refund", "warranty", "complaint", "e-commerce", "flipkart", "amazon"],
            "property": ["rent", "lease", "tenant", "landlord", "eviction", "security deposit", "property", "flat", "apartment"],
            "tax": ["gst", "income tax", "tds", "tax", "return", "notice", "assessment"],
            "corporate": ["company", "director", "shareholder", "board", "roc", "compliance", "annual filing"],
            "family": ["divorce", "maintenance", "custody", "marriage", "dowry", "domestic violence"],
            "criminal": ["police", "fir", "arrest", "bail", "cheating", "420", "406", "harassment"],
            "ip": ["trademark", "copyright", "patent", "brand", "logo", "infringement"],
        }
        
        detected_categories = []
        for cat, keywords in category_keywords.items():
            if any(kw in situation_lower for kw in keywords):
                detected_categories.append(cat)
        
        if not detected_categories:
            detected_categories = ["contract"]
        
        # Map to acts
        act_mapping = {
            "contract": ["Indian Contract Act 1872", "Specific Relief Act 1963"],
            "employment": ["Industrial Disputes Act 1947", "Shops and Establishments Act", "Payment of Wages Act 1936"],
            "consumer": ["Consumer Protection Act 2019"],
            "property": ["Transfer of Property Act 1882", "Rent Control Act (state-specific)"],
            "tax": ["CGST Act 2017", "Income Tax Act 1961"],
            "corporate": ["Companies Act 2013", "SEBI LODR Regulations"],
            "family": ["Hindu Marriage Act 1955", "Protection of Women from Domestic Violence Act 2005"],
            "criminal": ["Indian Penal Code 1860", "Criminal Procedure Code 1973"],
            "ip": ["Trade Marks Act 1999", "Copyright Act 1957", "Patents Act 1970"],
        }
        
        acts = []
        for cat in detected_categories:
            acts.extend(act_mapping.get(cat, []))
        
        legal_issues = []
        for cat in detected_categories:
            legal_issues.append(LegalIssue(
                issue=f"Potential {cat} law issue identified from situation",
                category=cat,
                applicable_acts=act_mapping.get(cat, []),
                key_sections=[],
                urgency="medium",
                confidence=0.6
            ))
        
        return SituationAnalysis(
            summary=situation[:200],
            user_role=user_profile.get("role", "individual") if user_profile else "individual",
            counterparty_role="unknown",
            location=user_profile.get("location", "India") if user_profile else "India",
            amount_involved=None,
            has_written_contract=False,
            has_documentation=False,
            documentation_details=[],
            timeline="recent",
            legal_issues=legal_issues,
            missing_info=["Written contract details", "Documentation evidence", "Counterparty location", "Exact amounts and dates"]
        )