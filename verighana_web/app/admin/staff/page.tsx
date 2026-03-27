import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { StaffClient } from './StaffClient'

export type StaffMember = {
  id: string
  created_at: string
  full_name: string
  email: string
  role: string
  department: string | null
  employment_type: string
  start_date: string | null
  gross_salary_ghs: number
  status: string
  notes: string | null
}

export type PayrollRun = {
  id: string
  created_at: string
  period_year: number
  period_month: number
  status: string
  total_gross_ghs: number
  total_paye_ghs: number
  total_ssf_employee_ghs: number
  total_ssf_employer_ghs: number
  total_net_ghs: number
  notes: string | null
}

export default async function StaffPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const [{ data: staff }, { data: payrollRuns }] = await Promise.all([
    supabase.from('staff').select('*').order('full_name'),
    supabase.from('payroll_runs').select('*').order('period_year', { ascending: false }).order('period_month', { ascending: false }).limit(24),
  ])

  return (
    <StaffClient
      staff={(staff ?? []) as StaffMember[]}
      payrollRuns={(payrollRuns ?? []) as PayrollRun[]}
    />
  )
}
