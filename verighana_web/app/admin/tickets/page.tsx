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
  const tickets = await fetchTickets()
  return <TicketsClient tickets={tickets} />
}
