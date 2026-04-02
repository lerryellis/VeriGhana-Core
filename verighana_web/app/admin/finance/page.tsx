import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { FinanceClient } from './FinanceClient'

export type FinancePayment = {
  amount: number
  tax_amount: number | null
  created_at: string
  status: string
  plan_key: string
}

export type FinancePayrollRun = {
  period_year: number
  period_month: number
  total_gross_ghs: number
  total_paye_ghs: number
  total_ssf_employer_ghs: number
  total_net_ghs: number
  status: string
}

export default async function FinancePage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles').select('role').eq('user_id', user.id).single()
  const adminEmails = (process.env.ADMIN_EMAIL ?? '').split(',').map(e => e.trim().toLowerCase())
  const isAdmin = adminEmails.includes((user.email ?? '').toLowerCase()) || profile?.role === 'admin'

  const [{ data: payments }, { data: payrollRuns }] = await Promise.all([
    isAdmin
      ? supabase.from('payments').select('amount, tax_amount, created_at, status, plan_key').order('created_at', { ascending: false })
      : Promise.resolve({ data: [] }),
    supabase
      .from('payroll_runs')
      .select('period_year, period_month, total_gross_ghs, total_paye_ghs, total_ssf_employer_ghs, total_net_ghs, status')
      .order('period_year', { ascending: false })
      .order('period_month', { ascending: false }),
  ])

  return (
    <FinanceClient
      payments={(payments ?? []) as FinancePayment[]}
      payrollRuns={(payrollRuns ?? []) as FinancePayrollRun[]}
      isAdmin={isAdmin}
    />
  )
}
