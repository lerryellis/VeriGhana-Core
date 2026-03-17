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

  // KPI counts
  const all     = records ?? []
  const verified = all.filter(r => r.verdict === 'VERIFIED').length
  const falseCount = all.filter(r => r.verdict === 'FALSE').length
  const partial  = all.filter(r => r.verdict === 'PARTIAL').length
  const avgScore = all.length > 0
    ? Math.round(all.reduce((s, r) => s + (r.score ?? 0), 0) / all.length)
    : 0

  return (
    <HistoryClient
      records={all}
      stats={{ total: all.length, verified, falseCount, partial, avgScore }}
    />
  )
}
