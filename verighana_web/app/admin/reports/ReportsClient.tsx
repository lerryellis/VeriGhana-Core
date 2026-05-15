'use client'

import { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line,
} from 'recharts'
import type { Payment, Verification } from './page'
import { Pagination } from '@/components/ui/Pagination'

interface Props {
  payments:      Payment[]
  verifications: Verification[]
  apiUrl:        string
  adminKey:      string
}

const METHOD_LABELS: Record<string, string> = {
  card: 'Card', mtn_momo: 'MTN MoMo',
  vodafone_cash: 'Vodafone Cash', airteltigo_money: 'AirtelTigo',
}

// ── CSV helpers ─────────────────────────────────────────────────────────────
function csvField(v: unknown): string {
  return `"${String(v ?? '').replace(/"/g, '""')}"`
}
function toCSV<T>(rows: T[], headers: string[], pick: (r: T) => unknown[]): string {
  const lines = rows.map(r => pick(r).map(csvField).join(','))
  return [headers.join(','), ...lines].join('\n')
}
function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}

// ── Accuracy semantics (matches thesis §5.2 convention) ──────────────────────
// known_true   → VERIFIED or PARTIAL is acceptable
// known_false  → FALSE or PARTIAL is acceptable
// no_coverage  → UNCORROBORATED only
const ACCEPTABLE: Record<NonNullable<Verification['category']>, Set<string>> = {
  known_true:  new Set(['VERIFIED', 'PARTIAL']),
  known_false: new Set(['FALSE', 'PARTIAL']),
  no_coverage: new Set(['UNCORROBORATED']),
}
function isCorrect(v: Verification): boolean | null {
  if (!v.category) return null
  return ACCEPTABLE[v.category].has(v.verdict)
}

const PAGE_SIZE = 25

