'use client'

import { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line,
} from 'recharts'
import type { Payment } from './page'

interface Props { payments: Payment[] }

const METHOD_LABELS: Record<string, string> = {
  card: 'Card', mtn_momo: 'MTN MoMo',
  vodafone_cash: 'Vodafone Cash', airteltigo_money: 'AirtelTigo',
}

function toCSV(rows: Payment[]): string {
  const headers = ['Order Ref','Date','Name','Email','Plan','Amount','Currency','Method','Status','Country','Promo']
  const lines = rows.map(p => [
    p.order_ref, new Date(p.created_at).toISOString().slice(0,10),
    p.full_name, p.user_email, p.plan_key, p.amount, p.currency,
    p.payment_method, p.status, p.country, p.promo_code ?? '',
  ].map(v => `"${String(v).replace(/"/g,'""')}"`).join(','))
  return [headers.join(','), ...lines].join('\n')
}

function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}

export function ReportsClient({ payments }: Props) {
  const today    = new Date().toISOString().slice(0, 10)
  const monthAgo = new Date(Date.now() - 30 * 86400_000).toISOString().slice(0, 10)

  const [dateFrom, setDateFrom] = useState(monthAgo)
  const [dateTo,   setDateTo]   = useState(today)
  const [planFilter, setPlanFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

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

  const succeeded = filtered.filter(p => p.status === 'succeeded')
  const revenue   = succeeded.reduce((s, p) => s + parseFloat(String(p.amount)), 0)
  const proCount  = succeeded.filter(p => p.plan_key === 'pro').length
  const instCount = succeeded.filter(p => p.plan_key === 'institutional').length

  // Daily revenue chart data
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

  // Revenue by plan
  const planData = [
    { name: 'Pro',           value: succeeded.filter(p => p.plan_key === 'pro').reduce((s,p) => s + parseFloat(String(p.amount)), 0) },
    { name: 'Institutional', value: succeeded.filter(p => p.plan_key === 'institutional').reduce((s,p) => s + parseFloat(String(p.amount)), 0) },
  ]

  // Revenue by method
  const methodMap: Record<string, number> = {}
  succeeded.forEach(p => {
    const m = METHOD_LABELS[p.payment_method] ?? p.payment_method
    methodMap[m] = (methodMap[m] ?? 0) + parseFloat(String(p.amount))
  })
  const methodData = Object.entries(methodMap).map(([name, value]) => ({ name, value: parseFloat(value.toFixed(2)) }))

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Sales Reports</h1>
        <button
          type="button"
          onClick={() => downloadCSV(toCSV(filtered), `verighana-sales-${dateFrom}-${dateTo}.csv`)}
          className="bg-[#0f2240] hover:bg-[#1a3a6e] text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors flex items-center gap-2"
        >
          ↓ Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">From</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">To</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">Plan</label>
          <select value={planFilter} onChange={e => setPlanFilter(e.target.value)}
            className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400">
            <option value="all">All plans</option>
            <option value="pro">Pro</option>
            <option value="institutional">Institutional</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-400 font-mono-vg uppercase tracking-wider mb-1">Status</label>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
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
          { label: 'Revenue (USD)', value: `$${revenue.toFixed(2)}`, color: 'text-green-600' },
          { label: 'Transactions',  value: succeeded.length,          color: 'text-[#0f2240]' },
          { label: 'Pro Subs',      value: proCount,                  color: 'text-blue-600' },
          { label: 'Institutional', value: instCount,                 color: 'text-purple-600' },
        ].map(k => (
          <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-3 text-center">
            <div className={`font-display text-2xl font-bold ${k.color}`}>{k.value}</div>
            <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
          </div>
        ))}
      </div>

      {/* Daily revenue chart */}
      {dailyMap.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Daily Revenue (USD)</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={dailyMap} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip formatter={(v) => [`$${Number(v).toFixed(2)}`, 'Revenue']} />
              <Line type="monotone" dataKey="amount" stroke="#2563eb" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Plan + method charts side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Revenue by Plan</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={planData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip formatter={(v) => [`$${Number(v).toFixed(2)}`, 'Revenue']} />
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
              <Tooltip formatter={(v) => [`$${Number(v).toFixed(2)}`, 'Revenue']} />
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
              {filtered.length === 0 ? (
                <tr><td colSpan={8} className="text-center text-slate-400 text-sm py-8">No records match the selected filters.</td></tr>
              ) : (
                filtered.map(p => (
                  <tr key={p.id} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono-vg whitespace-nowrap">
                      {new Date(p.created_at).toLocaleDateString('en-GB', { day:'numeric', month:'short', year:'numeric' })}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono-vg whitespace-nowrap">
                      {p.order_ref || '—'}
                    </td>
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
                      {(p.currency ?? 'USD').toUpperCase()} {parseFloat(String(p.amount)).toFixed(2)}
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
                      <a href={`/app/billing/invoice/${p.id}`} className="text-xs text-blue-600 hover:underline">
                        View ↗
                      </a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
