'use client';

import { useState } from 'react';
import { Search, Scale, Lightbulb, Loader2, AlertCircle, CheckCircle, Clock, BookOpen, ChevronRight, HelpCircle, ArrowRight, Shield, DollarSign, AlertTriangle } from 'lucide-react';

/* ── Types matching actual API responses ──────────────────────────── */

interface LegalIssue {
  issue: string;
  category: string;
  applicable_acts: string[];
  key_sections: string[];
  urgency: string;
}

interface SituationAnalysis {
  summary: string;
  user_role: string;
  counterparty_role: string;
  location: string;
  amount_involved: string;
  has_written_contract: boolean;
  timeline: string;
  legal_issues: LegalIssue[];
  missing_info: string[];
}

interface ClarificationQuestion {
  id: string | null;
  question: string;
  why_needed: string;
  critical: boolean;
}

interface ClarificationResponse {
  questions: ClarificationQuestion[];
  can_proceed_without: boolean;
  missing_critical_info: string[];
}

interface ImmediateStep {
  step: string;
  reason: string;
  deadline: string | null;
  do_it_yourself: boolean;
}

interface LegalOption {
  name: string;
  description: string;
  applicable_act: string;
  key_sections: string[];
  estimated_cost: string;
  estimated_time: string;
  success_likelihood: string;
  pros: string[];
  cons: string[];
  prerequisites: string[];
}

interface RedFlag {
  flag: string;
  severity: string;
  explanation: string;
  mitigation: string | null;
}

interface WhenLawyerNeeded {
  scenario: string;
  reason: string;
  estimated_cost_range: string;
}

interface GuidanceData {
  situation_summary: string;
  applicable_laws: string[];
  immediate_steps: ImmediateStep[];
  legal_options: LegalOption[];
  red_flags: RedFlag[];
  when_lawyer_needed: WhenLawyerNeeded[];
  sources: Record<string, string>[];
  limitation_periods: Record<string, string>[];
  jurisdiction: string;
}

interface GuideApiResponse {
  situation_analysis: SituationAnalysis;
  clarification_response: ClarificationResponse | null;
  guidance: GuidanceData | null;
  status: 'needs_clarification' | 'complete' | 'error';
  error: string | null;
}

interface QuerySection {
  heading: string;
  content: string;
  citations: Record<string, string>[];
  confidence: number;
}

interface QueryApiResponse {
  answer: {
    query: string;
    summary: string;
    sections: QuerySection[];
    citations: Record<string, string>[];
    confidence: number;
    format: string;
  };
  retrieval_metadata: Record<string, unknown>;
  critic_metadata: {
    overall_faithfulness: number;
    hallucination_count: number;
    summary: string;
  } | null;
}

/* ── Constants ────────────────────────────────────────────────────── */

const MODES = [
  {
    id: 'guide' as const,
    label: 'Legal Guidance',
    icon: Lightbulb,
    desc: 'Plain-language steps tailored to your situation',
  },
  {
    id: 'query' as const,
    label: 'Legal Research',
    icon: Scale,
    desc: 'Cited sections, statutes, and case law analysis',
  },
];

const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

/* ── Component ────────────────────────────────────────────────────── */

