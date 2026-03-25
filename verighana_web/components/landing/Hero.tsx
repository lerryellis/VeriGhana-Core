'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import type { VerifyResponse as ApiVerifyResponse } from '@/types/api'

type Verdict = ApiVerifyResponse['verdict'] | 'CHECKING'
type VerifyResponse = Omit<ApiVerifyResponse, 'verdict'> & { verdict: Verdict }

const DEMO_DATA: (VerifyResponse & { claim: string })[] = [
  {
    claim: 'EC postpones 2026 Accra by-election',
    verdict: 'UNCORROBORATED', score: 8,
    explanation: 'No matching story found in any indexed source from Citi Newsroom, Joy Online, or EC official communications.',
    sources: [], model_used: 'demo', processing_ms: 0, search_method: 'demo',
  },
  {
    claim: 'Free SHS programme officially cancelled',
    verdict: 'FALSE', score: 5,
    explanation: 'Multiple credible sources directly contradict this claim. Ministry of Education has confirmed the programme continues.',
    sources: [{ title: 'Ministry of Education confirms Free SHS continuation', url: '#', source: 'Ministry of Education' }],
    model_used: 'demo', processing_ms: 0, search_method: 'demo',
  },
  {
    claim: 'Bank of Ghana cuts interest rate to 27%',
    verdict: 'VERIFIED', score: 81,
    explanation: "The Bank of Ghana's Monetary Policy Committee statement confirms this rate adjustment in their latest release.",
    sources: [{ title: 'Monetary Policy Statement — February 2026', url: '#', source: 'Bank of Ghana' }],
    model_used: 'demo', processing_ms: 0, search_method: 'demo',
  },
  {
    claim: 'Ghana Statistical Service releases 2024 census data',
    verdict: 'VERIFIED', score: 91,
    explanation: 'Ghana Statistical Service officially published the 2024 Population and Housing Census report on their portal.',
    sources: [{ title: '2024 Population & Housing Census — Final Results', url: '#', source: 'Ghana Statistical Service' }],
    model_used: 'demo', processing_ms: 0, search_method: 'demo',
  },
]

const VERDICT_GRADIENT: Record<string, string> = {
  VERIFIED:       'linear-gradient(90deg,#16a34a,#4ade80)',
  PARTIAL:        'linear-gradient(90deg,#d97706,#fbbf24)',
  FALSE:          'linear-gradient(90deg,#dc2626,#f87171)',
  UNCORROBORATED: 'linear-gradient(90deg,#475569,#94a3b8)',
  CHECKING:       'linear-gradient(90deg,#2563eb,#60a5fa)',
  ERROR:          'linear-gradient(90deg,#dc2626,#f87171)',
}

const VERDICT_TEXT: Record<string, string> = {
  VERIFIED: 'text-green-400', PARTIAL: 'text-amber-400',
  FALSE: 'text-red-400', UNCORROBORATED: 'text-slate-400',
  CHECKING: 'text-blue-400', ERROR: 'text-red-400',
}

type ResultState = VerifyResponse & { barWidth: number }

