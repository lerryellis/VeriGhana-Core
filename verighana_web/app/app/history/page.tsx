import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { HistoryClient } from './HistoryClient'

export type VerificationRecord = {
  id: number
  input_claim: string
  score: number
  verdict: string
  explanation: string | null
  matched_sources: string | null
  model_used: string | null
  created_at: string
}

export default async function HistoryPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: records } = await supabase
    .from('verification_log')
    .select('id, input_claim, score, verdict, explanation, matched_sources, model_used, created_at')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .limit(100)

  return <HistoryClient records={records ?? []} />
}
