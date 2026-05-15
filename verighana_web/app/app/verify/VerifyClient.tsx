'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { createClient } from '@/lib/supabase/client'
import type { VerifyResponse, NarrativeDelta, BiasSignal, SourceCitation } from '@/types/api'
import { VerdictChip } from '@/components/ui/VerdictChip'
import { TruthBar } from '@/components/ui/TruthBar'

// ── Helpers ────────────────────────────────────────────────────────────────
const STOPWORDS = new Set([
  'the','a','an','of','in','on','at','to','for','and','or','is','are','was','were','be','been',
  'this','that','these','those','it','its','as','by','with','from','has','have','had','will',
  'would','can','could','should','i','you','he','she','they','we','his','her','their','our',
])

function tokenize(text: string): Set<string> {
  return new Set(
    text.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(t => t.length > 2 && !STOPWORDS.has(t))
  )
}

function tierSources(sources: SourceCitation[], claim: string): { primary: SourceCitation[]; related: SourceCitation[] } {
  const claimTokens = tokenize(claim)
  if (claimTokens.size === 0 || sources.length === 0) return { primary: sources, related: [] }

  const scored = sources.map(s => {
    const titleTokens = tokenize(s.title)
    let overlap = 0
    for (const t of titleTokens) if (claimTokens.has(t)) overlap++
    return { src: s, overlap }
  })

  // Primary if title shares ≥2 significant tokens with claim, OR ≥30% of significant claim tokens.
  const threshold = Math.max(2, Math.ceil(claimTokens.size * 0.3))
  const primary = scored.filter(x => x.overlap >= threshold || x.overlap >= 2).map(x => x.src)
  const related = scored.filter(x => !(x.overlap >= threshold || x.overlap >= 2)).map(x => x.src)

  // Fallback: if heuristic produced no primaries, show top-3 by overlap as primary.
  if (primary.length === 0) {
    const sorted = [...scored].sort((a, b) => b.overlap - a.overlap)
    return {
      primary: sorted.slice(0, Math.min(3, sorted.length)).map(x => x.src),
      related: sorted.slice(3).map(x => x.src),
    }
  }
  return { primary, related }
}

function isEmptyVariation(framing: string | undefined): boolean {
  const f = (framing ?? '').toLowerCase().trim()
  if (!f) return true
  return /^(no mention|not mentioned|no info|no information|n\/?a|none|nothing|silent)\b/.test(f)
}

function hasMeaningfulDelta(delta: NarrativeDelta): boolean {
  const real = delta.variations.filter(v => !isEmptyVariation(v.framing))
  if (real.length < 2) return false
  const tones = new Set(real.map(v => v.tone))
  return tones.size > 1 || real.some(v => v.tone !== 'neutral')
}

function getHeadline(r: VerifyResponse): string {
  if (r.summary && r.summary.trim()) return r.summary.trim()
  const first = r.explanation.split(/[.!?](?:\s|$)/)[0]
  return first ? first.trim().replace(/\.$/, '') + '.' : r.explanation
}

function shortModelName(m: string): string {
  // e.g. "groq:llama-3.1-8b-instant" → "llama-3.1-8b"
  const tail = m.includes(':') ? m.split(':').pop()! : m
  return tail.replace(/-instant$|-flash$/, '').slice(0, 24)
}

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
        user_id:         userId,
        input_claim:     input,
        score:           data.score,
        verdict:         data.verdict,
        explanation:     data.explanation,
        matched_sources: JSON.stringify(data.sources),
        model_used:      data.model_used,
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
      {result && (() => {
        const { primary, related } = tierSources(result.sources, claim)
        const meaningfulDeltas = (result.narrative_delta ?? []).filter(hasMeaningfulDelta)
        const hasTriangulation =
          (result.convergence?.length ?? 0) > 0 ||
          meaningfulDeltas.length > 0 ||
          (result.bias_signals?.length ?? 0) > 0 ||
          !!result.triangulation_note

        return <ResultCard
          result={result}
          claim={claim}
          primary={primary}
          related={related}
          meaningfulDeltas={meaningfulDeltas}
          hasTriangulation={hasTriangulation}
          dailyLimit={dailyLimit}
        />
      })()}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  ResultCard — redesigned verdict display
