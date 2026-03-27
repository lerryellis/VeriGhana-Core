'use client'

import { useState, useMemo } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { StaffMember, PayrollRun } from './page'

interface Props {
  staff: StaffMember[]
  payrollRuns: PayrollRun[]
}

const ROLES = ['Developer', 'Researcher', 'Support', 'Admin', 'Content', 'Contractor', 'Other']
const DEPTS = ['Engineering', 'Research', 'Operations', 'Finance', 'Communications', 'Management']
const EMP_TYPES = [
  { value: 'full_time',  label: 'Full Time' },
  { value: 'part_time',  label: 'Part Time' },
  { value: 'contract',   label: 'Contract'  },
]
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

// ── Ghana PAYE monthly tax bands (2024/2025) ────────────────────────────────
// First GHS 490: 0%  |  Next 110: 5%  |  Next 130: 10%
// Next 3,000: 17.5%  |  Next 16,400: 25%  |  Above 20,130: 30%
const PAYE_BANDS = [
  { limit: 490,    rate: 0 },
  { limit: 110,    rate: 0.05 },
  { limit: 130,    rate: 0.10 },
  { limit: 3000,   rate: 0.175 },
  { limit: 16400,  rate: 0.25 },
  { limit: Infinity, rate: 0.30 },
]

function calcPAYE(gross: number): number {
  let remaining = gross, tax = 0
  for (const { limit, rate } of PAYE_BANDS) {
    const taxable = Math.min(remaining, limit)
    tax      += taxable * rate
    remaining -= taxable
    if (remaining <= 0) break
  }
  return Math.round(tax * 100) / 100
}

