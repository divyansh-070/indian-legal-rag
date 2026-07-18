'use client';

import { useState } from 'react';
import { Search, Scale, FileText, Lightbulb, Loader2, AlertCircle, CheckCircle, ArrowRight } from 'lucide-react';

const MODES = [
  { id: 'guide', label: 'Legal Guidance', icon: Lightbulb, desc: 'Plain-language steps for your situation' },
  { id: 'query', label: 'Legal Research', icon: Scale, desc: 'Cited sections, cases, and analysis' },
];

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://indian-legal-rag-api-1hv3.onrender.com/api/v1';

export default function HomePage() {
  const [mode, setMode] = useState<'guide' | 'query'>('guide');
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
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
        body: JSON.stringify(mode === 'guide' 
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
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Indian Legal Guide</h1>
          <p className="mt-1 text-gray-600">AI-powered legal research and actionable guidance</p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-10">
        <div className="grid md:grid-cols-2 gap-8">
          {/* Mode Selector */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Choose Mode</h2>
            <div className="space-y-3">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id as 'guide' | 'query')}
                  className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                    mode === m.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <m.icon className={`w-5 h-5 ${mode === m.id ? 'text-blue-500' : 'text-gray-400'}`} />
                    <div>
                      <p className="font-medium text-gray-900">{m.label}</p>
                      <p className="text-sm text-gray-500">{m.desc}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Input Form */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {mode === 'guide' ? 'Describe Your Situation' : 'Enter Legal Query'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={4}
                placeholder={mode === 'guide'
                  ? 'e.g., "I want to register a private limited company in Maharashtra"'
                  : 'e.g., "Section 9 CGST Act composition scheme eligibility"'}
                className="w-full p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="w-full py-3 px-6 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Searching...
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

        {/* Error */}
        {error && (
          <div className="mt-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="mt-8">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="bg-gray-50 px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">
                  {mode === 'guide' ? 'Actionable Guidance' : 'Legal Research Results'}
                </h3>
                <CheckCircle className="w-5 h-5 text-green-500" />
              </div>
              <div className="p-6 prose prose-gray max-w-none">
                {mode === 'guide' ? (
                  <>
                    <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="font-medium text-blue-900 mb-2">Your Situation</p>
                      <p className="text-blue-700">{result.situation || question}</p>
                    </div>

                    {result.disclaimer && (
                      <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">
                        <strong>Disclaimer:</strong> {result.disclaimer}
                      </div>
                    )}

                    {result.legal_framework && (
                      <div className="mb-6">
                        <h4 className="font-semibold text-gray-900 mb-3">Applicable Legal Framework</h4>
                        <ul className="space-y-2">
                          {result.legal_framework.map((item: any, i: number) => (
                            <li key={i} className="text-gray-700">
                              <strong>{item.act || item.section}:</strong> {item.description || item.relevance}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {result.actionable_steps && (
                      <div className="mb-6">
                        <h4 className="font-semibold text-gray-900 mb-3">Actionable Steps</h4>
                        <ol className="space-y-3">
                          {result.actionable_steps.map((step: any, i: number) => (
                            <li key={i} className="flex gap-3 p-4 bg-gray-50 rounded-lg">
                              <span className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 text-blue-700 font-medium flex items-center justify-center text-sm">
                                {i + 1}
                              </span>
                              <div>
                                <p className="font-medium text-gray-900">{step.step || step.title}</p>
                                {step.details && <p className="text-sm text-gray-600 mt-1">{step.details}</p>}
                                {step.timeline && <p className="text-sm text-gray-500 mt-1">⏱ {step.timeline}</p>}
                                {step.authority && <p className="text-sm text-gray-500 mt-1">🏛 {step.authority}</p>}
                              </div>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}

                    {result.key_forms && (
                      <div className="mb-6">
                        <h4 className="font-semibold text-gray-900 mb-3">Key Forms & Documents</h4>
                        <ul className="list-disc list-inside space-y-1 text-gray-700">
                          {result.key_forms.map((f: string, i: number) => (
                            <li key={i}>{f}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {result.next_steps && (
                      <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
                        <h4 className="font-semibold text-green-900 mb-2">Next Steps</h4>
                        <p className="text-green-700">{result.next_steps}</p>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    {result.answer && (
                      <div className="mb-6">
                        <h4 className="font-semibold text-gray-900 mb-3">Answer</h4>
                        <div className="prose prose-gray max-w-none">{result.answer}</div>
                      </div>
                    )}

                    {result.citations && result.citations.length > 0 && (
                      <div className="mb-6">
                        <h4 className="font-semibold text-gray-900 mb-3">Citations</h4>
                        <ul className="space-y-2">
                          {result.citations.map((c: any, i: number) => (
                            <li key={i} className="p-3 bg-gray-50 rounded-lg text-sm text-gray-700">
                              <p className="font-medium">{c.citation || c.source}</p>
                              {c.excerpt && <p className="text-gray-600 mt-1">{c.excerpt}</p>}
                              {c.relevance && <p className="text-xs text-gray-500 mt-1">Relevance: {c.relevance}</p>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {result.confidence !== undefined && (
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <p className="text-sm text-gray-600">
                          Confidence: <strong>{Math.round(result.confidence * 100)}%</strong>
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-4xl mx-auto px-4 py-6 text-center text-sm text-gray-500">
          <p>Not legal advice. Consult a qualified advocate for your specific matter.</p>
        </div>
      </footer>
    </div>
  );
}