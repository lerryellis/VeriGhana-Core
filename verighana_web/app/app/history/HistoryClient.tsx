'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import type { VerificationRecord } from './page'
import { VerdictChip } from '@/components/ui/VerdictChip'
import { TruthBar } from '@/components/ui/TruthBar'
import { createClient } from '@/lib/supabase/client'

type Verdict = 'VERIFIED' | 'PARTIAL' | 'FALSE' | 'UNCORROBORATED'
type Source  = { title: string; url?: string; source?: string; category?: string }

const FILTER_OPTIONS = ['All', 'VERIFIED', 'PARTIAL', 'FALSE', 'UNCORROBORATED'] as const

interface Props {
  records: VerificationRecord[]
}

function computeStats(records: VerificationRecord[]) {
  return {
    total:      records.length,
    verified:   records.filter(r => r.verdict === 'VERIFIED').length,
    falseCount: records.filter(r => r.verdict === 'FALSE').length,
    partial:    records.filter(r => r.verdict === 'PARTIAL').length,
    avgScore:   records.length > 0
      ? Math.round(records.reduce((s, r) => s + (r.score ?? 0), 0) / records.length)
      : 0,
  }
}

export function HistoryClient({ records: initial }: Props) {
  const router = useRouter()
  const [records, setRecords] = useState(initial)
  const [filter, setFilter]   = useState<string>('All')
  const [search, setSearch]   = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [editingId, setEditingId]   = useState<number | null>(null)
  const [editText, setEditText]     = useState('')

  const stats    = computeStats(records)
  const filtered = records.filter(r => {
    const matchVerdict = filter === 'All' || r.verdict === filter
    const matchSearch  = !search || r.input_claim.toLowerCase().includes(search.toLowerCase())
    return matchVerdict && matchSearch
  })

  async function handleDelete(id: number) {
    setDeletingId(id)
    try {
      const supabase = createClient()
      await supabase.from('verification_log').delete().eq('id', id)
      setRecords(prev => prev.filter(r => r.id !== id))
      if (expanded === id) setExpanded(null)
      if (editingId === id) { setEditingId(null); setEditText('') }
    } finally {
      setDeletingId(null)
    }
  }

  function handleEditStart(record: VerificationRecord) {
    setEditingId(record.id)
    setEditText(record.input_claim)
    setExpanded(null)
  }

  function handleEditCancel() {
    setEditingId(null)
    setEditText('')
  }

  function handleRecheck(claim: string) {
    router.push(`/app/verify?claim=${encodeURIComponent(claim)}`)
  }

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
        <Link href="/app/verify" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
          + New Verification
        </Link>
      </div>

      {/* KPI pills */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total',     value: stats.total,                   color: 'text-[#0f2240]' },
          { label: 'Verified',  value: stats.verified,                color: 'text-green-600' },
          { label: 'False',     value: stats.falseCount,              color: 'text-red-500'   },
          { label: 'Avg Score', value: `${stats.avgScore}%`,          color: 'text-blue-600'  },
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
              isEditing={editingId === record.id}
              editText={editingId === record.id ? editText : ''}
              isDeleting={deletingId === record.id}
              onToggle={() => {
                if (editingId === record.id) return
                setExpanded(expanded === record.id ? null : record.id)
              }}
              onRecheck={() => handleRecheck(record.input_claim)}
              onEditStart={() => handleEditStart(record)}
              onEditChange={setEditText}
              onEditCancel={handleEditCancel}
              onEditRecheck={() => { handleEditCancel(); handleRecheck(editText) }}
              onDelete={() => handleDelete(record.id)}
            />
          ))
        )}
      </div>
    </div>
  )
}

interface RowProps {
  record:        VerificationRecord
  isExpanded:    boolean
  isEditing:     boolean
  editText:      string
  isDeleting:    boolean
  onToggle:      () => void
  onRecheck:     () => void
  onEditStart:   () => void
  onEditChange:  (v: string) => void
  onEditCancel:  () => void
  onEditRecheck: () => void
  onDelete:      () => void
}

