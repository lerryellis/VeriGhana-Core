'use client'

import { useState, useMemo } from 'react'
import type { FeedbackRow } from './page'

interface Props { rows: FeedbackRow[] }

const ROLE_LABELS: Record<string, string> = {
  researcher: 'Researcher', journalist: 'Journalist', student: 'Student',
  developer: 'Developer', educator: 'Educator', general: 'General Public',
}

const FREQ_LABELS: Record<string, string> = {
  daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly',
  occasionally: 'Occasionally', first_time: 'First time',
}

function avg(vals: (number | null)[]): number | null {
  const filtered = vals.filter((v): v is number => v !== null)
  if (!filtered.length) return null
  return filtered.reduce((a, b) => a + b, 0) / filtered.length
}

function StarDisplay({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-300 text-xs font-mono-vg">—</span>
  const filled = Math.round(value)
  return (
    <span className="text-amber-400 text-sm" title={`${value.toFixed(1)}/5`}>
      {'★'.repeat(filled)}{'☆'.repeat(5 - filled)}
    </span>
  )
}

function NpsBar({ rows }: { rows: FeedbackRow[] }) {
  const scores = rows.map(r => r.nps_score).filter((s): s is number => s !== null)
  if (!scores.length) return <p className="text-slate-400 text-sm">No NPS data yet.</p>
  const detractors = scores.filter(s => s <= 6).length
  const passives   = scores.filter(s => s === 7 || s === 8).length
  const promoters  = scores.filter(s => s >= 9).length
  const nps        = Math.round(((promoters - detractors) / scores.length) * 100)
  const pct = (n: number) => Math.round((n / scores.length) * 100)
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <div className="text-center">
          <p className={`text-3xl font-display font-extrabold ${nps >= 50 ? 'text-green-600' : nps >= 0 ? 'text-amber-500' : 'text-red-500'}`}>{nps}</p>
          <p className="text-xs text-slate-400 font-mono-vg">NPS Score</p>
        </div>
        <div className="flex-1 space-y-1.5">
          {[
            { label: 'Promoters (9–10)', count: promoters, color: 'bg-green-400' },
            { label: 'Passives (7–8)',   count: passives,  color: 'bg-amber-300' },
            { label: 'Detractors (0–6)', count: detractors, color: 'bg-red-400' },
          ].map(({ label, count, color }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="text-xs text-slate-500 w-32 shrink-0">{label}</span>
              <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                <div className={`${color} h-full rounded-full transition-all`} style={{ width: `${pct(count)}%` }} />
              </div>
              <span className="text-xs text-slate-500 font-mono-vg w-8 text-right">{pct(count)}%</span>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-400 font-mono-vg">Based on {scores.length} response{scores.length !== 1 ? 's' : ''}</p>
    </div>
  )
}

function toCSV(rows: FeedbackRow[]): string {
  const headers = [
    'Date', 'Email', 'Tier', 'Role', 'Frequency', 'Use Case',
    'NPS', 'Accuracy', 'Usability', 'Speed', 'Reliability', 'Value',
    'Easy to Use', 'Trust Results', 'Improves Work', 'Recommend',
    'Most Useful', 'Biggest Challenge', 'Feature Request', 'General Comments',
  ]
  const lines = rows.map(r => [
    r.created_at.slice(0, 10), r.user_email ?? '', r.user_tier ?? '',
    r.respondent_role ?? '', r.use_frequency ?? '', r.use_case ?? '',
    r.nps_score ?? '', r.rating_accuracy ?? '', r.rating_usability ?? '',
    r.rating_speed ?? '', r.rating_reliability ?? '', r.rating_value ?? '',
    r.likert_easy_to_use ?? '', r.likert_trust_results ?? '',
    r.likert_improves_work ?? '', r.likert_recommend ?? '',
    r.most_useful ?? '', r.biggest_challenge ?? '',
    r.feature_request ?? '', r.general_comments ?? '',
  ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
  return [headers.join(','), ...lines].join('\n')
}

function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}

export function FeedbackAdminClient({ rows }: Props) {
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const filtered = useMemo(() => rows.filter(r => {
    if (roleFilter !== 'all' && r.respondent_role !== roleFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return (r.user_email ?? '').toLowerCase().includes(q)
        || (r.most_useful ?? '').toLowerCase().includes(q)
        || (r.biggest_challenge ?? '').toLowerCase().includes(q)
        || (r.feature_request ?? '').toLowerCase().includes(q)
    }
    return true
  }), [rows, search, roleFilter])

  const avgNps       = avg(rows.map(r => r.nps_score))
  const avgAccuracy  = avg(rows.map(r => r.rating_accuracy))
  const avgUsability = avg(rows.map(r => r.rating_usability))
  const avgValue     = avg(rows.map(r => r.rating_value))

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-[#0f2240]">Feedback</h1>
          <p className="text-sm text-slate-500 mt-0.5">{rows.length} response{rows.length !== 1 ? 's' : ''} collected</p>
        </div>
        <button
          type="button"
          onClick={() => downloadCSV(toCSV(rows), `verighana-feedback-${new Date().toISOString().slice(0,10)}.csv`)}
          className="text-sm bg-[#0f2240] hover:bg-[#1a3560] text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
        >
          ↓ Export CSV
        </button>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Responses',     value: rows.length.toString(),                        color: 'text-[#0f2240]' },
          { label: 'Avg NPS',       value: avgNps !== null ? avgNps.toFixed(1) : '—',     color: 'text-blue-600' },
          { label: 'Avg Accuracy',  value: avgAccuracy !== null ? `${avgAccuracy.toFixed(1)}/5` : '—', color: 'text-green-600' },
          { label: 'Avg Usability', value: avgUsability !== null ? `${avgUsability.toFixed(1)}/5` : '—', color: 'text-teal-600' },
        ].map(k => (
          <div key={k.label} className="bg-white border border-slate-200 rounded-xl p-4">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1">{k.label}</p>
            <p className={`text-2xl font-display font-extrabold ${k.color}`}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* NPS distribution */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Net Promoter Score</p>
        <NpsBar rows={rows} />
      </div>

      {/* Rating averages */}
      {rows.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Average Ratings</p>
          <div className="space-y-3">
            {[
              { label: 'Accuracy',    val: avg(rows.map(r => r.rating_accuracy)) },
              { label: 'Usability',   val: avg(rows.map(r => r.rating_usability)) },
              { label: 'Speed',       val: avg(rows.map(r => r.rating_speed)) },
              { label: 'Reliability', val: avg(rows.map(r => r.rating_reliability)) },
              { label: 'Value',       val: avg(rows.map(r => r.rating_value)) },
            ].map(({ label, val }) => (
              <div key={label} className="flex items-center gap-3">
                <span className="text-sm text-slate-600 w-24 shrink-0">{label}</span>
                <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div className="bg-amber-400 h-full rounded-full transition-all" style={{ width: val !== null ? `${(val / 5) * 100}%` : '0%' }} />
                </div>
                <span className="text-xs font-mono-vg text-slate-500 w-8 text-right">{val !== null ? val.toFixed(1) : '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap gap-3">
        <input
          type="search"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search responses…"
          aria-label="Search feedback"
          className="flex-1 min-w-[200px] bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
        />
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          aria-label="Filter by role"
          className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
        >
          <option value="all">All roles</option>
          {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <p className="text-xs text-slate-400 self-center font-mono-vg">{filtered.length} shown</p>
      </div>

      {/* Response table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-0 border-b border-slate-100 px-4 py-2 text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest">
          <span>Respondent</span>
          <span className="px-3">NPS</span>
          <span className="px-3">Accuracy</span>
          <span className="px-3">Value</span>
          <span className="px-3">Date</span>
        </div>

        {filtered.length === 0 && (
          <p className="text-sm text-slate-400 text-center py-10">No responses yet.</p>
        )}

        {filtered.map(r => (
          <div key={r.id} className="border-b border-slate-100 last:border-0">
            <button
              type="button"
              onClick={() => setExpanded(prev => prev === r.id ? null : r.id)}
              className="w-full grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-0 px-4 py-3 hover:bg-slate-50 transition-colors text-left"
            >
              <div>
                <p className="text-sm font-medium text-[#0f2240] truncate">{r.user_email ?? 'Anonymous'}</p>
                <p className="text-xs text-slate-400 font-mono-vg">
                  {r.respondent_role ? ROLE_LABELS[r.respondent_role] ?? r.respondent_role : '—'}
                  {r.use_frequency ? ` · ${FREQ_LABELS[r.use_frequency] ?? r.use_frequency}` : ''}
                </p>
              </div>
              <span className="px-3 text-sm font-mono-vg font-bold text-center" style={{
                color: r.nps_score === null ? '#94a3b8' : r.nps_score <= 6 ? '#ef4444' : r.nps_score <= 8 ? '#f59e0b' : '#22c55e'
              }}>
                {r.nps_score ?? '—'}
              </span>
              <span className="px-3"><StarDisplay value={r.rating_accuracy} /></span>
              <span className="px-3"><StarDisplay value={r.rating_value} /></span>
              <span className="px-3 text-xs text-slate-400 font-mono-vg whitespace-nowrap">
                {new Date(r.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
              </span>
            </button>

            {expanded === r.id && (
              <div className="px-4 pb-4 space-y-4 bg-slate-50/50">
                {/* All ratings */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-2">
                  {[
                    { label: 'Accuracy',    val: r.rating_accuracy },
                    { label: 'Usability',   val: r.rating_usability },
                    { label: 'Speed',       val: r.rating_speed },
                    { label: 'Reliability', val: r.rating_reliability },
                    { label: 'Value',       val: r.rating_value },
                  ].map(({ label, val }) => (
                    <div key={label} className="bg-white border border-slate-200 rounded-lg p-2 text-center">
                      <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase mb-1">{label}</p>
                      <StarDisplay value={val} />
                    </div>
                  ))}
                </div>

                {/* Likert */}
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: 'Easy to use',    val: r.likert_easy_to_use },
                    { label: 'Trusts results', val: r.likert_trust_results },
                    { label: 'Improves work',  val: r.likert_improves_work },
                    { label: 'Would recommend', val: r.likert_recommend },
                  ].map(({ label, val }) => (
                    <div key={label} className="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2">
                      <span className="text-xs text-slate-500">{label}</span>
                      <span className="text-xs font-mono-vg font-bold text-[#0f2240]">
                        {val !== null ? ['SD','D','N','A','SA'][val - 1] ?? val : '—'}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Qualitative */}
                {[
                  { label: 'Most Useful',       text: r.most_useful },
                  { label: 'Biggest Challenge', text: r.biggest_challenge },
                  { label: 'Feature Request',   text: r.feature_request },
                  { label: 'General Comments',  text: r.general_comments },
                ].filter(q => q.text).map(({ label, text }) => (
                  <div key={label} className="bg-white border border-slate-200 rounded-lg px-3 py-2.5">
                    <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-1">{label}</p>
                    <p className="text-sm text-slate-700 leading-relaxed">{text}</p>
                  </div>
                ))}

                {r.use_case && (
                  <div className="bg-white border border-slate-200 rounded-lg px-3 py-2.5">
                    <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-1">Use Case</p>
                    <p className="text-sm text-slate-700">{r.use_case}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
