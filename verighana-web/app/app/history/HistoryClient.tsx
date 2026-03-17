'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { VerificationRecord } from './page'
import { VerdictChip } from '@/components/ui/VerdictChip'
import { TruthBar } from '@/components/ui/TruthBar'

type Verdict = 'VERIFIED' | 'PARTIAL' | 'FALSE' | 'UNCORROBORATED'


interface Props {
  records: VerificationRecord[]
  stats: { total: number; verified: number; falseCount: number; partial: number; avgScore: number }
}

const FILTER_OPTIONS = ['All', 'VERIFIED', 'PARTIAL', 'FALSE', 'UNCORROBORATED'] as const

export function HistoryClient({ records, stats }: Props) {
  const [filter, setFilter]     = useState<string>('All')
  const [search, setSearch]     = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)

  const filtered = records.filter(r => {
    const matchVerdict = filter === 'All' || r.verdict === filter
    const matchSearch  = !search || r.input_claim.toLowerCase().includes(search.toLowerCase())
    return matchVerdict && matchSearch
  })

  if (records.length === 0) {
    return (
      <div className="max-w-2xl mx-auto space-y-5">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Verification History</h1>
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center">
          <div className="text-4xl mb-3">🔍</div>
          <p className="font-display font-bold text-[#0f2240] mb-1">No verifications yet</p>
          <p className="text-sm text-slate-400 mb-4">Your fact-checking history will appear here.</p>
          <Link href="/app/verify" className="inline-block bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors">
            Start Verifying →
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Verification History</h1>
        <Link href="/app/verify" className="text-sm text-blue-600 hover:text-blue-700 font-medium">+ New Verification</Link>
      </div>

      {/* KPI pills */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total',    value: stats.total,      color: 'text-[#0f2240]' },
          { label: 'Verified', value: stats.verified,   color: 'text-green-600' },
          { label: 'False',    value: stats.falseCount, color: 'text-red-500' },
          { label: 'Avg Score', value: `${stats.avgScore}%`, color: 'text-blue-600' },
        ].map(k => (
          <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-3 text-center">
            <div className={`font-display text-2xl font-bold ${k.color}`}>{k.value}</div>
            <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap gap-3 items-center">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search claims…"
          className="flex-1 min-w-[160px] bg-slate-50 border border-slate-200 text-sm text-slate-700 px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
        />
        <div className="flex gap-1.5 flex-wrap">
          {FILTER_OPTIONS.map(f => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                filter === f
                  ? 'bg-blue-600 border-blue-600 text-white'
                  : 'border-slate-200 text-slate-500 hover:border-slate-400'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Count */}
      {filtered.length !== records.length && (
        <p className="text-xs text-slate-400 font-mono-vg">
          Showing {filtered.length} of {records.length} verifications
        </p>
      )}

      {/* Records */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400 text-sm">
            No results match your filter.
          </div>
        ) : (
          filtered.map(record => (
            <HistoryRow
              key={record.id}
              record={record}
              isExpanded={expanded === record.id}
              onToggle={() => setExpanded(expanded === record.id ? null : record.id)}
            />
          ))
        )}
      </div>
    </div>
  )
}

function HistoryRow({
  record, isExpanded, onToggle,
}: {
  record: VerificationRecord
  isExpanded: boolean
  onToggle: () => void
}) {
  const sources = (() => {
    try { return record.matched_sources ? JSON.parse(record.matched_sources) : [] }
    catch { return [] }
  })()

  const validVerdict = ['VERIFIED', 'PARTIAL', 'FALSE', 'UNCORROBORATED'].includes(record.verdict)
    ? record.verdict as Verdict
    : 'UNCORROBORATED'

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      {/* Row header — always visible */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left px-5 py-4 flex items-start gap-4 hover:bg-slate-50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-800 font-medium line-clamp-2 mb-2">{record.input_claim}</p>
          <div className="flex items-center gap-3 flex-wrap">
            <VerdictChip verdict={validVerdict} />
            <span className="font-display font-bold text-lg text-[#0f2240]">{record.score}%</span>
            <span className="text-xs text-slate-400 font-mono-vg">
              {new Date(record.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
            {record.model_used && (
              <span className="text-xs text-slate-400 font-mono-vg">{record.model_used}</span>
            )}
          </div>
        </div>
        <span className="text-slate-400 text-xs mt-1 shrink-0">{isExpanded ? '▲' : '▼'}</span>
      </button>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="border-t border-slate-100 px-5 py-4 space-y-4">
          <div className="w-full">
            <TruthBar score={record.score} />
          </div>

          {record.explanation && (
            <div>
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1.5">AI Analysis</p>
              <p className="text-sm text-slate-600 leading-relaxed">{record.explanation}</p>
            </div>
          )}

          {sources.length > 0 && (
            <div>
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-2">Sources</p>
              <div className="space-y-1.5">
                {sources.map((s: { title: string; url?: string; source: string }, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1 shrink-0" />
                    <div>
                      {s.url && s.url !== '#'
                        ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{s.title}</a>
                        : <span>{s.title}</span>
                      }
                      <span className="text-slate-400"> — {s.source}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
