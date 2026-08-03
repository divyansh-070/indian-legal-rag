'use client';

import { useState } from 'react';
import { Search, Scale, Lightbulb, Loader2, AlertCircle, CheckCircle, Shield, Clock, BookOpen, ChevronRight, Sparkles } from 'lucide-react';

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
    desc: 'Plain-language actionable steps for your situation',
    accent: 'var(--accent-gold)',
    badgeClass: 'badge-gold',
  },
  {
    id: 'query' as const,
    label: 'Legal Research',
    icon: Scale,
    desc: 'Cited sections, statutes, and case law analysis',
    accent: 'var(--accent-blue)',
    badgeClass: 'badge-blue',
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
    <div className="min-h-screen bg-gradient-radial bg-grid">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="relative border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, var(--accent-blue), #7c3aed)',
                boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)',
              }}
            >
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                Indian Legal Guide
              </h1>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                AI-Powered Legal Intelligence
              </p>
            </div>
          </div>
          <span className="badge badge-blue">
            <Sparkles className="w-3 h-3 mr-1" />
            Beta
          </span>
        </div>
      </header>

      {/* ── Main Content ─────────────────────────────────────────── */}
      <main className="max-w-5xl mx-auto px-6 py-10">
        {/* Hero Section */}
        <div className="text-center mb-10 animate-fade-in-up">
          <h2
            className="text-3xl md:text-4xl font-extrabold mb-3"
            style={{
              background: 'linear-gradient(135deg, var(--text-primary) 0%, var(--accent-blue) 50%, var(--accent-gold) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Navigate Indian Law with Confidence
          </h2>
          <p className="text-base max-w-2xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
            Get actionable legal guidance or deep research with cited statutes and case law — powered by AI.
          </p>
        </div>

        {/* Mode & Input Grid */}
        <div className="grid md:grid-cols-5 gap-6 mb-8">
          {/* Mode Selector — Left */}
          <div className="md:col-span-2 space-y-4 animate-fade-in-up animate-delay-100">
            <p className="text-sm font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Choose Mode
            </p>
            {MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                className={`mode-card w-full text-left ${mode === m.id ? 'active' : ''}`}
              >
                <div className="flex items-start gap-3 relative z-10">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{
                      background:
                        mode === m.id
                          ? `linear-gradient(135deg, ${m.accent}, rgba(59,130,246,0.6))`
                          : 'rgba(148, 163, 184, 0.08)',
                      boxShadow:
                        mode === m.id ? `0 4px 12px ${m.accent}40` : 'none',
                      transition: 'all 0.3s ease',
                    }}
                  >
                    <m.icon
                      className="w-5 h-5"
                      style={{
                        color: mode === m.id ? 'white' : 'var(--text-muted)',
                      }}
                    />
                  </div>
                  <div>
                    <p className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
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

          {/* Input Form — Right */}
          <div className="md:col-span-3 glass-card-static p-6 animate-fade-in-up animate-delay-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                {mode === 'guide' ? 'Describe Your Situation' : 'Enter Your Legal Query'}
              </h2>
              <span className={`badge ${mode === 'guide' ? 'badge-gold' : 'badge-blue'}`}>
                {mode === 'guide' ? 'Guidance' : 'Research'}
              </span>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <textarea
                id="legal-query-input"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={5}
                placeholder={
                  mode === 'guide'
                    ? 'e.g., "My landlord is refusing to return my security deposit after I vacated the flat in Mumbai. I have the rental agreement and payment receipts."'
                    : 'e.g., "Section 9 CGST Act composition scheme eligibility criteria for service providers"'
                }
                className="input-glass"
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
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    {mode === 'guide' ? 'Get Guidance' : 'Research'}
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* ── Loading State ──────────────────────────────────────── */}
        {loading && (
          <div className="animate-fade-in space-y-3 mb-8">
            <div className="loading-spinner h-4 w-3/4 rounded" />
            <div className="loading-spinner h-4 w-1/2 rounded animate-delay-200" />
            <div className="loading-spinner h-4 w-5/6 rounded animate-delay-400" />
          </div>
        )}

        {/* ── Error ──────────────────────────────────────────────── */}
        {error && (
          <div className="alert-error mb-8 animate-fade-in-up">
            <AlertCircle className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--accent-rose)' }} />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* ── Results ─────────────────────────────────────────────── */}
        {result && (
          <div className="animate-fade-in-up">
            <div className="glass-card-static overflow-hidden">
              {/* Result Header */}
              <div
                className="px-6 py-4 flex items-center justify-between"
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  background: 'rgba(59, 130, 246, 0.04)',
                }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{
                      background: 'linear-gradient(135deg, var(--accent-emerald), #059669)',
                      boxShadow: '0 2px 8px rgba(16, 185, 129, 0.3)',
                    }}
                  >
                    <CheckCircle className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {mode === 'guide' ? 'Actionable Guidance' : 'Research Results'}
                  </h3>
                </div>
                {result.confidence !== undefined && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      Confidence
                    </span>
                    <span className="badge badge-emerald">
                      {Math.round(result.confidence * 100)}%
                    </span>
                  </div>
                )}
              </div>

              {/* Result Body */}
              <div className="p-6 space-y-6">
                {mode === 'guide' ? (
                  /* ── Guide Mode Results ─────────────────────── */
                  <>
                    {/* Situation Summary */}
                    {(result.situation || question) && (
                      <div className="alert-info animate-fade-in-up">
                        <p className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#60a5fa' }}>
                          Your Situation
                        </p>
                        <p className="text-sm" style={{ color: '#93c5fd' }}>
                          {result.situation || question}
                        </p>
                      </div>
                    )}

                    {/* Disclaimer */}
                    {result.disclaimer && (
                      <div className="alert-warning animate-fade-in-up animate-delay-100">
                        <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent-gold)' }}>
                          ⚖️ Disclaimer
                        </p>
                        <p className="text-sm" style={{ color: '#d4a853cc' }}>
                          {result.disclaimer}
                        </p>
                      </div>
                    )}

                    {/* Legal Framework */}
                    {result.legal_framework && result.legal_framework.length > 0 && (
                      <div className="animate-fade-in-up animate-delay-200">
                        <div className="flex items-center gap-2 mb-3">
                          <BookOpen className="w-4 h-4" style={{ color: 'var(--accent-blue)' }} />
                          <h4 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                            Applicable Legal Framework
                          </h4>
                        </div>
                        <div className="space-y-2">
                          {result.legal_framework.map((item: LegalFrameworkItem, i: number) => (
                            <div key={i} className="result-section">
                              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
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
                      <div className="animate-fade-in-up animate-delay-300">
                        <div className="flex items-center gap-2 mb-3">
                          <ChevronRight className="w-4 h-4" style={{ color: 'var(--accent-emerald)' }} />
                          <h4 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                            Actionable Steps
                          </h4>
                        </div>
                        <div className="space-y-3">
                          {result.actionable_steps.map((step: ActionableStep, i: number) => (
                            <div key={i} className="step-item">
                              <div className="step-number">{i + 1}</div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                                  {step.step || step.title}
                                </p>
                                {step.details && (
                                  <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                    {step.details}
                                  </p>
                                )}
                                <div className="flex flex-wrap gap-2 mt-2">
                                  {step.timeline && (
                                    <span className="badge badge-blue">
                                      <Clock className="w-3 h-3 mr-1" />
                                      {step.timeline}
                                    </span>
                                  )}
                                  {step.authority && (
                                    <span className="badge badge-gold">
                                      🏛 {step.authority}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Key Forms */}
                    {result.key_forms && result.key_forms.length > 0 && (
                      <div className="animate-fade-in-up animate-delay-400">
                        <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
                          📋 Key Forms & Documents
                        </h4>
                        <div className="grid sm:grid-cols-2 gap-2">
                          {result.key_forms.map((f: string, i: number) => (
                            <div key={i} className="result-section text-sm" style={{ color: 'var(--text-secondary)' }}>
                              {f}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Next Steps */}
                    {result.next_steps && (
                      <div className="alert-success animate-fade-in-up animate-delay-400">
                        <p className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#34d399' }}>
                          Recommended Next Steps
                        </p>
                        <p className="text-sm" style={{ color: '#6ee7b7' }}>
                          {result.next_steps}
                        </p>
                      </div>
                    )}
                  </>
                ) : (
                  /* ── Query / Research Mode Results ────────────── */
                  <>
                    {/* Answer */}
                    {result.answer && (
                      <div className="animate-fade-in-up">
                        <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
                          Analysis
                        </h4>
                        <div
                          className="text-sm leading-relaxed"
                          style={{ color: 'var(--text-secondary)' }}
                        >
                          {result.answer}
                        </div>
                      </div>
                    )}

                    {/* Citations */}
                    {result.citations && result.citations.length > 0 && (
                      <div className="animate-fade-in-up animate-delay-200">
                        <div className="flex items-center gap-2 mb-3">
                          <BookOpen className="w-4 h-4" style={{ color: 'var(--accent-gold)' }} />
                          <h4 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                            Citations & Sources
                          </h4>
                        </div>
                        <div className="space-y-2">
                          {result.citations.map((c: Citation, i: number) => (
                            <div key={i} className="result-section">
                              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                                {c.citation || c.source}
                              </p>
                              {c.excerpt && (
                                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                  {c.excerpt}
                                </p>
                              )}
                              {c.relevance && (
                                <div className="mt-1.5">
                                  <span className="badge badge-blue text-xs">{c.relevance}</span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Confidence Bar */}
                    {result.confidence !== undefined && (
                      <div className="animate-fade-in-up animate-delay-300">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                            Response Confidence
                          </span>
                          <span className="text-xs font-semibold" style={{ color: 'var(--accent-emerald)' }}>
                            {Math.round(result.confidence * 100)}%
                          </span>
                        </div>
                        <div className="confidence-bar">
                          <div
                            className="confidence-bar-fill"
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
      <footer
        className="mt-16 py-6 text-center"
        style={{ borderTop: '1px solid var(--border-subtle)' }}
      >
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          ⚖️ Not legal advice. Consult a qualified advocate for your specific matter.
        </p>
        <p className="text-xs mt-1" style={{ color: 'rgba(100,116,139,0.5)' }}>
          Indian Legal Guide v1.0 — Built with AI for accessibility to justice.
        </p>
      </footer>
    </div>
  );
}