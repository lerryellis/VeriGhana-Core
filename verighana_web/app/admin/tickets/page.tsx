import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { TicketsClient } from './TicketsClient'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

export type AdminTicket = {
  id: string
  created_at: string
  updated_at: string
  name: string | null
  email: string | null
  category: string | null
  subject: string
  message: string | null
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  user_followup?: string | null
  user_followup_read?: boolean
}

async function fetchTickets(): Promise<AdminTicket[]> {
  try {
    const res = await fetch(`${API_URL}/admin/tickets?limit=200`, {
      headers: { 'X-Admin-Key': ADMIN_KEY },
      cache: 'no-store',
    })
    if (!res.ok) return []
    const data = await res.json() as { tickets: AdminTicket[] }
    return data.tickets ?? []
  } catch {
    return []
  }
}

export default async function TicketsPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('role')
    .eq('user_id', user.id)
    .single()

  const adminEmails = (process.env.ADMIN_EMAIL ?? '').split(',').map(e => e.trim().toLowerCase())
  const role = adminEmails.includes((user.email ?? '').toLowerCase()) ? 'admin' : (profile?.role ?? 'user')

  const tickets = await fetchTickets()
  return <TicketsClient tickets={tickets} adminEmail={user.email ?? ''} adminRole={role as 'admin' | 'staff'} />
}