// ══════════════════════════════════════════════════════════════════════════════

interface ResultCardProps {
  result: VerifyResponse & { barWidth: number }
  claim: string
  primary: SourceCitation[]
  related: SourceCitation[]
  meaningfulDeltas: NarrativeDelta[]
  hasTriangulation: boolean
  dailyLimit: number | null
}

function sourceIcon(name: string): string {
  const n = name.toLowerCase()
  if (/gov|ministry|parliament|bog|gss|gra|nmimr|ghs|ec/.test(n)) return '🏛️'
  if (/myjoyonline|graphic|ghanaweb|citi|joy|tv3|3news|pulse|gbc|yen|adomonline/.test(n)) return '📰'
  if (/health|who|cdc|fda/.test(n)) return '⚕️'
  if (/research|university|gimpa|legon|knust/.test(n)) return '🎓'
  return '📰'
}

function ResultCard({ result, claim, primary, related, meaningfulDeltas, hasTriangulation, dailyLimit }: ResultCardProps) {
  const [showRelated, setShowRelated] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [shareLabel, setShareLabel] = useState<'Share' | 'Copied!'>('Share')

  const headline = getHeadline(result)

  async function handleShare() {
    const text = `${result.verdict} (${result.score}%) — ${headline}\n\nClaim: ${claim}\n\nVerified by VeriGhana`
    try {
      if (navigator.share) {
        await navigator.share({ title: 'VeriGhana verdict', text })
      } else {
        await navigator.clipboard.writeText(text)
        setShareLabel('Copied!')
        setTimeout(() => setShareLabel('Share'), 2000)
      }
    } catch { /* user cancelled */ }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden animate-fade-in">
      {/* ── Header: chip + score + timestamp ─────────────────────────────── */}
      <div className="px-6 py-4 border-b border-slate-100 flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <VerdictChip verdict={result.verdict as 'VERIFIED' | 'PARTIAL' | 'FALSE' | 'UNCORROBORATED'} />
            <span className="font-display text-3xl font-extrabold text-[#0f2240] leading-none">{result.score}%</span>
            <span className="text-xs text-slate-400 font-mono-vg ml-auto whitespace-nowrap">Verified just now</span>
          </div>
          <p className="font-display font-bold text-[#0f2240] text-base md:text-lg leading-snug">
            {headline}
          </p>
        </div>
      </div>

      {/* Truth bar */}
      <div className="px-6 py-4 border-b border-slate-100">
        <TruthBar score={result.score} showLabel={false} />
      </div>

      {/* Web-search disclaimer */}
      {result.disclaimer && (
        <div className="mx-6 mt-4 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold text-amber-700 mb-1">Web Search Results</p>
          <p className="text-xs text-amber-600 leading-relaxed">{result.disclaimer}</p>
        </div>
      )}

      {/* ── Primary citations ────────────────────────────────────────────── */}
      {primary.length > 0 && (
        <div className="px-6 py-4 border-b border-slate-100">
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Primary citations</p>
            <span className="text-[0.65rem] text-slate-400 font-mono-vg">{primary.length} of {primary.length + related.length}</span>
          </div>
          <div className="space-y-2">
            {primary.map((s, i) => (
              <a
                key={i}
                href={s.url && s.url !== '#' ? s.url : undefined}
                target={s.url && s.url !== '#' ? '_blank' : undefined}
                rel="noopener noreferrer"
                className={`flex items-start gap-3 p-2.5 rounded-lg border border-slate-100 hover:border-blue-200 hover:bg-blue-50/40 transition-colors ${
                  !s.url || s.url === '#' ? 'pointer-events-none' : ''
                }`}
              >
                <span className="shrink-0 w-8 h-8 rounded-md bg-slate-50 border border-slate-100 flex items-center justify-center text-base" aria-hidden>
                  {sourceIcon(s.source)}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-blue-700 font-medium leading-snug line-clamp-2">{s.title}</p>
                  <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-wider mt-0.5">{s.source}</p>
                </div>
              </a>
            ))}
          </div>

          {/* Related (collapsed by default) */}
          {related.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowRelated(v => !v)}
                className="text-xs text-slate-500 hover:text-slate-700 font-mono-vg flex items-center gap-1.5"
              >
                <span className={`transition-transform ${showRelated ? 'rotate-90' : ''}`}>▶</span>
                {showRelated ? 'Hide' : 'Show'} also retrieved ({related.length})
              </button>
              {showRelated && (
                <div className="mt-3 space-y-1.5 pl-4">
                  {related.map((s, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="w-1 h-1 rounded-full bg-slate-300 mt-1.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        {s.url && s.url !== '#'
                          ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-slate-700 hover:underline">{s.title}</a>
                          : <span className="text-slate-500">{s.title}</span>
                        }
                        <span className="text-slate-400"> — {s.source}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── AI analysis (full explanation) ───────────────────────────────── */}
      <div className="px-6 py-4 border-b border-slate-100">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-2">AI Analysis</p>
        <p className="text-sm text-slate-700 leading-relaxed">{result.explanation}</p>
      </div>

      {/* ── Triangulation panel ──────────────────────────────────────────── */}
      {hasTriangulation && (
        <div>
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

          {result.triangulation_note && (
            <div className="px-6 py-3 border-b border-slate-100">
              <p className="text-xs text-slate-600 italic leading-relaxed">{result.triangulation_note}</p>
            </div>
          )}

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

          {meaningfulDeltas.length > 0 && (
            <div className="px-6 py-4 border-b border-slate-100">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-3">Narrative differences</p>
              <div className="space-y-4">
                {meaningfulDeltas.map((delta, i) => (
                  <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 overflow-hidden">
                    <div className="px-4 py-2 border-b border-slate-100">
                      <span className="text-xs font-semibold text-slate-600">{delta.aspect}</span>
                    </div>
                    <div className="divide-y divide-slate-100">
                      {delta.variations.filter(v => !isEmptyVariation(v.framing)).map((v, j) => (
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
                    {delta.delta_analysis && (
                      <div className="px-4 py-2.5 bg-amber-50 border-t border-amber-100">
                        <p className="text-xs text-amber-800 leading-relaxed">{delta.delta_analysis}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.bias_signals && result.bias_signals.length > 0 && (
            <div className="px-6 py-4 border-b border-slate-100">
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
      )}

      {/* ── Footer: actions + collapsible methodology ────────────────────── */}
      <div className="px-6 py-3 bg-slate-50 flex items-center gap-3 flex-wrap">
        <button
          type="button"
          onClick={handleShare}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-blue-600 px-3 py-1.5 bg-white border border-slate-200 rounded-md hover:border-blue-300 transition-colors"
        >
          <span aria-hidden>↗</span> {shareLabel}
        </button>
        <button
          type="button"
          onClick={() => setShowDetails(v => !v)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 hover:bg-white rounded-md transition-colors"
        >
          <span aria-hidden className={`transition-transform ${showDetails ? 'rotate-90' : ''}`}>▶</span>
          Details
        </button>
        {result.rate_limit && dailyLimit !== null && (
          <p className="text-xs text-slate-400 font-mono-vg ml-auto">
            {result.rate_limit.remaining} verification{result.rate_limit.remaining !== 1 ? 's' : ''} remaining today
          </p>
        )}
      </div>
      {showDetails && (
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200">
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[0.7rem] font-mono-vg">
            <div>
              <dt className="text-slate-400 uppercase tracking-wider mb-0.5">Model</dt>
              <dd className="text-slate-600">{shortModelName(result.model_used)}</dd>
            </div>
            <div>
              <dt className="text-slate-400 uppercase tracking-wider mb-0.5">Latency</dt>
              <dd className="text-slate-600">{result.processing_ms > 0 ? `${(result.processing_ms / 1000).toFixed(1)}s` : '—'}</dd>
            </div>
            <div>
              <dt className="text-slate-400 uppercase tracking-wider mb-0.5">Search</dt>
              <dd className="text-slate-600">{result.search_method}{result.web_search ? ' + web' : ''}</dd>
            </div>
            <div>
              <dt className="text-slate-400 uppercase tracking-wider mb-0.5">Sources</dt>
              <dd className="text-slate-600">{result.sources.length}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  )
}