export function Hero({ models }: { models: { id: string; name: string }[] }) {
  const router = useRouter()
  const [claim, setClaim] = useState('')
  const [selectedModel, setSelectedModel] = useState(models[0]?.id ?? 'gemini-2.0-flash')
  const [loading, setLoading] = useState(false)
  const [apiOffline, setApiOffline] = useState(false)
  const [result, setResult] = useState<ResultState | null>(null)
  const demoIdx = useRef(0)
  const cycleRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const showResult = useCallback((r: VerifyResponse) => {
    setResult({ ...r, barWidth: 0 })
    setTimeout(() => setResult(prev => prev ? { ...prev, barWidth: r.score } : prev), 80)
  }, [])

  const runDemo = useCallback(() => {
    const d = DEMO_DATA[demoIdx.current % DEMO_DATA.length]
    demoIdx.current++
    setClaim(d.claim)
    showResult(d)
  }, [showResult])

  const startCycle = useCallback(() => {
    cycleRef.current = setInterval(() => {
      if (document.activeElement !== inputRef.current && !claim.trim()) {
        runDemo()
      }
    }, 4500)
  }, [claim, runDemo])

  useEffect(() => {
    const t = setTimeout(() => { runDemo(); startCycle() }, 900)
    return () => { clearTimeout(t); if (cycleRef.current) clearInterval(cycleRef.current) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function verify() {
    const input = claim.trim()
    if (!input) { runDemo(); return }

    if (cycleRef.current) clearInterval(cycleRef.current)
    setLoading(true)
    setApiOffline(false)
    setResult({ verdict: 'CHECKING', score: 100, explanation: 'Searching across indexed Ghanaian sources…', sources: [], model_used: '—', processing_ms: 0, search_method: '—', barWidth: 100 })

    try {
      const data = await api.verify({ claim: input, model: selectedModel }, '')
      showResult(data)
    } catch (err: unknown) {
      const isNetworkError = err instanceof TypeError || (err as { status?: number })?.status === undefined
      if (isNetworkError) {
        setApiOffline(true)
        showResult({ verdict: 'UNCORROBORATED', score: 8, explanation: 'API offline — showing demo result. Start the backend to get real results.', sources: [], model_used: '—', processing_ms: 0, search_method: '—' })
      } else {
        showResult({ verdict: 'ERROR', score: 0, explanation: `Error: ${(err as { detail?: string })?.detail ?? 'Unknown error'}`, sources: [], model_used: '—', processing_ms: 0, search_method: '—' })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="relative overflow-hidden py-20 px-[5%] text-center" style={{ background: 'linear-gradient(160deg,#0f2240 0%,#0c1e3f 55%,#112244 100%)' }}>
      {/* Grid overlay */}
      <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: 'linear-gradient(rgba(37,99,235,0.07) 1px,transparent 1px),linear-gradient(90deg,rgba(37,99,235,0.07) 1px,transparent 1px)', backgroundSize: '48px 48px', maskImage: 'radial-gradient(ellipse at 50% 0%,black 40%,transparent 75%)' }} />
      {/* Glow */}
      <div className="absolute pointer-events-none" style={{ width: 600, height: 600, background: 'radial-gradient(circle,rgba(37,99,235,0.18) 0%,transparent 70%)', top: -200, right: -150 }} />

      <div className="relative z-10 max-w-2xl mx-auto">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 bg-blue-600/15 border border-blue-400/30 text-blue-300 text-xs font-medium tracking-widest uppercase px-4 py-1.5 rounded-full mb-6 animate-fade-up">
          🇬🇭 Ghana&apos;s AI-Powered Fact Verification
        </div>

        <h1 className="font-display font-extrabold text-4xl md:text-5xl text-white leading-tight tracking-tight mb-4 animate-fade-up" style={{ animationDelay: '0.1s' }}>
          Fighting <em className="not-italic text-blue-400">Misinformation</em><br />in Ghana with AI
        </h1>

        <p className="text-slate-400 font-light text-base leading-relaxed max-w-md mx-auto mb-8 animate-fade-up" style={{ animationDelay: '0.2s' }}>
          Submit any social media claim — get an instant Truth Score backed by verified Ghanaian sources, updated every 6 hours.
        </p>

        {/* Model selector */}
        <div className="flex justify-center items-center gap-2 mb-3 animate-fade-up" style={{ animationDelay: '0.25s' }}>
          <span className="text-[0.72rem] text-slate-500 font-mono-vg tracking-wider">MODEL:</span>
          <select
            aria-label="AI model selection"
            value={selectedModel}
            onChange={e => setSelectedModel(e.target.value)}
            className="bg-white/[0.07] border border-white/15 text-blue-300 font-mono-vg text-[0.72rem] px-2.5 py-1 rounded-md outline-none cursor-pointer"
          >
            {models.map(m => (
              <option key={m.id} value={m.id} style={{ background: '#1a3560' }}>{m.name ?? m.id}</option>
            ))}
          </select>
        </div>

        {/* Search bar */}
        <div className="flex rounded-xl overflow-hidden border border-white/[0.14] bg-white/[0.06] mb-3 animate-fade-up" style={{ animationDelay: '0.3s' }}>
          <input
            ref={inputRef}
            type="text"
            value={claim}
            onChange={e => setClaim(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && verify()}
            onFocus={() => { if (cycleRef.current) clearInterval(cycleRef.current) }}
            onBlur={() => { if (!claim.trim()) startCycle() }}
            placeholder="Paste a suspicious claim, social post, or rumour here…"
            className="flex-1 bg-transparent text-white placeholder:text-slate-500 text-sm px-4 py-3.5 outline-none"
          />
          <button
            type="button"
            onClick={() => router.push('/register')}
            className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-5 flex items-center gap-2 transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6.5 12a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11zM14 14l-3-3" />
            </svg>
            Check Now
          </button>
        </div>

        {/* API offline notice */}
        {apiOffline && (
          <div className="text-amber-400/80 text-xs bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2 mb-3">
            ⚠ API server not reachable — start it with <code className="font-mono-vg">uvicorn src.api:app --reload --port 8000</code>
          </div>
        )}

        {/* Truth meter */}
        {result && (
          <div className="glass-card p-5 text-left mt-4 animate-fade-in">
            <div className="flex items-center justify-between mb-3">
              <span className="flex items-center gap-2 text-xs text-slate-400 font-mono-vg tracking-widest uppercase">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                Truth Meter
              </span>
              <span className={`text-xs font-bold font-mono-vg tracking-widest ${VERDICT_TEXT[result.verdict] ?? 'text-slate-400'}`}>
                {result.verdict}
              </span>
            </div>

            <div className="flex items-center gap-3 mb-3">
              <span className="font-display text-2xl font-bold text-white w-12 text-right">
                {result.verdict === 'CHECKING' ? '…' : `${result.score}%`}
              </span>
              <div className="flex-1 h-2.5 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${result.barWidth}%`, background: VERDICT_GRADIENT[result.verdict] ?? VERDICT_GRADIENT.UNCORROBORATED }}
                />
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed mb-3">{result.explanation}</p>

            {result.sources.length > 0 && (
              <div className="border-t border-white/[0.08] pt-3 space-y-2">
                <p className="text-[0.68rem] text-slate-500 font-mono-vg uppercase tracking-widest">Sources</p>
                {result.sources.slice(0, 4).map((s, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 shrink-0" />
                    <div>
                      {s.url && s.url !== '#'
                        ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">{s.title}</a>
                        : <span>{s.title}</span>
                      }
                      <span className="text-slate-500"> — {s.source}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-between mt-3 text-[0.68rem] font-mono-vg text-slate-600">
              <span>{result.processing_ms > 0 ? `${(result.processing_ms / 1000).toFixed(1)}s · ${result.search_method}` : 'Demo mode'}</span>
              <span>{result.model_used !== 'demo' && result.model_used !== '—' ? result.model_used : '—'}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
