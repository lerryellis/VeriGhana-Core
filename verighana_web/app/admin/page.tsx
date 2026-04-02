import { createClient } from '@/lib/supabase/server'
import { AdminClient } from './AdminClient'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

async function fetchAdminStats() {
  try {
    const res = await fetch(`${API_URL}/admin/stats`, {
      headers: { 'X-Admin-Key': ADMIN_KEY },
      cache: 'no-store',
    })
    if (!res.ok) return null
    return res.json() as Promise<{
      articles: number; sources: number; tickets: number; users: number
      payments: number; revenue_usd: number; pro_subs: number; inst_subs: number
    }>
  } catch {
    return null
  }
}

export type CrmUser = {
  created_at: string
  tier: string
  role: string
  daily_queries_used: number
  subscription_status: string | null
}

export default async function AdminPage() {
  const [stats, supabase] = await Promise.all([fetchAdminStats(), createClient()])

  // CRM data: all user profiles for signup chart, segmentation, and churn
  const { data: crmUsers } = await supabase
    .from('user_profiles')
    .select('created_at, tier, role, daily_queries_used, subscription_status')
    .order('created_at', { ascending: true })

  return (
    <AdminClient
      stats={stats}
      adminKey={ADMIN_KEY}
      apiUrl={API_URL}
      crmUsers={(crmUsers ?? []) as CrmUser[]}
    />
  )
}
