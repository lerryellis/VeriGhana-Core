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

export default async function AdminPage() {
  const stats = await fetchAdminStats()

  return <AdminClient stats={stats} adminKey={ADMIN_KEY} apiUrl={API_URL} />
}
