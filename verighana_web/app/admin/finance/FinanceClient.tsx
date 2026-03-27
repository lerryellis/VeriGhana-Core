'use client'

import { useState, useMemo } from 'react'
import type { FinancePayment, FinancePayrollRun } from './page'

interface Props {
  payments: FinancePayment[]
  payrollRuns: FinancePayrollRun[]
  isAdmin: boolean
}

const USD_TO_GHS = 15
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function fmt(n: number, currency = '₵') {
  return `${currency}${n.toLocaleString('en-GH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtUsd(n: number) {
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

type Period = '30d' | '90d' | '1y' | 'all'

export function FinanceClient({ payments, payrollRuns, isAdmin }: Props) {
  const [period, setPeriod] = useState<Period>('all')

  const cutoff = useMemo(() => {
    if (period === 'all') return null
    const d = new Date()
    if (period === '30d') d.setDate(d.getDate() - 30)
    else if (period === '90d') d.setDate(d.getDate() - 90)
    else if (period === '1y') d.setFullYear(d.getFullYear() - 1)
    return d.toISOString().slice(0, 10)
  }, [period])

  // ── Revenue ──────────────────────────────────────────────────────────────
  const succeeded = useMemo(() => payments.filter(p => {
    if (p.status !== 'succeeded') return false
    if (cutoff && p.created_at.slice(0, 10) < cutoff) return false
    return true
  }), [payments, cutoff])

  const revenueUsd   = succeeded.reduce((s, p) => s + Number(p.amount), 0)
  const taxUsd       = succeeded.reduce((s, p) => s + (p.tax_amount !== null ? Number(p.tax_amount) : Number(p.amount) * 0.20), 0)
  const grossUsd     = revenueUsd + taxUsd  // total collected (subtotal + tax)
  const revenueGhs   = revenueUsd   * USD_TO_GHS
  const taxGhs       = taxUsd       * USD_TO_GHS
  const grossGhs     = grossUsd     * USD_TO_GHS

  // GRA tax breakdown
  const vatGhs       = taxGhs * (15 / 20)    // 15% portion
  const nhilGhs      = taxGhs * (2.5 / 20)   // 2.5% portion
  const getfundGhs   = taxGhs * (2.5 / 20)   // 2.5% portion

  // ── Payroll ───────────────────────────────────────────────────────────────
  const relevantRuns = useMemo(() => {
    if (!cutoff) return payrollRuns
    return payrollRuns.filter(r => {
      const d = `${r.period_year}-${String(r.period_month).padStart(2,'0')}-01`
      return d >= cutoff
    })
  }, [payrollRuns, cutoff])

  const payrollGross     = relevantRuns.reduce((s, r) => s + Number(r.total_gross_ghs), 0)
  const payrollPAYE      = relevantRuns.reduce((s, r) => s + Number(r.total_paye_ghs), 0)
  const payrollSsfEmpr   = relevantRuns.reduce((s, r) => s + Number(r.total_ssf_employer_ghs), 0)
  const totalPayrollCost = payrollGross + payrollSsfEmpr  // employer's true cost

  // ── Profit ────────────────────────────────────────────────────────────────
  // Profit = Revenue (pre-tax) in GHS − total payroll cost
  // Tax collected from customers is a liability (pass-through to GRA)
  const profitGhs = revenueGhs - totalPayrollCost

  // ── Month-by-month revenue ────────────────────────────────────────────────
  const monthlyRevenue = useMemo(() => {
    const map: Record<string, number> = {}
    succeeded.forEach(p => {
      const key = p.created_at.slice(0, 7)
      map[key] = (map[key] ?? 0) + Number(p.amount)
    })
    return Object.entries(map).sort(([a],[b]) => a.localeCompare(b)).slice(-12).map(([month, amt]) => ({
      label: `${MONTHS[parseInt(month.slice(5)) - 1]} ${month.slice(2, 4)}`,
      usd: amt,
      ghs: amt * USD_TO_GHS,
    }))
  }, [succeeded])

  const maxMonthly = Math.max(...monthlyRevenue.map(m => m.ghs), 1)

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold text-[#0f2240]">Finance</h1>
          <p className="text-sm text-slate-500 mt-0.5">{isAdmin ? 'Earnings, tax obligations, and payroll' : 'Payroll overview'}</p>
        </div>
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
          {(['30d','90d','1y','all'] as Period[]).map(p => (
            <button key={p} type="button" onClick={() => setPeriod(p)}
              className={`text-xs px-3 py-1.5 rounded-md transition-colors font-mono-vg ${period === p ? 'bg-white shadow-sm text-[#0f2240] font-bold' : 'text-slate-500 hover:text-slate-700'}`}>
              {p === 'all' ? 'All time' : p}
            </button>
          ))}
        </div>
      </div>

      {/* ── Top KPIs — admin only ───────────────────────────────────────────── */}
      {isAdmin && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Gross Collected',  value: fmtUsd(grossUsd),   sub: fmt(grossGhs),   color: 'text-[#0f2240]',  tip: 'Subtotal + all taxes received' },
            { label: 'Revenue (pre-tax)',value: fmtUsd(revenueUsd),  sub: fmt(revenueGhs), color: 'text-green-600',  tip: 'Subscription fees before taxes' },
            { label: 'Tax Collected',    value: fmtUsd(taxUsd),      sub: fmt(taxGhs),     color: 'text-amber-600',  tip: 'To be remitted to GRA' },
            { label: 'Est. Profit',      value: fmt(profitGhs),      sub: 'after payroll', color: profitGhs >= 0 ? 'text-green-600' : 'text-red-500', tip: 'Revenue − payroll cost (GHS)' },
          ].map(k => (
            <div key={k.label} className="bg-white border border-slate-200 rounded-xl p-4" title={k.tip}>
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1">{k.label}</p>
              <p className={`text-xl font-display font-extrabold ${k.color}`}>{k.value}</p>
              <p className="text-xs text-slate-400 font-mono-vg mt-0.5">{k.sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Tax Breakdown — admin only ───────────────────────────────────────── */}
      {isAdmin && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Tax Obligations to GRA</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { label: 'VAT (15%)',     value: vatGhs,     note: 'Value Added Tax',                 color: 'text-red-600',    due: 'File monthly VAT return' },
              { label: 'NHIL (2.5%)',   value: nhilGhs,    note: 'Nat. Health Insurance Levy',      color: 'text-orange-500', due: 'Remit with VAT return' },
              { label: 'GETFund (2.5%)',value: getfundGhs, note: 'Ghana Education Trust Fund Levy', color: 'text-amber-500',  due: 'Remit with VAT return' },
            ].map(({ label, value, note, color, due }) => (
              <div key={label} className="border border-slate-100 rounded-xl p-4">
                <p className={`text-xl font-display font-extrabold ${color}`}>{fmt(value)}</p>
                <p className="text-sm font-medium text-[#0f2240] mt-1">{label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{note}</p>
                <p className="text-xs text-slate-300 font-mono-vg mt-2">{due}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-4 font-mono-vg">
            Total GRA tax liability: <span className="font-bold text-slate-600">{fmt(taxGhs)}</span> · Estimated at 15 GHS/USD
          </p>
        </div>
      )}

      {/* ── Payroll Cost Summary ─────────────────────────────────────────────── */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Payroll Obligations</p>
        {payrollRuns.length === 0
          ? <p className="text-sm text-slate-400">No payroll runs recorded yet. Go to Staff → Payroll to run payroll.</p>
          : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Gross Salaries',    value: payrollGross,     color: 'text-[#0f2240]', note: `${relevantRuns.length} pay period${relevantRuns.length !== 1 ? 's' : ''}` },
                { label: 'PAYE to GRA',       value: payrollPAYE,      color: 'text-red-600',   note: 'Withheld from staff' },
                { label: 'Employer SSF (13%)',value: payrollSsfEmpr,   color: 'text-orange-500', note: 'Your contribution' },
                { label: 'Total Payroll Cost',value: totalPayrollCost, color: 'text-slate-700', note: 'Gross + employer SSF' },
              ].map(k => (
                <div key={k.label} className="border border-slate-100 rounded-xl p-4">
                  <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1">{k.label}</p>
                  <p className={`text-xl font-display font-extrabold ${k.color}`}>{fmt(k.value)}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{k.note}</p>
                </div>
              ))}
            </div>
          )
        }
      </div>

      {/* ── Monthly Revenue Chart ────────────────────────────────────────────── */}
      {isAdmin && monthlyRevenue.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Monthly Revenue (GHS, pre-tax)</p>
          <div className="flex items-end gap-2 h-32">
            {monthlyRevenue.map(m => (
              <div key={m.label} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                <span className="text-[0.6rem] text-slate-400 font-mono-vg hidden md:block">{fmt(m.ghs, '₵')}</span>
                <div
                  className="w-full bg-blue-500 rounded-t-sm min-h-[4px] transition-all"
                  style={{ height: `${(m.ghs / maxMonthly) * 100}%` }}
                />
                <span className="text-[0.6rem] text-slate-400 font-mono-vg truncate w-full text-center">{m.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── P&L Summary ─────────────────────────────────────────────────────── */}
      {isAdmin && <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">P&L Summary (GHS)</p>
        <div className="space-y-2 max-w-sm">
          {[
            { label: 'Gross collected',        value: grossGhs,          sign: '',   color: 'text-[#0f2240]' },
            { label: '− GRA taxes (VAT/NHIL/GETFund)', value: taxGhs,   sign: '−',  color: 'text-amber-600' },
            { label: '= Net Revenue',          value: revenueGhs,        sign: '=',  color: 'text-green-600', bold: true },
            { label: '− Total payroll cost',   value: totalPayrollCost,  sign: '−',  color: 'text-slate-600' },
            { label: '= Estimated Profit',     value: profitGhs,         sign: '=',  color: profitGhs >= 0 ? 'text-green-700' : 'text-red-500', bold: true },
          ].map(row => (
            <div key={row.label} className={`flex items-center justify-between ${row.bold ? 'border-t border-slate-200 pt-2 mt-2' : ''}`}>
              <span className="text-sm text-slate-500">{row.label}</span>
              <span className={`text-sm font-mono-vg ${row.bold ? 'font-bold text-base' : ''} ${row.color}`}>
                {row.sign} {fmt(Math.abs(row.value))}
              </span>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-300 font-mono-vg mt-4">
          Note: USD converted at ₵{USD_TO_GHS}/USD (fixed rate). Profit estimate does not include hosting, tooling, or other operational costs.
        </p>
      </div>}
    </div>
  )
}
