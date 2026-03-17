import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { AccountClient } from './AccountClient'

export type UserProfile = {
  user_id: string
  email: string
  full_name: string | null
  phone: string | null
  organisation: string | null
  country: string | null
  tier: string
  role: string
  subscription_status: string | null
  subscription_expires_at: string | null
  cancelled_at: string | null
  daily_queries_used: number
  created_at: string
}

export default async function AccountPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('*')
    .eq('user_id', user.id)
    .single()

  const { count: totalVerifications } = await supabase
    .from('verification_log')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', user.id)

  return (
    <AccountClient
      profile={profile as UserProfile}
      authEmail={user.email ?? ''}
      totalVerifications={totalVerifications ?? 0}
    />
  )
}
