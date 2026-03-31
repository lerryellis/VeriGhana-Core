import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { BillingClient } from './BillingClient'
import type { UserProfile } from '../account/page'

export type PaymentRecord = {
  id: string
  order_ref: string | null
  plan: string
  amount: number
  currency: string
  status: string
  payment_method: string | null
  created_at: string
}

export default async function BillingPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('*')
    .eq('user_id', user.id)
    .single()

  const { data: payments } = await supabase
    .from('payments')
    .select('id, order_ref, plan, amount, currency, status, payment_method, created_at')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .limit(10)

  const session = await supabase.auth.getSession()

  const adminEmails = (process.env.ADMIN_EMAIL ?? '').split(',').map(e => e.trim().toLowerCase())
  const isEnvAdmin  = adminEmails.includes((user.email ?? '').toLowerCase())
  const role        = isEnvAdmin ? 'admin' : (profile?.role ?? 'user')

  return (
    <BillingClient
      profile={profile as UserProfile | null}
      authEmail={user.email ?? ''}
      accessToken={session.data.session?.access_token ?? ''}
      payments={(payments ?? []) as PaymentRecord[]}
      role={role}
    />
  )
}
