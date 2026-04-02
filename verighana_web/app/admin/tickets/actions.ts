'use server'

const API_URL   = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

export async function markFollowupRead(ticketId: string): Promise<boolean> {
  const res = await fetch(`${API_URL}/admin/tickets/${ticketId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
    body: JSON.stringify({ user_followup_read: true }),
  })
  return res.ok
}

export async function updateTicketStatus(
  ticketId: string,
  status: string
): Promise<boolean> {
  const res = await fetch(`${API_URL}/admin/tickets/${ticketId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
    body: JSON.stringify({ status }),
  })
  return res.ok
}

export async function sendTicketReply(params: {
  ticketId: string
  toEmail: string | null
  toName: string | null
  subject: string
  body: string
  newStatus: string
}): Promise<{ ok: boolean; saved?: boolean; emailSent?: boolean; emailError?: string; error?: string }> {
  try {
    const res = await fetch(`${API_URL}/support/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
      body: JSON.stringify({
        to_email:   params.toEmail,
        to_name:    params.toName,
        subject:    params.subject,
        body:       params.body,
        ticket_id:  params.ticketId,
        new_status: params.newStatus,
      }),
    })
    if (!res.ok) return { ok: false, error: `Server error (${res.status})` }
    const data = await res.json() as { saved: boolean; email_sent: boolean; email_error?: string }
    return { ok: true, saved: data.saved, emailSent: data.email_sent, emailError: data.email_error }
  } catch {
    return { ok: false, error: 'Network error' }
  }
}