function HistoryRow({
  record, isExpanded, isEditing, editText, isDeleting,
  onToggle, onRecheck, onEditStart, onEditChange, onEditCancel, onEditRecheck, onDelete,
}: RowProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  const sources: Source[] = (() => {
    try { return record.matched_sources ? JSON.parse(record.matched_sources) : [] }
    catch { return [] }
  })()

  const validVerdict = (['VERIFIED', 'PARTIAL', 'FALSE', 'UNCORROBORATED'] as const).includes(record.verdict as Verdict)
    ? record.verdict as Verdict
    : 'UNCORROBORATED'

  function handleDeleteClick() {
    if (confirmDelete) {
      onDelete()
      setConfirmDelete(false)
    } else {
      setConfirmDelete(true)
    }
  }

  // ── Edit mode ──────────────────────────────────────────────────────────────
  if (isEditing) {
    return (
      <div className="bg-white border border-blue-300 rounded-xl overflow-hidden">
        <div className="px-5 py-4 space-y-3">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Edit claim</p>
          <textarea
            value={editText}
            onChange={e => onEditChange(e.target.value)}
            rows={3}
            aria-label="Edit claim text"
            placeholder="Enter claim to verify…"
            className="w-full bg-slate-50 border border-slate-200 text-sm text-slate-800 px-3 py-2 rounded-lg outline-none focus:border-blue-400 resize-none transition-colors"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onEditRecheck}
              disabled={!editText.trim()}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-medium px-4 py-2 rounded-lg transition-colors"
            >
              Recheck edited claim →
            </button>
            <button
              type="button"
              onClick={onEditCancel}
              className="border border-slate-200 text-slate-500 hover:border-slate-400 text-xs font-medium px-4 py-2 rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Normal mode ────────────────────────────────────────────────────────────
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      {/* Row header */}
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
              {new Date(record.created_at).toLocaleDateString('en-GB', {
                day: 'numeric', month: 'short', year: 'numeric',
              })}
            </span>
            {record.model_used && (
              <span className="text-xs text-slate-400 font-mono-vg">{record.model_used}</span>
            )}
          </div>
        </div>
        <span className="text-slate-400 text-xs mt-1 shrink-0">{isExpanded ? '▲' : '▼'}</span>
      </button>

      {/* Action bar */}
      <div className="px-5 pb-3 flex items-center gap-2 border-t border-slate-50">
        <button
          type="button"
          onClick={onRecheck}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium py-1.5 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Recheck
        </button>
        <span className="text-slate-200">|</span>
        <button
          type="button"
          onClick={onEditStart}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 font-medium py-1.5 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Edit &amp; Recheck
        </button>
        <span className="text-slate-200">|</span>
        <button
          type="button"
          onClick={handleDeleteClick}
          onBlur={() => setTimeout(() => setConfirmDelete(false), 200)}
          disabled={isDeleting}
          className={`flex items-center gap-1.5 text-xs font-medium py-1.5 transition-colors ${
            confirmDelete ? 'text-red-600 font-semibold' : 'text-slate-400 hover:text-red-500'
          }`}
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          {isDeleting ? 'Deleting…' : confirmDelete ? 'Confirm delete?' : 'Delete'}
        </button>
      </div>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="border-t border-slate-100 px-5 py-4 space-y-4">
          {/* Score bar */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Confidence Score</p>
              <span className="font-display font-bold text-xl text-[#0f2240]">{record.score}%</span>
            </div>
            <TruthBar score={record.score} />
          </div>

          {/* AI Analysis */}
          {record.explanation && (
            <div>
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1.5">AI Analysis</p>
              <p className="text-sm text-slate-600 leading-relaxed">{record.explanation}</p>
            </div>
          )}

          {/* Sources found */}
          {sources.length > 0 && (
            <div>
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-2">
                Sources Found ({sources.length})
              </p>
              <div className="space-y-2">
                {sources.map((s, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs bg-slate-50 rounded-lg px-3 py-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 shrink-0" />
                    <div className="min-w-0">
                      {s.url && s.url !== '#' ? (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline font-medium line-clamp-1"
                        >
                          {s.title || s.url}
                        </a>
                      ) : (
                        <span className="text-slate-700 font-medium">{s.title || '—'}</span>
                      )}
                      <div className="flex items-center gap-2 mt-0.5 text-slate-400">
                        {s.source && <span>{s.source}</span>}
                        {s.category && (
                          <>
                            <span>·</span>
                            <span className="capitalize">{s.category}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {sources.length === 0 && !record.explanation && (
            <p className="text-sm text-slate-400 italic">No detail saved for this verification.</p>
          )}
        </div>
      )}
    </div>
  )
}
