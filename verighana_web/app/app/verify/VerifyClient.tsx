'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { createClient } from '@/lib/supabase/client'
import type { VerifyResponse, NarrativeDelta, BiasSignal } from '@/types/api'
import { VerdictChip } from '@/components/ui/VerdictChip'
import { TruthBar } from '@/components/ui/TruthBar'

type Tier = 'free' | 'pro' | 'institutional'

interface Props {
  userId: string
  accessToken: string
  tier: Tier
  models: { id: string; name: string; tier_required: string }[]
  used: number
  dailyLimit: number | null
  initialClaim?: string
}

const VERDICT_GRADIENT: Record<string, string> = {
  VERIFIED:       'linear-gradient(90deg,#16a34a,#4ade80)',
  PARTIAL:        'linear-gradient(90deg,#d97706,#fbbf24)',
  FALSE:          'linear-gradient(90deg,#dc2626,#f87171)',
  UNCORROBORATED: 'linear-gradient(90deg,#475569,#94a3b8)',
  ERROR:          'linear-gradient(90deg,#dc2626,#f87171)',
}

export function VerifyClient({ userId, accessToken, tier, models, used: initialUsed, dailyLimit, initialClaim }: Props) {
  const [claim, setClaim]           = useState(initialClaim ?? '')
  const [selectedModel, setModel]   = useState(models[0]?.id ?? '')
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [result, setResult]         = useState<(VerifyResponse & { barWidth: number }) | null>(null)
  const [used, setUsed]             = useState(initialUsed)

  const remaining = dailyLimit !== null ? Math.max(0, dailyLimit - used) : null
  const limitHit  = remaining !== null && remaining <= 0

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault()
    const input = claim.trim()
    if (!input) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const data = await api.verify({ claim: input, model: selectedModel }, accessToken)
      setResult({ ...data, barWidth: data.score })
      setUsed(u => u + 1)

      // Save to verification_log (fire-and-forget — don't block the UI)
      const supabase = createClient()
      supabase.from('verification_log').insert({
        user_id:           userId,
        input_claim:       input,
        score:             data.score,
        verdict:           data.verdict,
        explanation:       data.explanation,
        matched_sources:   JSON.stringify(data.sources),
        model_used:        data.model_used,
        response_time_ms:  data.processing_ms ?? null,
        sources_retrieved: data.sources?.length ?? 0,
      }).then(() => {}) // ignore errors silently

    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail
      if (detail?.includes('rate limit') || detail?.includes('quota')) {
        setError('Daily verification limit reached. Upgrade to Pro for unlimited access.')
      } else {
        setError(detail ?? 'Verification failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5 max-w-2xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Fact Verification</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Paste any claim — AI searches 60+ trusted Ghanaian sources and scores the verdict.
        </p>
      </div>

      {/* Usage bar — free tier only */}
      {dailyLimit !== null && (
        <div className="bg-white border border-slate-200 rounded-xl px-5 py-3.5 flex items-center gap-4">
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-slate-500">Daily verifications</span>
              <span className={`font-semibold font-mono-vg ${remaining === 0 ? 'text-red-500' : 'text-slate-700'}`}>
                {used} / {dailyLimit}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, (used / dailyLimit) * 100)}%`,
                  background: remaining === 0 ? '#dc2626' : (remaining ?? 999) <= 1 ? '#d97706' : '#2563eb',
                }}
              />
            </div>
          </div>
          {remaining !== null && remaining <= 2 && remaining > 0 && (
            <span className="text-xs text-amber-600 font-medium shrink-0">{remaining} left today</span>
          )}
          {remaining === 0 && (
            <a href="/app/billing" className="text-xs text-blue-600 hover:text-blue-700 font-medium shrink-0">Upgrade →</a>
          )}
        </div>
      )}

      {/* Input form */}
      <form onSubmit={handleVerify} className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1.5 font-mono-vg uppercase tracking-wider">
            Claim to verify
          </label>
          <textarea
            value={claim}
            onChange={e => setClaim(e.target.value)}
            placeholder="Paste a social media post, WhatsApp message, headline, or any claim you want to fact-check…"
            rows={4}
            maxLength={2000}
            className="w-full bg-slate-50 border border-slate-200 text-slate-800 placeholder:text-slate-400 text-sm px-4 py-3 rounded-lg outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/20 transition-all resize-none"
          />
          <div className="flex justify-between mt-1">
            <span className="text-[0.68rem] text-slate-400">Press verify or Ctrl+Enter</span>
            <span className="text-[0.68rem] text-slate-400 font-mono-vg">{claim.length}/2000</span>
          </div>
        </div>

        {/* Model selector */}
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1.5 font-mono-vg uppercase tracking-wider">
              AI Model
            </label>
            <select
              aria-label="AI model selection"
              value={selectedModel}
              onChange={e => setModel(e.target.value)}
              disabled={tier === 'free'}
              className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2.5 rounded-lg outline-none focus:border-blue-400 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {models.map(m => (
                <option key={m.id} value={m.id}>{m.name ?? m.id}</option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={loading || limitHit || !claim.trim()}
            className="self-end bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors flex items-center gap-2"
          >
            {loading
              ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Checking…</>
              : 'Verify →'
            }
          </button>
        </div>

        {tier === 'free' && (
          <p className="text-[0.68rem] text-slate-400">
            Free plan: model selection locked.{' '}
            <a href="/app/billing" className="text-blue-500 hover:underline">Upgrade to Pro</a> to choose models.
          </p>
        )}
      </form>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 text-sm px-4 py-3 rounded-xl">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden animate-fade-in">
          {/* Verdict header */}
          <div
            className="px-6 py-4 flex items-center justify-between"
            style={{ background: `${VERDICT_GRADIENT[result.verdict] ?? VERDICT_GRADIENT.UNCORROBORATED}, opacity: 0.08` }}
          >
            <div>
              <div className="flex items-center gap-3 mb-1">
                <VerdictChip verdict={result.verdict as 'VERIFIED' | 'PARTIAL' | 'FALSE' | 'UNCORROBORATED'} />
                <span className="font-display text-3xl font-extrabold text-[#0f2240]">{result.score}%</span>
              </div>
              <p className="text-xs text-slate-500 font-mono-vg">
                {result.model_used} · {result.processing_ms > 0 ? `${(result.processing_ms / 1000).toFixed(1)}s` : '—'} · {result.search_method}
              </p>
            </div>
          </div>

          {/* Web search disclaimer */}
          {result.disclaimer && (
            <div className="mx-6 mt-4 mb-0 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
              <p className="text-xs font-semibold text-amber-700 mb-1">Web Search Results</p>
              <p className="text-xs text-amber-600 leading-relaxed">{result.disclaimer}</p>
            </div>
          )}

          {/* Truth bar */}
          <div className="px-6 py-4 border-b border-slate-100">
            <TruthBar score={result.score} showLabel={false} />
          </div>

          {/* Explanation */}
          <div className="px-6 py-4 border-b border-slate-100">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-2">AI Analysis</p>
            <p className="text-sm text-slate-700 leading-relaxed">{result.explanation}</p>
          </div>

          {/* Sources */}
          {result.sources.length > 0 && (
            <div className="px-6 py-4">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-3">Sources</p>
              <div className="space-y-2.5">
                {result.sources.map((s, i) => (
                  <div key={i} className="flex items-start gap-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                    <div>
                      {s.url && s.url !== '#'
                        ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:text-blue-700 hover:underline">{s.title}</a>
                        : <span className="text-sm text-slate-700">{s.title}</span>
                      }
                      <span className="text-xs text-slate-400"> — {s.source}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Triangulation & Nuance Panel */}
          {(result.convergence?.length || result.narrative_delta?.length || result.bias_signals?.length) ? (
            <div className="border-t border-slate-100">
              {/* Header bar */}
              <div className="px-6 py-3 bg-slate-50 border-b border-slate-100 flex items-center gap-2">
                <span className="text-xs font-mono-vg uppercase tracking-widest text-slate-500">Triangulation &amp; Nuance</span>
                {result.triangulation_confidence && (
                  <span className={`ml-auto text-[0.65rem] font-semibold px-2 py-0.5 rounded-full font-mono-vg ${
                    result.triangulation_confidence === 'high'   ? 'bg-green-100 text-green-700' :
                    result.triangulation_confidence === 'medium' ? 'bg-amber-100 text-amber-700' :
                                                                   'bg-slate-200 text-slate-500'
                  }`}>
                    {result.triangulation_confidence.toUpperCase()} confidence
                  </span>
                )}
              </div>

              {/* Reliability note */}
              {result.triangulation_note && (
                <div className="px-6 py-3 border-b border-slate-100">
                  <p className="text-xs text-slate-600 italic leading-relaxed">{result.triangulation_note}</p>
                </div>
              )}

              {/* Convergence — facts sources agree on */}
              {result.convergence && result.convergence.length > 0 && (
                <div className="px-6 py-4 border-b border-slate-100">
                  <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-2.5">Where sources agree</p>
                  <ul className="space-y-1.5">
                    {result.convergence.map((fact, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                        <span className="mt-1 shrink-0 w-4 h-4 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-[0.6rem] font-bold">✓</span>
                        {fact}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Narrative Delta — framing differences */}
              {result.narrative_delta && result.narrative_delta.length > 0 && (
                <div className="px-6 py-4 border-b border-slate-100">
                  <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-3">Narrative differences</p>
                  <div className="space-y-4">
                    {result.narrative_delta.map((delta: NarrativeDelta, i: number) => (
                      <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 overflow-hidden">
                        <div className="px-4 py-2 border-b border-slate-100">
                          <span className="text-xs font-semibold text-slate-600">{delta.aspect}</span>
                        </div>
                        <div className="divide-y divide-slate-100">
                          {delta.variations.map((v, j) => (
                            <div key={j} className="px-4 py-2.5 flex gap-3 items-start">
                              <span className={`shrink-0 text-[0.6rem] font-mono-vg px-1.5 py-0.5 rounded mt-0.5 ${
                                v.tone === 'alarming'    ? 'bg-red-100 text-red-600' :
                                v.tone === 'dismissive'  ? 'bg-slate-200 text-slate-500' :
                                v.tone === 'positive'    ? 'bg-green-100 text-green-600' :
                                v.tone === 'promotional' ? 'bg-blue-100 text-blue-600' :
                                v.tone === 'critical'    ? 'bg-orange-100 text-orange-600' :
                                                           'bg-slate-100 text-slate-500'
                              }`}>{v.tone}</span>
                              <div>
                                <span className="text-[0.7rem] font-semibold text-slate-500 block">{v.source}</span>
                                <span className="text-xs text-slate-700">{v.framing}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="px-4 py-2.5 bg-amber-50 border-t border-amber-100">
                          <p className="text-xs text-amber-800 leading-relaxed">{delta.delta_analysis}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Bias Signals */}
              {result.bias_signals && result.bias_signals.length > 0 && (
                <div className="px-6 py-4">
                  <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-2.5">Bias signals detected</p>
                  <div className="space-y-2">
                    {result.bias_signals.map((signal: BiasSignal, i: number) => (
                      <div key={i} className="flex items-start gap-2.5 text-xs">
                        <span className="shrink-0 bg-orange-100 text-orange-600 font-mono-vg px-1.5 py-0.5 rounded text-[0.6rem] mt-0.5">{signal.type}</span>
                        <div>
                          <span className="font-semibold text-slate-600">{signal.source}: </span>
                          <span className="text-slate-600">{signal.signal}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {/* Rate limit info */}
          {result.rate_limit && dailyLimit !== null && (
            <div className="px-6 py-3 bg-slate-50 border-t border-slate-100">
              <p className="text-xs text-slate-400 font-mono-vg">
                {result.rate_limit.remaining} verification{result.rate_limit.remaining !== 1 ? 's' : ''} remaining today
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
