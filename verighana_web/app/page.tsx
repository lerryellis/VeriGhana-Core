import { api } from '@/lib/api'
import { Nav }          from '@/components/landing/Nav'
import { Hero }         from '@/components/landing/Hero'
import { StatsBar }     from '@/components/landing/StatsBar'
import { SourcesStrip } from '@/components/landing/SourcesStrip'
import { HowItWorks }   from '@/components/landing/HowItWorks'
import { Pricing }      from '@/components/landing/Pricing'
import { Ticker }       from '@/components/landing/Ticker'
import { Footer }       from '@/components/landing/Footer'

async function getModels() {
  try {
    const data = await api.models()
    return data.models
  } catch {
    return [
      { id: 'gemini-2.0-flash',      name: 'Gemini 2.0 Flash',      provider: 'google', tier_required: 'free' },
      { id: 'gemini-2.0-flash-lite', name: 'Gemini 2.0 Flash Lite', provider: 'google', tier_required: 'free' },
      { id: 'gemini-1.5-flash',      name: 'Gemini 1.5 Flash',      provider: 'google', tier_required: 'free' },
      { id: 'gemini-1.5-flash-8b',   name: 'Gemini 1.5 Flash 8B',   provider: 'google', tier_required: 'free' },
    ]
  }
}

export default async function LandingPage() {
  const models = await getModels()

  return (
    <div className="noise-overlay min-h-screen flex flex-col">
      <Nav />
      <Hero models={models} />
      <StatsBar />
      <SourcesStrip />
      <HowItWorks />
      <Pricing />
      <Ticker />
      <Footer />
    </div>
  )
}
