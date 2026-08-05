'use client';

import { useState } from 'react';
import { Search, Scale, Lightbulb, Loader2, AlertCircle, CheckCircle, Clock, BookOpen, ChevronRight } from 'lucide-react';

/* ── Types ────────────────────────────────────────────────────────── */

interface LegalFrameworkItem {
  act?: string;
  section?: string;
  description?: string;
  relevance?: string;
}

interface ActionableStep {
  step?: string;
  title?: string;
  details?: string;
  timeline?: string;
  authority?: string;
}

interface Citation {
  citation?: string;
  source?: string;
  excerpt?: string;
  relevance?: string;
}

interface GuidanceResult {
  situation?: string;
  disclaimer?: string;
  legal_framework?: LegalFrameworkItem[];
  actionable_steps?: ActionableStep[];
  key_forms?: string[];
  next_steps?: string;
}

interface ResearchResult {
  answer?: string;
  citations?: Citation[];
  confidence?: number;
}

type QueryResult = GuidanceResult & ResearchResult;

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
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const endpoint = mode === 'guide' ? '/guide' : '/query';
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          mode === 'guide'
            ? { situation: question }
            : { query: question, mode: 'research' }
        ),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Something went wrong';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

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
              onClick={() => setMode(m.id)}
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
                  ? 'e.g., "My landlord is refusing to return my security deposit after I vacated the flat in Mumbai. I have the rental agreement and payment receipts."'
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

        {/* ── Results ─────────────────────────────────────────────── */}
        {result && (
          <div className="animate-enter">
            <div className="card overflow-hidden">

              {/* Result Header */}
              <div
                className="px-6 py-4 flex items-center justify-between"
                style={{ borderBottom: '1px solid var(--border-light)' }}
              >
                <div className="flex items-center gap-2.5">
                  <CheckCircle className="w-5 h-5" style={{ color: 'var(--emerald)' }} />
                  <h2
                    className="text-lg font-semibold"
                    style={{ color: 'var(--text-heading)', fontFamily: "'Lora', serif" }}
                  >
                    {mode === 'guide' ? 'Your Legal Guidance' : 'Research Results'}
                  </h2>
                </div>
                {result.confidence !== undefined && (
                  <span className="tag tag-emerald">
                    {Math.round(result.confidence * 100)}% confidence
                  </span>
                )}
              </div>

              {/* Result Body */}
              <div className="p-6 space-y-5">
                {mode === 'guide' ? (
                  <>
                    {/* Situation */}
                    {(result.situation || question) && (
                      <div className="callout callout-blue animate-enter">
                        <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--indigo)' }}>
                          Your Situation
                        </p>
                        <p className="text-sm" style={{ color: 'var(--text-body)' }}>
                          {result.situation || question}
                        </p>
                      </div>
                    )}

                    {/* Disclaimer */}
                    {result.disclaimer && (
                      <div className="callout callout-amber animate-enter delay-1">
                        <p className="text-xs font-semibold mb-1" style={{ color: 'var(--amber)' }}>
                          Disclaimer
                        </p>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                          {result.disclaimer}
                        </p>
                      </div>
                    )}

                    {/* Legal Framework */}
                    {result.legal_framework && result.legal_framework.length > 0 && (
                      <div className="animate-enter delay-2">
                        <div className="flex items-center gap-2 mb-3">
                          <BookOpen className="w-4 h-4" style={{ color: 'var(--indigo)' }} />
                          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                            Applicable Legal Framework
                          </h3>
                        </div>
                        <div className="space-y-2">
                          {result.legal_framework.map((item: LegalFrameworkItem, i: number) => (
                            <div key={i} className="result-block">
                              <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>
                                {item.act || item.section}
                              </p>
                              <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                {item.description || item.relevance}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actionable Steps */}
                    {result.actionable_steps && result.actionable_steps.length > 0 && (
                      <div className="animate-enter delay-3">
                        <div className="flex items-center gap-2 mb-3">
                          <ChevronRight className="w-4 h-4" style={{ color: 'var(--emerald)' }} />
                          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                            What You Should Do
                          </h3>
                        </div>
                        <div className="space-y-2.5">
                          {result.actionable_steps.map((step: ActionableStep, i: number) => (
                            <div key={i} className="step-item">
                              <div className="step-number">{i + 1}</div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>
                                  {step.step || step.title}
                                </p>
                                {step.details && (
                                  <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                    {step.details}
                                  </p>
                                )}
                                {(step.timeline || step.authority) && (
                                  <div className="flex flex-wrap gap-1.5 mt-2">
                                    {step.timeline && (
                                      <span className="tag tag-indigo">
                                        <Clock className="w-3 h-3 mr-1" />
                                        {step.timeline}
                                      </span>
                                    )}
                                    {step.authority && (
                                      <span className="tag tag-amber">{step.authority}</span>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Key Forms */}
                    {result.key_forms && result.key_forms.length > 0 && (
                      <div className="animate-enter delay-4">
                        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-heading)' }}>
                          Key Forms & Documents
                        </h3>
                        <div className="grid sm:grid-cols-2 gap-2">
                          {result.key_forms.map((f: string, i: number) => (
                            <div key={i} className="result-block text-sm" style={{ color: 'var(--text-body)' }}>
                              {f}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Next Steps */}
                    {result.next_steps && (
                      <div className="callout callout-emerald animate-enter delay-4">
                        <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--emerald)' }}>
                          Recommended Next Steps
                        </p>
                        <p className="text-sm" style={{ color: 'var(--text-body)' }}>
                          {result.next_steps}
                        </p>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    {/* Answer */}
                    {result.answer && (
                      <div className="animate-enter">
                        <h3
                          className="text-sm font-semibold mb-3"
                          style={{ color: 'var(--text-heading)' }}
                        >
                          Analysis
                        </h3>
                        <div
                          className="text-sm leading-relaxed"
                          style={{ color: 'var(--text-body)', lineHeight: 1.75 }}
                        >
                          {result.answer}
                        </div>
                      </div>
                    )}

                    {/* Citations */}
                    {result.citations && result.citations.length > 0 && (
                      <div className="animate-enter delay-2">
                        <div className="flex items-center gap-2 mb-3">
                          <BookOpen className="w-4 h-4" style={{ color: 'var(--amber)' }} />
                          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                            Citations & Sources
                          </h3>
                        </div>
                        <div className="space-y-2">
                          {result.citations.map((c: Citation, i: number) => (
                            <div key={i} className="result-block">
                              <p className="text-sm font-medium" style={{ color: 'var(--text-heading)' }}>
                                {c.citation || c.source}
                              </p>
                              {c.excerpt && (
                                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                  {c.excerpt}
                                </p>
                              )}
                              {c.relevance && (
                                <span className="tag tag-indigo mt-1.5 inline-block">{c.relevance}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Confidence */}
                    {result.confidence !== undefined && (
                      <div className="animate-enter delay-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                            Response Confidence
                          </span>
                          <span className="text-xs font-semibold" style={{ color: 'var(--emerald)' }}>
                            {Math.round(result.confidence * 100)}%
                          </span>
                        </div>
                        <div className="meter-track">
                          <div
                            className="meter-fill"
                            style={{ width: `${Math.round(result.confidence * 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </>
                )}
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