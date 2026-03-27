import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { FeedbackAdminClient } from './FeedbackAdminClient'

export type FeedbackRow = {
  id: string
  created_at: string
  user_email: string | null
  user_tier: string | null
  respondent_role: string | null
  use_frequency: string | null
  use_case: string | null
  nps_score: number | null
  rating_accuracy: number | null
  rating_usability: number | null
  rating_speed: number | null
  rating_reliability: number | null
  rating_value: number | null
  likert_easy_to_use: number | null
  likert_trust_results: number | null
  likert_improves_work: number | null
  likert_recommend: number | null
  most_useful: string | null
  biggest_challenge: string | null
  feature_request: string | null
  general_comments: string | null
}

export default async function AdminFeedbackPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: rows } = await supabase
    .from('app_feedback')
    .select('*')
    .order('created_at', { ascending: false })

  return <FeedbackAdminClient rows={(rows ?? []) as FeedbackRow[]} />
}
