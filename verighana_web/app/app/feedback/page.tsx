import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { FeedbackClient } from './FeedbackClient'

export default async function FeedbackPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles').select('tier').eq('user_id', user.id).single()

  const { data: existing } = await supabase
    .from('app_feedback').select('id, created_at')
    .eq('user_id', user.id).order('created_at', { ascending: false }).limit(1).single()

  return (
    <FeedbackClient
      userEmail={user.email ?? ''}
      userTier={profile?.tier ?? 'free'}
      priorSubmission={existing ?? null}
    />
  )
}
