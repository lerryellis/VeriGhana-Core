import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { api } from '@/lib/api'
import { VerifyClient } from './VerifyClient'

type Tier = 'free' | 'pro' | 'institutional'

const ALL_MODELS_FALLBACK = [
  { id: 'gemini-2.0-flash',                   name: 'Gemini 2.0 Flash',          tier_required: 'free' },
  { id: 'gemini-2.0-flash-lite',              name: 'Gemini 2.0 Flash Lite',     tier_required: 'free' },
  { id: 'gemini-1.5-flash',                   name: 'Gemini 1.5 Flash',          tier_required: 'free' },
  { id: 'gemini-1.5-flash-8b',               name: 'Gemini 1.5 Flash 8B',       tier_required: 'free' },
  { id: 'groq:llama-3.3-70b-versatile',      name: 'Groq Llama 3.3 70B',        tier_required: 'pro' },
  { id: 'groq:llama-3.1-8b-instant',         name: 'Groq Llama 3.1 8B Fast',    tier_required: 'pro' },
  { id: 'cohere:command-r-plus',             name: 'Cohere Command-R+',         tier_required: 'pro' },
  { id: 'cohere:command-r',                  name: 'Cohere Command-R',          tier_required: 'pro' },
  { id: 'openrouter:llama-3.3-70b',          name: 'OpenRouter Llama 3.3 70B',  tier_required: 'pro' },
]

async function getModels(token: string, tier: Tier) {
  try {
    const data = await api.models(token)
    if (data.models && data.models.length > 0) return data.models
  } catch {
    // fall through to local fallback
  }
  // Fallback: filter by tier locally
  if (tier === 'free') return ALL_MODELS_FALLBACK.slice(0, 4)
  return ALL_MODELS_FALLBACK
}

export default async function VerifyPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('tier, role, daily_queries_used')
    .eq('user_id', user.id)
    .single()

  const tier = (profile?.tier ?? 'free') as Tier
  const session = await supabase.auth.getSession()
  const accessToken = session.data.session?.access_token ?? ''

  const models = await getModels(accessToken, tier)
  const dailyLimit = tier === 'free' ? 5 : null
  const used = profile?.daily_queries_used ?? 0

  return (
    <VerifyClient
      userId={user.id}
      accessToken={accessToken}
      tier={tier}
      models={models}
      used={used}
      dailyLimit={dailyLimit}
    />
  )
}
