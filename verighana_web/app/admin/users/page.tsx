import { UsersClient } from './UsersClient'

const API_URL   = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

export type AdminUser = {
  user_id: string
  email: string
  full_name: string | null
  phone: string | null
  organisation: string | null
  country: string | null
  tier: 'free' | 'pro' | 'institutional'
  role: string
  subscription_status: string | null
  subscription_expires_at: string | null
  daily_queries_used: number
  created_at: string
}

async function fetchUsers(): Promise<AdminUser[]> {
  try {
    const res = await fetch(`${API_URL}/admin/users?limit=1000`, {
      headers: { 'X-Admin-Key': ADMIN_KEY },
      cache: 'no-store',
    })
    if (!res.ok) return []
    const data = await res.json() as { users: AdminUser[] }
    return data.users ?? []
  } catch {
    return []
  }
}

export default async function UsersPage() {
  const users = await fetchUsers()
  return <UsersClient users={users} />
}