export function ReportsClient({ payments, verifications, apiUrl, adminKey }: Props) {
  const [tab, setTab] = useState<'sales' | 'queries'>('sales')

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Reports</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200">
        {([
          { id: 'sales',   label: `Sales (${payments.length})` },
          { id: 'queries', label: `Verifications (${verifications.length})` },
        ] as const).map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-blue-600 text-[#0f2240]'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'sales'
        ? <SalesTab payments={payments} />
        : <VerificationsTab verifications={verifications} apiUrl={apiUrl} adminKey={adminKey} />}
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════
//  SALES TAB
// ════════════════════════════════════════════════════════════════════════════
function SalesTab({ payments }: { payments: Payment[] }) {
  const today    = new Date().toISOString().slice(0, 10)
  const monthAgo = new Date(Date.now() - 30 * 86400_000).toISOString().slice(0, 10)

  const [dateFrom, setDateFrom] = useState(monthAgo)
  const [dateTo,   setDateTo]   = useState(today)
  const [planFilter, setPlanFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(1)

  const filtered = useMemo(() => {
    return payments.filter(p => {
      const d = p.created_at.slice(0, 10)
      if (dateFrom && d < dateFrom) return false
      if (dateTo   && d > dateTo)   return false
      if (planFilter   !== 'all' && p.plan_key  !== planFilter)   return false
      if (statusFilter !== 'all' && p.status    !== statusFilter) return false
      return true
    })
  }, [payments, dateFrom, dateTo, planFilter, statusFilter])

  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const succeeded = filtered.filter(p => p.status === 'succeeded')
  const revenue   = succeeded.reduce((s, p) => s + parseFloat(String(p.amount)), 0)
  const proCount  = succeeded.filter(p => p.plan_key === 'pro').length
  const instCount = succeeded.filter(p => p.plan_key === 'institutional').length

  const dailyMap = useMemo(() => {
    const map: Record<string, number> = {}
    succeeded.forEach(p => {
      const d = p.created_at.slice(0, 10)
      map[d] = (map[d] ?? 0) + parseFloat(String(p.amount))
    })
    return Object.entries(map).sort(([a],[b]) => a.localeCompare(b)).map(([date, amount]) => ({
      date: date.slice(5), amount: parseFloat(amount.toFixed(2)),
    }))
  }, [succeeded])

  const planData = [
    { name: 'Pro',           value: succeeded.filter(p => p.plan_key === 'pro').reduce((s,p) => s + parseFloat(String(p.amount)), 0) },
    { name: 'Institutional', value: succeeded.filter(p => p.plan_key === 'institutional').reduce((s,p) => s + parseFloat(String(p.amount)), 0) },
  ]
  const methodMap: Record<string, number> = {}
  succeeded.forEach(p => {
    const m = METHOD_LABELS[p.payment_method] ?? p.payment_method
    methodMap[m] = (methodMap[m] ?? 0) + parseFloat(String(p.amount))
  })
  const methodData = Object.entries(methodMap).map(([name, value]) => ({ name, value: parseFloat(value.toFixed(2)) }))

  function exportSalesCSV() {
    const csv = toCSV(
      filtered,
      ['Order Ref','Date','Name','Email','Plan','Amount','Currency','Method','Status','Country','Promo'],
      p => [
        p.order_ref, new Date(p.created_at).toISOString().slice(0,10),
        p.full_name, p.user_email, p.plan_key, p.amount, p.currency,
        p.payment_method, p.status, p.country, p.promo_code ?? '',
      ],
    )
    downloadCSV(csv, `verighana-sales-${dateFrom}-${dateTo}.csv`)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={exportSalesCSV}
          className="bg-[#0f2240] hover:bg-[#1a3a6e] text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors flex items-center gap-2"
        >
          ↓ Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">From</label>
          <input type="date" aria-label="From date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">To</label>
          <input type="date" aria-label="To date" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">Plan</label>
          <select aria-label="Plan filter" value={planFilter} onChange={e => { setPlanFilter(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400">
            <option value="all">All plans</option>
            <option value="pro">Pro</option>
            <option value="institutional">Institutional</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">Status</label>
          <select aria-label="Status filter" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400">
            <option value="all">All statuses</option>
            <option value="succeeded">Succeeded</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Revenue (GHS)', value: `₵${revenue.toFixed(2)}`, color: 'text-green-600' },
          { label: 'Transactions',  value: succeeded.length,         color: 'text-[#0f2240]' },
          { label: 'Pro Subs',      value: proCount,                 color: 'text-blue-600' },
          { label: 'Institutional', value: instCount,                color: 'text-purple-600' },
        ].map(k => (
          <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-3 text-center">
            <div className={`font-display text-2xl font-bold ${k.color}`}>{k.value}</div>
            <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      {dailyMap.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Daily Revenue (GHS)</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={dailyMap} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip formatter={(v) => [`₵${Number(v).toFixed(2)}`, 'Revenue']} />
              <Line type="monotone" dataKey="amount" stroke="#2563eb" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Revenue by Plan</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={planData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip formatter={(v) => [`₵${Number(v).toFixed(2)}`, 'Revenue']} />
              <Bar dataKey="value" fill="#3b82f6" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Revenue by Payment Method</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={methodData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip formatter={(v) => [`₵${Number(v).toFixed(2)}`, 'Revenue']} />
              <Bar dataKey="value" fill="#8b5cf6" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Payments table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Transactions ({filtered.length})</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                {['Date','Reference','Name / Email','Plan','Amount','Method','Status','Invoice'].map(h => (
                  <th key={h} className="text-left text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-wider px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.length === 0 ? (
                <tr><td colSpan={8} className="text-center text-slate-400 text-sm py-8">No records match the selected filters.</td></tr>
              ) : (
                paged.map(p => (
                  <tr key={p.id} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono-vg whitespace-nowrap">
                      {new Date(p.created_at).toLocaleDateString('en-GB', { day:'numeric', month:'short', year:'numeric' })}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono-vg whitespace-nowrap">{p.order_ref || '—'}</td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-[#0f2240] text-xs">{p.full_name || '—'}</p>
                      <p className="text-xs text-slate-400">{p.user_email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-mono-vg px-2 py-0.5 rounded-full ${
                        p.plan_key === 'institutional' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                      }`}>{p.plan_key}</span>
                    </td>
                    <td className="px-4 py-3 font-display font-bold text-[#0f2240] whitespace-nowrap">
                      {(p.currency ?? 'GHS').toUpperCase()} {parseFloat(String(p.amount)).toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                      {METHOD_LABELS[p.payment_method] ?? p.payment_method}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-mono-vg px-2 py-0.5 rounded-full ${
                        p.status === 'succeeded' ? 'bg-green-100 text-green-700'
                        : p.status === 'pending' ? 'bg-amber-100 text-amber-700'
                        : 'bg-red-100 text-red-600'
                      }`}>{p.status}</span>
                    </td>
                    <td className="px-4 py-3">
                      <a href={`/app/billing/invoice/${p.id}`} className="text-xs text-blue-600 hover:underline">View ↗</a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="px-4 pb-3">
          <Pagination page={page} totalPages={Math.ceil(filtered.length / PAGE_SIZE)} onPageChange={setPage} totalItems={filtered.length} pageSize={PAGE_SIZE} />
        </div>
      </div>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════
//  VERIFICATIONS TAB — for thesis §5.2 accuracy evaluation
// ════════════════════════════════════════════════════════════════════════════

const CATEGORY_LABEL: Record<string, string> = {
  known_true:  'Known-true',
  known_false: 'Known-false',
  no_coverage: 'No-coverage',
}

function VerificationsTab({ verifications, apiUrl, adminKey }: { verifications: Verification[]; apiUrl: string; adminKey: string }) {
  const today    = new Date().toISOString().slice(0, 10)
  const monthAgo = new Date(Date.now() - 60 * 86400_000).toISOString().slice(0, 10)

  const [rows, setRows] = useState<Verification[]>(verifications)
  const [dateFrom, setDateFrom] = useState(monthAgo)
  const [dateTo,   setDateTo]   = useState(today)
  const [verdictFilter,  setVerdictFilter]  = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [savingId, setSavingId] = useState<string | null>(null)

  const filtered = useMemo(() => rows.filter(v => {
    const d = v.created_at.slice(0, 10)
    if (dateFrom && d < dateFrom) return false
    if (dateTo   && d > dateTo)   return false
    if (verdictFilter  !== 'all' && v.verdict  !== verdictFilter) return false
    if (categoryFilter === 'tagged'   && !v.category) return false
    if (categoryFilter === 'untagged' && v.category)  return false
    if (['known_true','known_false','no_coverage'].includes(categoryFilter) && v.category !== categoryFilter) return false
    return true
  }), [rows, dateFrom, dateTo, verdictFilter, categoryFilter])

  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // Accuracy summary (§5.2 table)
  const tagged = filtered.filter(v => v.category)
  const summary = (['known_true','known_false','no_coverage'] as const).map(cat => {
    const rowsForCat = tagged.filter(v => v.category === cat)
    const correct    = rowsForCat.filter(v => isCorrect(v)).length
    const acc        = rowsForCat.length === 0 ? null : Math.round((correct / rowsForCat.length) * 100)
    return { cat, count: rowsForCat.length, correct, acc }
  })
  const totalTagged  = summary.reduce((s, r) => s + r.count, 0)
  const totalCorrect = summary.reduce((s, r) => s + r.correct, 0)
  const totalAcc     = totalTagged === 0 ? null : Math.round((totalCorrect / totalTagged) * 100)

  async function updateRow(id: string, patch: Partial<Pick<Verification, 'category' | 'expected_verdict'>>) {
    setSavingId(id)
    try {
      const res = await fetch(`${apiUrl}/admin/verifications/${id}`, {
        method:  'PATCH',
        headers: { 'X-Admin-Key': adminKey, 'Content-Type': 'application/json' },
        body:    JSON.stringify(patch),
      })
      if (res.ok) {
        setRows(prev => prev.map(r => r.id === id ? { ...r, ...patch } : r))
      }
    } catch { /* network — leave local state unchanged */ }
    finally { setSavingId(null) }
  }

  function exportVerificationsCSV() {
    const csv = toCSV(
      filtered,
      ['claim_text','category','expected_verdict','returned_verdict','score','correct','response_time_ms','provider_used','sources_retrieved','user_email','date'],
      v => [
        v.input_claim,
        v.category ?? '',
        v.expected_verdict ?? '',
        v.verdict,
        v.score,
        v.category ? (isCorrect(v) ? 'TRUE' : 'FALSE') : '',
        v.response_time_ms ?? '',
        v.model_used,
        v.sources_retrieved ?? '',
        v.user_email ?? '',
        new Date(v.created_at).toISOString(),
      ],
    )
    downloadCSV(csv, `verighana-verifications-${dateFrom}-${dateTo}.csv`)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center flex-wrap gap-3">
        <p className="text-sm text-slate-500">All user queries with verdict, score, and §5.2 accuracy tagging.</p>
        <button
          type="button"
          onClick={exportVerificationsCSV}
          className="bg-[#0f2240] hover:bg-[#1a3a6e] text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors flex items-center gap-2"
        >
          ↓ Export CSV
        </button>
      </div>

      {/* Accuracy summary (§5.2) */}
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Accuracy Evaluation (§5.2)</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                {['Category','Count','Expected Verdict','Correct','Accuracy'].map(h => (
                  <th key={h} className="text-left text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-wider px-3 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {summary.map(r => (
                <tr key={r.cat} className="border-b border-slate-100">
                  <td className="px-3 py-2 font-medium text-[#0f2240]">{CATEGORY_LABEL[r.cat]} claims</td>
                  <td className="px-3 py-2 font-mono-vg text-slate-600">{r.count}</td>
                  <td className="px-3 py-2 text-slate-500 text-xs">
                    {r.cat === 'known_true'  ? 'VERIFIED or PARTIAL' :
                     r.cat === 'known_false' ? 'FALSE or PARTIAL'    :
                                                'UNCORROBORATED'}
                  </td>
                  <td className="px-3 py-2 font-mono-vg text-slate-600">{r.correct}</td>
                  <td className="px-3 py-2 font-mono-vg font-semibold text-[#0f2240]">
                    {r.acc === null ? '—' : `${r.acc}%`}
                  </td>
                </tr>
              ))}
              <tr className="bg-slate-50">
                <td className="px-3 py-2 font-bold text-[#0f2240]">Total</td>
                <td className="px-3 py-2 font-mono-vg font-bold text-[#0f2240]">{totalTagged}</td>
                <td className="px-3 py-2 text-slate-400">—</td>
                <td className="px-3 py-2 font-mono-vg font-bold text-[#0f2240]">{totalCorrect}</td>
                <td className="px-3 py-2 font-mono-vg font-bold text-green-700">
                  {totalAcc === null ? '—' : `${totalAcc}%`}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        {totalTagged === 0 && (
          <p className="text-xs text-slate-400 mt-3 italic">
            Tag rows below with a category to populate this table. The thesis §5.2 sample is 20 tagged claims (7 known-true, 7 known-false, 6 no-coverage).
          </p>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">From</label>
          <input type="date" aria-label="From date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">To</label>
          <input type="date" aria-label="To date" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">Returned</label>
          <select aria-label="Returned verdict filter" value={verdictFilter} onChange={e => { setVerdictFilter(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400">
            <option value="all">All verdicts</option>
            <option value="VERIFIED">VERIFIED</option>
            <option value="PARTIAL">PARTIAL</option>
            <option value="FALSE">FALSE</option>
            <option value="UNCORROBORATED">UNCORROBORATED</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">Category</label>
          <select aria-label="Category filter" value={categoryFilter} onChange={e => { setCategoryFilter(e.target.value); setPage(1) }}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400">
            <option value="all">All</option>
            <option value="tagged">Tagged only</option>
            <option value="untagged">Untagged only</option>
            <option value="known_true">Known-true</option>
            <option value="known_false">Known-false</option>
            <option value="no_coverage">No-coverage</option>
          </select>
        </div>
      </div>

      {/* Verifications table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Queries ({filtered.length})</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                {['Date','Claim','Category','Expected','Returned','Score','Correct','Latency','Provider','Sources'].map(h => (
                  <th key={h} className="text-left text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-wider px-3 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.length === 0 ? (
                <tr><td colSpan={10} className="text-center text-slate-400 text-sm py-8">No queries match the selected filters.</td></tr>
              ) : (
                paged.map(v => {
                  const correct = isCorrect(v)
                  return (
                    <tr key={v.id} className="border-b border-slate-50 hover:bg-slate-50/40 transition-colors align-top">
                      <td className="px-3 py-3 text-xs text-slate-500 font-mono-vg whitespace-nowrap">
                        {new Date(v.created_at).toLocaleDateString('en-GB', { day:'numeric', month:'short' })}
                        <br />
                        <span className="text-slate-400">{new Date(v.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute:'2-digit' })}</span>
                      </td>
                      <td className="px-3 py-3 max-w-[280px]">
                        <p className="text-xs text-[#0f2240] line-clamp-3" title={v.input_claim}>{v.input_claim}</p>
                        {v.user_email && <p className="text-[0.6rem] text-slate-400 mt-1 font-mono-vg truncate">{v.user_email}</p>}
                      </td>
                      <td className="px-3 py-3">
                        <select
                          aria-label="Category"
                          value={v.category ?? ''}
                          onChange={e => updateRow(v.id, { category: (e.target.value || null) as Verification['category'] })}
                          disabled={savingId === v.id}
                          className="bg-white border border-slate-200 text-xs px-2 py-1 rounded outline-none focus:border-blue-400"
                        >
                          <option value="">—</option>
                          <option value="known_true">Known-true</option>
                          <option value="known_false">Known-false</option>
                          <option value="no_coverage">No-coverage</option>
                        </select>
                      </td>
                      <td className="px-3 py-3">
                        <select
                          aria-label="Expected verdict"
                          value={v.expected_verdict ?? ''}
                          onChange={e => updateRow(v.id, { expected_verdict: (e.target.value || null) as Verification['expected_verdict'] })}
                          disabled={savingId === v.id}
                          className="bg-white border border-slate-200 text-xs px-2 py-1 rounded outline-none focus:border-blue-400"
                        >
                          <option value="">—</option>
                          <option value="VERIFIED">VERIFIED</option>
                          <option value="PARTIAL">PARTIAL</option>
                          <option value="FALSE">FALSE</option>
                          <option value="UNCORROBORATED">UNCORROBORATED</option>
                        </select>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`text-[0.65rem] font-mono-vg px-2 py-0.5 rounded-full whitespace-nowrap ${
                          v.verdict === 'VERIFIED'       ? 'bg-green-100 text-green-700'  :
                          v.verdict === 'PARTIAL'        ? 'bg-amber-100 text-amber-700'  :
                          v.verdict === 'FALSE'          ? 'bg-red-100 text-red-600'      :
                          v.verdict === 'UNCORROBORATED' ? 'bg-slate-100 text-slate-500'  :
                                                            'bg-slate-200 text-slate-500'
                        }`}>{v.verdict}</span>
                      </td>
                      <td className="px-3 py-3 font-mono-vg text-xs font-bold text-[#0f2240]">{v.score}%</td>
                      <td className="px-3 py-3">
                        {correct === null
                          ? <span className="text-slate-300 text-xs">—</span>
                          : correct
                            ? <span className="text-green-600 text-sm font-bold">✓</span>
                            : <span className="text-red-500 text-sm font-bold">✗</span>}
                      </td>
                      <td className="px-3 py-3 text-xs text-slate-500 font-mono-vg whitespace-nowrap">
                        {v.response_time_ms != null ? `${(v.response_time_ms / 1000).toFixed(2)}s` : '—'}
                      </td>
                      <td className="px-3 py-3 text-[0.65rem] text-slate-500 font-mono-vg whitespace-nowrap">
                        {v.model_used?.split(':').pop()?.slice(0, 18) ?? '—'}
                      </td>
                      <td className="px-3 py-3 text-xs text-slate-500 font-mono-vg text-center">
                        {v.sources_retrieved ?? '—'}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        <div className="px-4 pb-3">
          <Pagination page={page} totalPages={Math.ceil(filtered.length / PAGE_SIZE)} onPageChange={setPage} totalItems={filtered.length} pageSize={PAGE_SIZE} />
        </div>
      </div>
    </div>
  )
}