export default function HomePage() {
  const [mode, setMode] = useState<'guide' | 'query'>('guide');
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [guideResult, setGuideResult] = useState<GuideApiResponse | null>(null);
  const [queryResult, setQueryResult] = useState<QueryApiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    setGuideResult(null);
    setQueryResult(null);

    try {
      if (mode === 'guide') {
        const body: Record<string, unknown> = { situation: question };
        if (Object.keys(clarificationAnswers).length > 0) {
          body.clarification_answers = clarificationAnswers;
        }
        const res = await fetch(`${API_URL}/guide`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Request failed' }));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data: GuideApiResponse = await res.json();
        setGuideResult(data);
      } else {
        const res = await fetch(`${API_URL}/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: question }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Request failed' }));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data: QueryApiResponse = await res.json();
        setQueryResult(data);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Something went wrong';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleClarificationSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/guide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          situation: question,
          clarification_answers: clarificationAnswers,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data: GuideApiResponse = await res.json();
      setGuideResult(data);
      setClarificationAnswers({});
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Something went wrong';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const hasResult = guideResult || queryResult;

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-primary)', fontFamily: "'Inter', sans-serif" }}>

      {/* ── Header ──────────────────────────────────────────────── */}
      <header style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: 'var(--navy)', color: 'white' }}
            >
              <Scale className="w-4 h-4" />
            </div>
            <span className="text-base font-semibold" style={{ color: 'var(--text-heading)' }}>
              Indian Legal Guide
            </span>
          </div>
          <span className="tag tag-indigo">v1.0</span>
        </div>
      </header>

      {/* ── Main ─────────────────────────────────────────────────── */}
      <main className="max-w-3xl mx-auto px-6 pt-12 pb-16">

        {/* Hero */}
        <div className="text-center mb-12 animate-enter">
          <h1
            className="text-3xl md:text-4xl font-bold mb-3"
            style={{ color: 'var(--text-heading)', fontFamily: "'Lora', serif" }}
          >
            How can we help you today?
          </h1>
          <p className="text-base max-w-xl mx-auto" style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            Describe your legal situation or ask a specific question.
            We&apos;ll provide actionable guidance backed by Indian statutes and case law.
          </p>
        </div>

        {/* Mode Selector */}
        <div className="grid grid-cols-2 gap-3 mb-6 animate-enter delay-1">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => { setMode(m.id); setGuideResult(null); setQueryResult(null); setError(null); }}
              className={`mode-card ${mode === m.id ? 'active' : ''}`}
            >
              <div className="flex items-start gap-3">
                <m.icon
                  className="w-5 h-5 mt-0.5 flex-shrink-0"
                  style={{ color: mode === m.id ? 'var(--navy)' : 'var(--text-muted)' }}
                />
                <div>
                  <p className="font-semibold text-sm" style={{ color: 'var(--text-heading)' }}>
                    {m.label}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                    {m.desc}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Input Form */}
        <div className="card p-6 mb-8 animate-enter delay-2">
          <form onSubmit={handleSubmit}>
            <label
              htmlFor="legal-query-input"
              className="block text-sm font-semibold mb-2"
              style={{ color: 'var(--text-heading)' }}
            >
              {mode === 'guide' ? 'Describe your situation' : 'Enter your legal question'}
            </label>
            <textarea
              id="legal-query-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={4}
              placeholder={
                mode === 'guide'
                  ? 'e.g., "My landlord is refusing to return my ₹50,000 security deposit after I vacated the flat in Mumbai. I have the rental agreement and payment receipts."'
                  : 'e.g., "What are the eligibility criteria for composition scheme under Section 10 of the CGST Act?"'
              }
              className="input-field mb-4"
              disabled={loading}
            />
            <button
              id="submit-query-btn"
              type="submit"
              disabled={loading || !question.trim()}
              className="btn-primary w-full"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  {mode === 'guide' ? 'Get guidance' : 'Search'}
                </>
              )}
            </button>
          </form>
        </div>

        {/* ── Loading ─────────────────────────────────────────────── */}
        {loading && (
          <div className="text-center py-8 animate-enter">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-3" style={{ color: 'var(--indigo)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Searching statutes and case law...
            </p>
          </div>
        )}

        {/* ── Error ───────────────────────────────────────────────── */}
        {error && (
          <div className="callout callout-rose flex items-center gap-3 mb-8 animate-enter">
            <AlertCircle className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--rose)' }} />
            <p className="text-sm" style={{ color: 'var(--rose)' }}>{error}</p>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════ */}
        {/* ── GUIDE MODE RESULTS ─────────────────────────────────── */}
        {/* ══════════════════════════════════════════════════════════ */}
        {guideResult && (
          <div className="animate-enter space-y-6">

            {/* Situation Analysis */}
            {guideResult.situation_analysis && (
              <div className="card overflow-hidden">
                <div className="px-6 py-4" style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--text-heading)', fontFamily: "'Lora', serif" }}>
                    Situation Analysis
                  </h2>
                </div>
                <div className="p-6 space-y-4">
                  <p className="text-sm" style={{ color: 'var(--text-body)', lineHeight: 1.7 }}>
                    {guideResult.situation_analysis.summary}
                  </p>

                  <div className="grid sm:grid-cols-2 gap-3">
                    <div className="result-block">
                      <p className="text-xs font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>Your Role</p>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{guideResult.situation_analysis.user_role}</p>
                    </div>
                    <div className="result-block">
                      <p className="text-xs font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>Other Party</p>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{guideResult.situation_analysis.counterparty_role}</p>
                    </div>
                    <div className="result-block">
                      <p className="text-xs font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>Location</p>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{guideResult.situation_analysis.location || 'Not specified'}</p>
                    </div>
                    <div className="result-block">
                      <p className="text-xs font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>Written Contract</p>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{guideResult.situation_analysis.has_written_contract ? 'Yes' : 'No'}</p>
                    </div>
                  </div>

                  {/* Legal Issues Identified */}
                  {guideResult.situation_analysis.legal_issues.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <BookOpen className="w-4 h-4" style={{ color: 'var(--indigo)' }} />
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                          Legal Issues Identified
                        </h3>
                      </div>
                      <div className="space-y-2">
                        {guideResult.situation_analysis.legal_issues.map((issue, i) => (
                          <div key={i} className="result-block">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{issue.issue}</p>
                                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                  {issue.applicable_acts.join(', ')} — {issue.key_sections.join(', ')}
                                </p>
                              </div>
                              <span className={`tag ${issue.urgency === 'High' ? 'tag-rose' : issue.urgency === 'Medium' ? 'tag-amber' : 'tag-indigo'}`}>
                                {issue.urgency}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Clarification Questions ─────────────────────────── */}
            {guideResult.status === 'needs_clarification' && guideResult.clarification_response && (
              <div className="card overflow-hidden">
                <div className="px-6 py-4 flex items-center gap-2.5" style={{ borderBottom: '1px solid var(--border-light)', background: '#fffbeb' }}>
                  <HelpCircle className="w-5 h-5" style={{ color: 'var(--amber)' }} />
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--text-heading)', fontFamily: "'Lora', serif" }}>
                    A few questions to help us guide you better
                  </h2>
                </div>
                <div className="p-6 space-y-4">
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Answer these to get more accurate and actionable guidance. You can skip optional ones.
                  </p>

                  {guideResult.clarification_response.questions.map((q, i) => (
                    <div key={i} className="space-y-2">
                      <label className="block">
                        <div className="flex items-start gap-2 mb-1.5">
                          <span className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>
                            {i + 1}. {q.question}
                          </span>
                          {q.critical && <span className="tag tag-rose">Required</span>}
                        </div>
                        <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
                          Why this matters: {q.why_needed}
                        </p>
                        <textarea
                          rows={2}
                          className="input-field"
                          placeholder="Your answer..."
                          value={clarificationAnswers[q.id || `q_${i}`] || ''}
                          onChange={(e) => setClarificationAnswers(prev => ({
                            ...prev,
                            [q.id || `q_${i}`]: e.target.value,
                          }))}
                        />
                      </label>
                    </div>
                  ))}

                  {guideResult.clarification_response.missing_critical_info && guideResult.clarification_response.missing_critical_info.length > 0 && (
                    <div className="callout callout-amber">
                      <p className="text-xs font-semibold mb-1" style={{ color: 'var(--amber)' }}>Missing Critical Information</p>
                      <p className="text-sm" style={{ color: 'var(--text-body)' }}>
                        {guideResult.clarification_response.missing_critical_info.join(', ')}
                      </p>
                    </div>
                  )}

                  <button
                    onClick={handleClarificationSubmit}
                    disabled={loading}
                    className="btn-primary w-full"
                  >
                    {loading ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Generating guidance...</>
                    ) : (
                      <><ArrowRight className="w-4 h-4" /> Get detailed guidance</>
                    )}
                  </button>

                  {guideResult.clarification_response.can_proceed_without && (
                    <p className="text-xs text-center" style={{ color: 'var(--text-muted)' }}>
                      You can also submit without answering — we&apos;ll provide preliminary guidance.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* ── Full Guidance ───────────────────────────────────── */}
            {guideResult.status === 'complete' && guideResult.guidance && (
              <div className="card overflow-hidden">
                <div className="px-6 py-4 flex items-center gap-2.5" style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <CheckCircle className="w-5 h-5" style={{ color: 'var(--emerald)' }} />
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--text-heading)', fontFamily: "'Lora', serif" }}>
                    Your Legal Guidance
                  </h2>
                </div>
                <div className="p-6 space-y-6">
                  {/* Summary */}
                  <div className="callout callout-blue">
                    <p className="text-sm" style={{ color: 'var(--text-body)', lineHeight: 1.7 }}>
                      {guideResult.guidance.situation_summary}
                    </p>
                  </div>

                  {/* Applicable Laws */}
                  {guideResult.guidance.applicable_laws.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-heading)' }}>
                        Applicable Laws
                      </h3>
                      <div className="flex flex-wrap gap-1.5">
                        {guideResult.guidance.applicable_laws.map((law, i) => (
                          <span key={i} className="tag tag-indigo">{law}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Immediate Steps */}
                  {guideResult.guidance.immediate_steps.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <ChevronRight className="w-4 h-4" style={{ color: 'var(--emerald)' }} />
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                          Do This First
                        </h3>
                      </div>
                      <div className="space-y-2.5">
                        {guideResult.guidance.immediate_steps.map((step, i) => (
                          <div key={i} className="step-item">
                            <div className="step-number">{i + 1}</div>
                            <div className="flex-1">
                              <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{step.step}</p>
                              <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{step.reason}</p>
                              <div className="flex flex-wrap gap-1.5 mt-2">
                                {step.deadline && <span className="tag tag-amber"><Clock className="w-3 h-3 mr-1" />{step.deadline}</span>}
                                <span className={`tag ${step.do_it_yourself ? 'tag-emerald' : 'tag-indigo'}`}>
                                  {step.do_it_yourself ? '✓ DIY' : 'May need help'}
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Legal Options */}
                  {guideResult.guidance.legal_options.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <Scale className="w-4 h-4" style={{ color: 'var(--indigo)' }} />
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                          Your Legal Options
                        </h3>
                      </div>
                      <div className="space-y-3">
                        {guideResult.guidance.legal_options.map((opt, i) => (
                          <div key={i} className="card p-4">
                            <div className="flex items-start justify-between gap-3 mb-2">
                              <h4 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>{opt.name}</h4>
                              <span className={`tag ${opt.success_likelihood === 'high' ? 'tag-emerald' : opt.success_likelihood === 'medium' ? 'tag-amber' : 'tag-rose'}`}>
                                {opt.success_likelihood} success
                              </span>
                            </div>
                            <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>{opt.description}</p>
                            <div className="flex flex-wrap gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                              <span><DollarSign className="w-3 h-3 inline" /> {opt.estimated_cost}</span>
                              <span><Clock className="w-3 h-3 inline" /> {opt.estimated_time}</span>
                              <span><BookOpen className="w-3 h-3 inline" /> {opt.applicable_act}</span>
                            </div>
                            {(opt.pros.length > 0 || opt.cons.length > 0) && (
                              <div className="grid sm:grid-cols-2 gap-3 mt-3">
                                {opt.pros.length > 0 && (
                                  <div className="text-xs">
                                    <p className="font-semibold mb-1" style={{ color: 'var(--emerald)' }}>Pros</p>
                                    <ul className="space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
                                      {opt.pros.map((p, j) => <li key={j}>+ {p}</li>)}
                                    </ul>
                                  </div>
                                )}
                                {opt.cons.length > 0 && (
                                  <div className="text-xs">
                                    <p className="font-semibold mb-1" style={{ color: 'var(--rose)' }}>Cons</p>
                                    <ul className="space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
                                      {opt.cons.map((c, j) => <li key={j}>− {c}</li>)}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Red Flags */}
                  {guideResult.guidance.red_flags.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle className="w-4 h-4" style={{ color: 'var(--amber)' }} />
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                          Watch Out For
                        </h3>
                      </div>
                      <div className="space-y-2">
                        {guideResult.guidance.red_flags.map((flag, i) => (
                          <div key={i} className="callout callout-amber">
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{flag.flag}</p>
                              <span className={`tag ${flag.severity === 'critical' ? 'tag-rose' : 'tag-amber'}`}>{flag.severity}</span>
                            </div>
                            <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{flag.explanation}</p>
                            {flag.mitigation && (
                              <p className="text-xs mt-1" style={{ color: 'var(--emerald)' }}>→ {flag.mitigation}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* When to Hire a Lawyer */}
                  {guideResult.guidance.when_lawyer_needed.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <Shield className="w-4 h-4" style={{ color: 'var(--indigo)' }} />
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                          When to Hire a Lawyer
                        </h3>
                      </div>
                      <div className="space-y-2">
                        {guideResult.guidance.when_lawyer_needed.map((w, i) => (
                          <div key={i} className="result-block">
                            <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>{w.scenario}</p>
                            <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{w.reason}</p>
                            <p className="text-xs mt-1" style={{ color: 'var(--amber)' }}>Est. cost: {w.estimated_cost_range}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Jurisdiction + Disclaimer */}
                  <div className="callout callout-amber">
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Jurisdiction:</strong> {guideResult.guidance.jurisdiction}
                    </p>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                      This is legal information, not legal advice. Consult a qualified advocate for your specific case.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Error from API */}
            {guideResult.status === 'error' && guideResult.error && (
              <div className="callout callout-rose">
                <p className="text-sm" style={{ color: 'var(--rose)' }}>{guideResult.error}</p>
              </div>
            )}
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════ */}
        {/* ── QUERY / RESEARCH MODE RESULTS ──────────────────────── */}
        {/* ══════════════════════════════════════════════════════════ */}
        {queryResult && (
          <div className="animate-enter">
            <div className="card overflow-hidden">
              <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-light)' }}>
                <div className="flex items-center gap-2.5">
                  <CheckCircle className="w-5 h-5" style={{ color: 'var(--emerald)' }} />
                  <h2 className="text-lg font-semibold" style={{ color: 'var(--text-heading)', fontFamily: "'Lora', serif" }}>
                    Research Results
                  </h2>
                </div>
                {queryResult.answer.confidence !== undefined && (
                  <span className="tag tag-emerald">
                    {Math.round(queryResult.answer.confidence * 100)}% confidence
                  </span>
                )}
              </div>

              <div className="p-6 space-y-5">
                {/* Summary */}
                <div>
                  <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-heading)' }}>Summary</h3>
                  <p className="text-sm" style={{ color: 'var(--text-body)', lineHeight: 1.75 }}>
                    {queryResult.answer.summary}
                  </p>
                </div>

                {/* Sections */}
                {queryResult.answer.sections && queryResult.answer.sections.length > 0 && (
                  <div className="space-y-3">
                    {queryResult.answer.sections.map((sec, i) => (
                      <div key={i} className="result-block">
                        <h4 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-heading)' }}>{sec.heading}</h4>
                        <p className="text-sm" style={{ color: 'var(--text-body)', lineHeight: 1.7 }}>{sec.content}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Citations */}
                {queryResult.answer.citations && queryResult.answer.citations.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <BookOpen className="w-4 h-4" style={{ color: 'var(--amber)' }} />
                      <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>Sources</h3>
                    </div>
                    <div className="space-y-2">
                      {queryResult.answer.citations.map((c, i) => (
                        <div key={i} className="result-block text-xs" style={{ color: 'var(--text-secondary)' }}>
                          [{i + 1}] {c.act || c.citation_id} — §{c.section}: {c.description || c.text}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Critic metadata */}
                {queryResult.critic_metadata && (
                  <div className="result-block text-xs" style={{ color: 'var(--text-muted)' }}>
                    <strong>Verification:</strong> {queryResult.critic_metadata.summary} •
                    Faithfulness: {Math.round(queryResult.critic_metadata.overall_faithfulness * 100)}% •
                    Hallucinations: {queryResult.critic_metadata.hallucination_count}
                  </div>
                )}

                {/* Confidence Bar */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Confidence</span>
                    <span className="text-xs font-semibold" style={{ color: 'var(--emerald)' }}>
                      {Math.round(queryResult.answer.confidence * 100)}%
                    </span>
                  </div>
                  <div className="meter-track">
                    <div className="meter-fill" style={{ width: `${Math.round(queryResult.answer.confidence * 100)}%` }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <footer style={{ borderTop: '1px solid var(--border)' }}>
        <div className="max-w-3xl mx-auto px-6 py-6 text-center">
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            This tool provides legal information, not legal advice. Consult a qualified advocate for your specific matter.
          </p>
        </div>
      </footer>
    </div>
  );
}