function fmt(n: number) {
  return n.toLocaleString('en-GH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const STATUS_CHIP: Record<string, string> = {
  active:     'bg-green-100 text-green-700',
  inactive:   'bg-amber-100 text-amber-700',
  terminated: 'bg-red-100 text-red-600',
}

// ── Enroll form state ────────────────────────────────────────────────────────
type EnrollForm = {
  full_name: string; email: string; role: string; department: string
  employment_type: string; start_date: string; gross_salary_ghs: string; notes: string
}

const EMPTY_FORM: EnrollForm = {
  full_name: '', email: '', role: ROLES[0], department: '', employment_type: 'full_time',
  start_date: '', gross_salary_ghs: '', notes: '',
}

export function StaffClient({ staff: initialStaff, payrollRuns: initialRuns }: Props) {
  const [tab, setTab]             = useState<'staff' | 'payroll'>('staff')
  const [staff, setStaff]         = useState<StaffMember[]>(initialStaff)
  const [payrollRuns, setPayrollRuns] = useState<PayrollRun[]>(initialRuns)

  // Staff tab state
  const [showEnroll, setShowEnroll] = useState(false)
  const [form, setForm]           = useState<EnrollForm>(EMPTY_FORM)
  const [enrolling, setEnrolling] = useState(false)
  const [enrollMsg, setEnrollMsg] = useState<{ type: 'success'|'error'; text: string } | null>(null)
  const [statusFilter, setStatusFilter] = useState<'all'|'active'|'inactive'|'terminated'>('all')

  // Payroll tab state
  const today         = new Date()
  const [payYear, setPayYear]   = useState(today.getFullYear())
  const [payMonth, setPayMonth] = useState(today.getMonth() + 1)
  const [runningPayroll, setRunningPayroll] = useState(false)
  const [runMsg, setRunMsg]     = useState<{ type: 'success'|'error'; text: string } | null>(null)

  // ── Computed payroll preview ──────────────────────────────────────────────
  const activeStaff = staff.filter(s => s.status === 'active')
  const payrollPreview = useMemo(() => activeStaff.map(s => {
    const gross   = Number(s.gross_salary_ghs)
    const paye    = calcPAYE(gross)
    const ssfEmp  = Math.round(gross * 0.055 * 100) / 100   // 5.5% employee
    const ssfEmpr = Math.round(gross * 0.13  * 100) / 100   // 13%  employer
    const net     = Math.round((gross - paye - ssfEmp) * 100) / 100
    return { ...s, gross, paye, ssfEmp, ssfEmpr, net }
  }), [activeStaff])

  const payTotals = useMemo(() => payrollPreview.reduce(
    (acc, e) => ({
      gross: acc.gross + e.gross,
      paye:  acc.paye  + e.paye,
      ssfEmp: acc.ssfEmp + e.ssfEmp,
      ssfEmpr: acc.ssfEmpr + e.ssfEmpr,
      net:   acc.net   + e.net,
    }),
    { gross: 0, paye: 0, ssfEmp: 0, ssfEmpr: 0, net: 0 }
  ), [payrollPreview])

  const existingRun = payrollRuns.find(r => r.period_year === payYear && r.period_month === payMonth)

  // ── Enroll staff ──────────────────────────────────────────────────────────
  async function handleEnroll(e: React.FormEvent) {
    e.preventDefault()
    if (!form.full_name.trim() || !form.email.trim() || !form.gross_salary_ghs) {
      setEnrollMsg({ type: 'error', text: 'Name, email and salary are required.' })
      return
    }
    setEnrolling(true)
    setEnrollMsg(null)
    const supabase = createClient()
    const { data, error } = await supabase.from('staff').insert({
      full_name:        form.full_name.trim(),
      email:            form.email.trim(),
      role:             form.role,
      department:       form.department || null,
      employment_type:  form.employment_type,
      start_date:       form.start_date || null,
      gross_salary_ghs: parseFloat(form.gross_salary_ghs),
      notes:            form.notes.trim() || null,
    }).select('*').single()
    setEnrolling(false)
    if (error) {
      setEnrollMsg({ type: 'error', text: error.message })
    } else {
      setStaff(prev => [...prev, data as StaffMember].sort((a,b) => a.full_name.localeCompare(b.full_name)))
      setForm(EMPTY_FORM)
      setShowEnroll(false)
      setEnrollMsg({ type: 'success', text: `${data.full_name} enrolled successfully.` })
    }
  }

  async function updateStatus(id: string, status: string) {
    const supabase = createClient()
    await supabase.from('staff').update({ status }).eq('id', id)
    setStaff(prev => prev.map(s => s.id === id ? { ...s, status } : s))
  }

  async function updateSystemRole(email: string, role: 'admin' | 'client') {
    const supabase = createClient()
    // Find user_profile by email via user_id join
    const { data: profile } = await supabase
      .from('user_profiles')
      .select('user_id')
      .eq('email', email)
      .single()
    if (!profile) {
      setEnrollMsg({ type: 'error', text: `No system account found for ${email}. They must register first.` })
      return
    }
    await supabase.from('user_profiles').update({ role }).eq('user_id', profile.user_id)
    setEnrollMsg({ type: 'success', text: `${email} system role updated to "${role}".` })
  }

  // ── Run payroll ───────────────────────────────────────────────────────────
  async function runPayroll() {
    if (!payrollPreview.length) return
    setRunningPayroll(true)
    setRunMsg(null)
    const supabase = createClient()

    const runPayload = {
      period_year:  payYear,
      period_month: payMonth,
      status:       'draft',
      total_gross_ghs:       Math.round(payTotals.gross  * 100) / 100,
      total_paye_ghs:        Math.round(payTotals.paye   * 100) / 100,
      total_ssf_employee_ghs: Math.round(payTotals.ssfEmp * 100) / 100,
      total_ssf_employer_ghs: Math.round(payTotals.ssfEmpr * 100) / 100,
      total_net_ghs:         Math.round(payTotals.net    * 100) / 100,
    }

    let runId: string
    if (existingRun) {
      await supabase.from('payroll_runs').update(runPayload).eq('id', existingRun.id)
      runId = existingRun.id
    } else {
      const { data, error } = await supabase.from('payroll_runs').insert(runPayload).select('id').single()
      if (error) { setRunMsg({ type: 'error', text: error.message }); setRunningPayroll(false); return }
      runId = data.id
    }

    // Upsert entries
    const entries = payrollPreview.map(e => ({
      payroll_run_id:   runId,
      staff_id:         e.id,
      gross_salary_ghs: e.gross,
      paye_tax_ghs:     e.paye,
      ssf_employee_ghs: e.ssfEmp,
      ssf_employer_ghs: e.ssfEmpr,
      net_salary_ghs:   e.net,
    }))
    await supabase.from('payroll_entries').upsert(entries, { onConflict: 'payroll_run_id,staff_id' })

    const saved: PayrollRun = { ...runPayload, id: runId, created_at: new Date().toISOString(), notes: null }
    setPayrollRuns(prev => {
      const without = prev.filter(r => !(r.period_year === payYear && r.period_month === payMonth))
      return [saved, ...without].sort((a,b) => b.period_year !== a.period_year ? b.period_year - a.period_year : b.period_month - a.period_month)
    })
    setRunMsg({ type: 'success', text: `Payroll for ${MONTHS[payMonth-1]} ${payYear} saved as draft.` })
    setRunningPayroll(false)
  }

  const filteredStaff = staff.filter(s => statusFilter === 'all' || s.status === statusFilter)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Staff & Payroll</h1>
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
          {(['staff', 'payroll'] as const).map(t => (
            <button key={t} type="button" onClick={() => setTab(t)}
              className={`text-sm px-4 py-1.5 rounded-md transition-colors capitalize ${tab === t ? 'bg-white shadow-sm text-[#0f2240] font-medium' : 'text-slate-500 hover:text-slate-700'}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ── Staff Tab ────────────────────────────────────────────────── */}
      {tab === 'staff' && (
        <div className="space-y-4">
          {/* KPIs */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Total Staff',  value: staff.length },
              { label: 'Active',       value: staff.filter(s => s.status === 'active').length },
              { label: 'Monthly Payroll (GHS)', value: `₵${fmt(staff.filter(s=>s.status==='active').reduce((a,s)=>a+Number(s.gross_salary_ghs),0))}` },
            ].map(k => (
              <div key={k.label} className="bg-white border border-slate-200 rounded-xl p-4">
                <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1">{k.label}</p>
                <p className="text-xl font-display font-extrabold text-[#0f2240]">{k.value}</p>
              </div>
            ))}
          </div>

          {enrollMsg && (
            <div className={`text-sm px-4 py-3 rounded-xl ${enrollMsg.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
              {enrollMsg.text}
            </div>
          )}

          {/* Filter + Enroll */}
          <div className="flex items-center gap-3">
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value as typeof statusFilter)}
              aria-label="Filter by status"
              className="bg-white border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none">
              <option value="all">All</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="terminated">Terminated</option>
            </select>
            <div className="flex-1" />
            <button type="button" onClick={() => { setShowEnroll(!showEnroll); setEnrollMsg(null) }}
              className="bg-[#0f2240] hover:bg-[#1a3560] text-white text-sm px-4 py-2 rounded-lg transition-colors">
              {showEnroll ? 'Cancel' : '+ Enroll Staff'}
            </button>
          </div>

          {/* Enroll form */}
          {showEnroll && (
            <form onSubmit={handleEnroll} className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">New Staff Member</p>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Full Name', key: 'full_name', type: 'text', placeholder: 'Kofi Mensah' },
                  { label: 'Email', key: 'email', type: 'email', placeholder: 'kofi@verighana.com' },
                  { label: 'Start Date', key: 'start_date', type: 'date', placeholder: '' },
                  { label: 'Gross Monthly Salary (GHS)', key: 'gross_salary_ghs', type: 'number', placeholder: '3000' },
                ].map(({ label, key, type, placeholder }) => (
                  <div key={key}>
                    <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">{label}</label>
                    <input
                      type={type}
                      value={form[key as keyof EnrollForm]}
                      onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
                      placeholder={placeholder}
                      className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
                    />
                  </div>
                ))}
                <div>
                  <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Role</label>
                  <select value={form.role} onChange={e => setForm(p => ({ ...p, role: e.target.value }))}
                    aria-label="Staff role"
                    className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors">
                    {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Department</label>
                  <select value={form.department} onChange={e => setForm(p => ({ ...p, department: e.target.value }))}
                    aria-label="Department"
                    className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors">
                    <option value="">— Select —</option>
                    {DEPTS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Employment Type</label>
                  <select value={form.employment_type} onChange={e => setForm(p => ({ ...p, employment_type: e.target.value }))}
                    aria-label="Employment type"
                    className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors">
                    {EMP_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Notes (optional)</label>
                <textarea value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
                  aria-label="Notes" rows={2} className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors resize-none" />
              </div>
              <div className="flex justify-end">
                <button type="submit" disabled={enrolling}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors flex items-center gap-2">
                  {enrolling ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"/>Saving…</> : 'Enroll Staff Member'}
                </button>
              </div>
            </form>
          )}

          {/* Staff table */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            {filteredStaff.length === 0
              ? <p className="text-sm text-slate-400 text-center py-10">No staff enrolled yet.</p>
              : filteredStaff.map(s => (
                <div key={s.id} className="flex items-center justify-between px-4 py-3 border-b border-slate-100 last:border-0 gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[#0f2240]">{s.full_name}</p>
                    <p className="text-xs text-slate-400 font-mono-vg">{s.role}{s.department ? ` · ${s.department}` : ''} · {EMP_TYPES.find(t=>t.value===s.employment_type)?.label ?? s.employment_type}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-medium text-[#0f2240]">₵{fmt(Number(s.gross_salary_ghs))}/mo</p>
                    <p className="text-xs text-slate-400 font-mono-vg">Net ≈ ₵{fmt(Number(s.gross_salary_ghs) - calcPAYE(Number(s.gross_salary_ghs)) - Math.round(Number(s.gross_salary_ghs)*0.055*100)/100)}</p>
                  </div>
                  <span className={`text-xs px-2.5 py-1 rounded-full font-mono-vg shrink-0 ${STATUS_CHIP[s.status] ?? 'bg-slate-100 text-slate-500'}`}>{s.status}</span>
                  <select
                    value={s.status}
                    onChange={e => updateStatus(s.id, e.target.value)}
                    aria-label={`Update employment status for ${s.full_name}`}
                    className="text-xs bg-slate-50 border border-slate-200 text-slate-600 px-2 py-1 rounded-lg outline-none cursor-pointer"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="terminated">Terminated</option>
                  </select>
                  <select
                    defaultValue="client"
                    onChange={e => updateSystemRole(s.email, e.target.value as 'admin' | 'client')}
                    aria-label={`System role for ${s.full_name}`}
                    className="text-xs bg-amber-50 border border-amber-200 text-amber-700 px-2 py-1 rounded-lg outline-none cursor-pointer"
                    title="Platform system role (requires a registered account)"
                  >
                    <option value="client">client</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
              ))
            }
          </div>
        </div>
      )}

      {/* ── Payroll Tab ───────────────────────────────────────────────── */}
      {tab === 'payroll' && (
        <div className="space-y-4">
          {/* Period selector */}
          <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap items-center gap-3">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mr-2">Pay Period</p>
            <select value={payMonth} onChange={e => setPayMonth(Number(e.target.value))}
              aria-label="Payroll month"
              className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none">
              {MONTHS.map((m, i) => <option key={m} value={i+1}>{m}</option>)}
            </select>
            <select value={payYear} onChange={e => setPayYear(Number(e.target.value))}
              aria-label="Payroll year"
              className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none">
              {[today.getFullYear() - 1, today.getFullYear(), today.getFullYear() + 1].map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            {existingRun && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-mono-vg ${existingRun.status === 'paid' ? 'bg-green-100 text-green-700' : existingRun.status === 'approved' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>
                {existingRun.status}
              </span>
            )}
          </div>

          {/* Tax info card */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
            <p className="text-xs text-blue-700 font-mono-vg uppercase tracking-widest mb-1">Ghana PAYE Bands (Monthly)</p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-blue-600 font-mono-vg">
              <span>0 – ₵490: 0%</span>
              <span>₵491 – ₵600: 5%</span>
              <span>₵601 – ₵730: 10%</span>
              <span>₵731 – ₵3,730: 17.5%</span>
              <span>₵3,731 – ₵20,130: 25%</span>
              <span>Above ₵20,130: 30%</span>
            </div>
            <p className="text-xs text-blue-500 mt-1 font-mono-vg">SSF: Employee 5.5% · Employer 13% of gross</p>
          </div>

          {/* Preview table */}
          {payrollPreview.length === 0
            ? <div className="bg-white border border-slate-200 rounded-xl p-10 text-center text-slate-400 text-sm">No active staff to process payroll for.</div>
            : (
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <div className="grid grid-cols-[1fr_repeat(5,auto)] gap-0 border-b border-slate-100 px-4 py-2 text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest">
                  <span>Staff</span>
                  <span className="px-3 text-right">Gross (₵)</span>
                  <span className="px-3 text-right">PAYE (₵)</span>
                  <span className="px-3 text-right">SSF Emp (₵)</span>
                  <span className="px-3 text-right">SSF Empr (₵)</span>
                  <span className="px-3 text-right">Net Pay (₵)</span>
                </div>
                {payrollPreview.map(e => (
                  <div key={e.id} className="grid grid-cols-[1fr_repeat(5,auto)] items-center gap-0 px-4 py-2.5 border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <div>
                      <p className="text-sm text-[#0f2240]">{e.full_name}</p>
                      <p className="text-xs text-slate-400 font-mono-vg">{e.role}</p>
                    </div>
                    <span className="px-3 text-right text-sm text-slate-700 font-mono-vg">{fmt(e.gross)}</span>
                    <span className="px-3 text-right text-sm text-red-600 font-mono-vg">−{fmt(e.paye)}</span>
                    <span className="px-3 text-right text-sm text-orange-500 font-mono-vg">−{fmt(e.ssfEmp)}</span>
                    <span className="px-3 text-right text-sm text-slate-400 font-mono-vg">{fmt(e.ssfEmpr)}</span>
                    <span className="px-3 text-right text-sm font-medium text-green-700 font-mono-vg">{fmt(e.net)}</span>
                  </div>
                ))}
                {/* Totals row */}
                <div className="grid grid-cols-[1fr_repeat(5,auto)] items-center gap-0 px-4 py-3 bg-slate-50 border-t border-slate-200 font-medium">
                  <span className="text-sm text-[#0f2240]">Totals ({payrollPreview.length} staff)</span>
                  <span className="px-3 text-right text-sm text-[#0f2240] font-mono-vg font-bold">{fmt(payTotals.gross)}</span>
                  <span className="px-3 text-right text-sm text-red-600 font-mono-vg font-bold">−{fmt(payTotals.paye)}</span>
                  <span className="px-3 text-right text-sm text-orange-500 font-mono-vg font-bold">−{fmt(payTotals.ssfEmp)}</span>
                  <span className="px-3 text-right text-sm text-slate-500 font-mono-vg font-bold">{fmt(payTotals.ssfEmpr)}</span>
                  <span className="px-3 text-right text-sm text-green-700 font-mono-vg font-bold">{fmt(payTotals.net)}</span>
                </div>
              </div>
            )
          }

          {/* Government remittance summary */}
          {payrollPreview.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { label: 'PAYE to remit to GRA', value: payTotals.paye, note: 'Due by 15th of following month', color: 'text-red-600' },
                { label: 'SSF Employee to remit', value: payTotals.ssfEmp, note: '5.5% of gross per employee', color: 'text-orange-500' },
                { label: 'SSF Employer cost', value: payTotals.ssfEmpr, note: '13% of gross (your cost)', color: 'text-slate-600' },
              ].map(k => (
                <div key={k.label} className="bg-white border border-slate-200 rounded-xl p-4">
                  <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1">{k.label}</p>
                  <p className={`text-xl font-display font-extrabold ${k.color}`}>₵{fmt(k.value)}</p>
                  <p className="text-xs text-slate-400 mt-1">{k.note}</p>
                </div>
              ))}
            </div>
          )}

          {runMsg && (
            <div className={`text-sm px-4 py-3 rounded-xl ${runMsg.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
              {runMsg.text}
            </div>
          )}

          <div className="flex justify-end">
            <button type="button" disabled={runningPayroll || !payrollPreview.length} onClick={runPayroll}
              className="bg-[#0f2240] hover:bg-[#1a3560] disabled:opacity-50 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors flex items-center gap-2">
              {runningPayroll
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"/>Processing…</>
                : existingRun ? `Update ${MONTHS[payMonth-1]} ${payYear} Payroll` : `Save ${MONTHS[payMonth-1]} ${payYear} Payroll`}
            </button>
          </div>

          {/* Payroll history */}
          {payrollRuns.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100">
                <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Payroll History</p>
              </div>
              {payrollRuns.map(r => (
                <div key={r.id} className="flex items-center justify-between px-4 py-3 border-b border-slate-100 last:border-0">
                  <div>
                    <p className="text-sm font-medium text-[#0f2240]">{MONTHS[r.period_month - 1]} {r.period_year}</p>
                    <p className="text-xs text-slate-400 font-mono-vg">Gross ₵{fmt(Number(r.total_gross_ghs))} · Net ₵{fmt(Number(r.total_net_ghs))}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-red-500 font-mono-vg">PAYE ₵{fmt(Number(r.total_paye_ghs))}</p>
                    <span className={`text-xs px-2.5 py-0.5 rounded-full font-mono-vg ${r.status === 'paid' ? 'bg-green-100 text-green-700' : r.status === 'approved' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>{r.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
