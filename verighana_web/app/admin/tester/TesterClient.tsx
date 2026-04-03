'use client'

import { useState } from 'react'
import { testSiteAction } from './actions'

type DbUpdate = { action: 'inserted' | 'updated' | 'skipped' | 'error' | 'none'; source_name?: string; reason?: string }

type TestResult = {
  url: string
  status: string
  headline_count?: number
  sample_headlines?: string[]
  strategy?: string
  error?: string
  elapsed_ms?: number
  db_update?: DbUpdate
  challenge_detected?: boolean
}

interface Props {
  sites: string[]
}

export function TesterClient({ sites }: Props) {
  const [customUrl, setCustomUrl]   = useState('')
  const [loading, setLoading]       = useState(false)
  const [result, setResult]         = useState<TestResult | null>(null)
  const [batchResults, setBatch]    = useState<TestResult[]>([])
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchDone, setBatchDone]   = useState(0)

  async function testSingle(url: string) {
    if (!url.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const data = await testSiteAction(url.trim()) as TestResult
      setResult(data)
    } catch (err: unknown) {
      setResult({ url: url.trim(), status: 'error', error: (err as Error).message })
    } finally {
      setLoading(false)
    }
  }

  async function runBatch() {
    if (sites.length === 0) return
    setBatchRunning(true)
    setBatch([])
    setBatchDone(0)

    for (const url of sites) {
      try {
        const data = await testSiteAction(url) as TestResult
        setBatch(prev => [...prev, data])
      } catch (err: unknown) {
        setBatch(prev => [...prev, { url, status: 'error', error: (err as Error).message }])
      }
      setBatchDone(d => d + 1)
    }
    setBatchRunning(false)
  }

  const okCount    = batchResults.filter(r => r.status === 'ok').length
  const emptyCount = batchResults.filter(r => r.status === 'empty' || r.status === 'no_headlines').length
  const errCount   = batchResults.filter(r => r.status === 'error' || r.status === 'blocked' || r.status === 'challenge_blocked').length

  function statusStyle(status: string) {
    if (status === 'ok') return 'border-green-200 bg-green-50'
    if (status === 'no_headlines' || status === 'empty') return 'border-amber-200 bg-amber-50'
    return 'border-red-200 bg-red-50'
  }

  function statusTextStyle(status: string) {
    if (status === 'ok') return 'text-green-700'
    if (status === 'no_headlines' || status === 'empty') return 'text-amber-700'
    return 'text-red-600'
  }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Site Tester</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Test individual URLs or run the full {sites.length}-site batch to check scraper health.
        </p>
      </div>

      {/* Single URL tester */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Test Single URL</p>
        <div className="flex gap-3">
          <input
            type="url"
            value={customUrl}
            onChange={e => setCustomUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && testSingle(customUrl)}
            placeholder="https://www.ghanaweb.com"
            className="flex-1 bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2.5 rounded-lg outline-none focus:border-blue-400 transition-colors font-mono-vg"
          />
          <button
            type="button"
            onClick={() => testSingle(customUrl)}
            disabled={loading || !customUrl.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
          >
            {loading ? 'Testing…' : 'Test →'}
          </button>
        </div>

        {result && (
          <div className={`border rounded-xl p-4 ${statusStyle(result.status)}`}>
            <div className="flex items-center justify-between mb-2">
              <span className={`text-xs font-mono-vg font-semibold ${statusTextStyle(result.status)}`}>
                {result.status.toUpperCase().replace('_', ' ')}
                {result.headline_count !== undefined && ` · ${result.headline_count} headlines`}
                {result.strategy && ` · ${result.strategy}`}
                {result.elapsed_ms !== undefined && ` · ${(result.elapsed_ms / 1000).toFixed(1)}s`}
              </span>
              <span className="text-xs text-slate-400 font-mono-vg truncate max-w-[240px]">{result.url}</span>
            </div>
            {result.challenge_detected && (
              <p className="text-xs text-amber-600 font-mono-vg mb-2">Bot challenge detected (Akamai/Cloudflare). VeriGhana-Bot identity was attempted.</p>
            )}
            {result.error && (
              <p className="text-xs text-red-600 font-mono-vg">{result.error}</p>
            )}
            {result.sample_headlines && result.sample_headlines.length > 0 && (
              <ul className="mt-2 space-y-1">
                {result.sample_headlines.slice(0, 3).map((h, i) => (
                  <li key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                    {h}
                  </li>
                ))}
              </ul>
            )}
            {result.db_update && result.db_update.action !== 'none' && (
              <div className={`mt-3 text-[10px] font-mono-vg px-2.5 py-1.5 rounded-lg inline-flex items-center gap-1.5
                ${result.db_update.action === 'inserted' ? 'bg-green-100 text-green-700' :
                  result.db_update.action === 'updated'  ? 'bg-blue-100 text-blue-700' :
                  result.db_update.action === 'error'    ? 'bg-red-100 text-red-600' :
                  'bg-slate-100 text-slate-500'}`}>
                {result.db_update.action === 'inserted' && '+ Added to trusted sources'}
                {result.db_update.action === 'updated'  && `Updated source: ${result.db_update.source_name ?? ''}`}
                {result.db_update.action === 'skipped'  && `Skipped: ${result.db_update.reason ?? ''}`}
                {result.db_update.action === 'error'    && `DB error: ${result.db_update.reason ?? ''}`}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Batch tester */}
      {sites.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">
              Batch Test ({sites.length} sites)
            </p>
            <button
              type="button"
              onClick={runBatch}
              disabled={batchRunning}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-medium px-4 py-2 rounded-lg transition-colors"
            >
              {batchRunning ? `Testing… ${batchDone}/${sites.length}` : 'Run All →'}
            </button>
          </div>

          {batchRunning && (
            <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-500 transition-all duration-300"
                style={{ width: `${Math.round((batchDone / sites.length) * 100)}%` }}
              />
            </div>
          )}

          {batchResults.length > 0 && (
            <>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'OK',    value: okCount,    color: 'text-green-600' },
                  { label: 'Empty', value: emptyCount, color: 'text-amber-600' },
                  { label: 'Error', value: errCount,   color: 'text-red-600' },
                ].map(s => (
                  <div key={s.label} className="bg-slate-50 rounded-lg px-3 py-2.5 text-center">
                    <div className={`font-display font-bold text-xl ${s.color}`}>{s.value}</div>
                    <div className="text-xs text-slate-400">{s.label}</div>
                  </div>
                ))}
              </div>

              <div className="space-y-1.5 max-h-96 overflow-y-auto">
                {batchResults.map((r, i) => (
                  <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono-vg ${
                    r.status === 'ok' ? 'bg-green-50 text-green-700' :
                    r.status === 'no_headlines' || r.status === 'empty' ? 'bg-amber-50 text-amber-700' :
                    'bg-red-50 text-red-600'
                  }`}>
                    <span className="truncate flex-1">{r.url}</span>
                    <span className="shrink-0 ml-3">
                      {r.status === 'ok' ? `✓ ${r.headline_count ?? ''}` :
                       r.status === 'challenge_blocked' ? '🛡️' :
                       r.status === 'no_headlines' ? '⚠ empty' : '✗'}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
