import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { ContactClient } from './ContactClient'

export default async function ContactPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('full_name, email, tier')
    .eq('user_id', user.id)
    .single()

  // Load open tickets for this user
  const { data: tickets } = await supabase
    .from('support_tickets')
    .select('id, subject, status, created_at, updated_at, admin_reply, admin_reply_read, user_followup')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .limit(20)

  const session = await supabase.auth.getSession()

  return (
    <ContactClient
      authEmail={user.email ?? ''}
      fullName={profile?.full_name ?? ''}
      tier={(profile?.tier ?? 'free') as 'free' | 'pro' | 'institutional'}
      accessToken={session.data.session?.access_token ?? ''}
      tickets={(tickets ?? []) as SupportTicket[]}
    />
  )
}

export type SupportTicket = {
  id: string
  subject: string
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  created_at: string
  updated_at: string
  admin_reply?: string | null
  admin_reply_read?: boolean
  user_followup?: string | null
}
