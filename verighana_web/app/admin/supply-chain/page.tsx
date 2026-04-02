import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { SupplyChainClient } from './SupplyChainClient'

export type Supplier = {
  id: string
  source_name: string
  official_url: string
  scrape_url: string | null
  category: string | null
  article_count: number
  latest_article: string | null
}

export type InventoryStat = {
  total_articles: number
  with_embeddings: number
  categories: { category: string; count: number }[]
  recent_articles: { title: string; source_name: string; created_at: string }[]
}

export type ProviderStat = {
  model: string
  count: number
  avg_score: number
  avg_ms: number
}

export type DistributionStat = {
  total_verifications: number
  verdicts: { verdict: string; count: number }[]
  avg_score: number
  avg_ms: number
  daily: { day: string; count: number }[]
}

export default async function SupplyChainPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  // ── Suppliers: trusted_sources with article counts ─────────────────
  const { data: sources } = await supabase
    .from('trusted_sources')
    .select('id, source_name, official_url, scrape_url, category')
    .order('source_name')

  // Count articles per source
  const { data: articleCounts } = await supabase
    .from('fact_entries')
    .select('source_id')

  const countMap: Record<string, number> = {}
  for (const a of articleCounts ?? []) {
    countMap[a.source_id] = (countMap[a.source_id] ?? 0) + 1
  }

  // Latest article per source
  const { data: latestArticles } = await supabase
    .from('fact_entries')
    .select('source_id, created_at')
    .order('created_at', { ascending: false })

  const latestMap: Record<string, string> = {}
  for (const a of latestArticles ?? []) {
    if (!latestMap[a.source_id]) latestMap[a.source_id] = a.created_at
  }

  const suppliers: Supplier[] = (sources ?? []).map(s => ({
    ...s,
    article_count: countMap[s.id] ?? 0,
    latest_article: latestMap[s.id] ?? null,
  }))

  // ── Inventory: fact_entries stats ──────────────────────────────────
  const { count: totalArticles } = await supabase
    .from('fact_entries').select('id', { count: 'exact', head: true })

  const { count: withEmbeddings } = await supabase
    .from('fact_entries').select('id', { count: 'exact', head: true })
    .not('content_embedding', 'is', null)

  // Category breakdown from sources
  const catMap: Record<string, number> = {}
  for (const s of suppliers) {
    const cat = s.category ?? 'Unknown'
    catMap[cat] = (catMap[cat] ?? 0) + s.article_count
  }
  const categories = Object.entries(catMap).map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)

  // Recent articles
  const { data: recentRaw } = await supabase
    .from('fact_entries')
    .select('title, source_id, created_at')
    .order('created_at', { ascending: false })
    .limit(10)

  const sourceNameMap: Record<string, string> = {}
  for (const s of sources ?? []) sourceNameMap[s.id] = s.source_name

  const recentArticles = (recentRaw ?? []).map(a => ({
    title: a.title,
    source_name: sourceNameMap[a.source_id] ?? 'Unknown',
    created_at: a.created_at,
  }))

  const inventory: InventoryStat = {
    total_articles: totalArticles ?? 0,
    with_embeddings: withEmbeddings ?? 0,
    categories,
    recent_articles: recentArticles,
  }

  // ── Partners: AI provider usage from vg_usage_logs ────────────────
  const { data: usageLogs } = await supabase
    .from('vg_usage_logs')
    .select('model_used, score, processing_ms')

  const providerMap: Record<string, { count: number; totalScore: number; totalMs: number }> = {}
  for (const log of usageLogs ?? []) {
    const model = log.model_used ?? 'Unknown'
    if (!providerMap[model]) providerMap[model] = { count: 0, totalScore: 0, totalMs: 0 }
    providerMap[model].count++
    providerMap[model].totalScore += log.score ?? 0
    providerMap[model].totalMs += log.processing_ms ?? 0
  }

  const providers: ProviderStat[] = Object.entries(providerMap)
    .map(([model, d]) => ({
      model,
      count: d.count,
      avg_score: d.count > 0 ? Math.round(d.totalScore / d.count) : 0,
      avg_ms: d.count > 0 ? Math.round(d.totalMs / d.count) : 0,
    }))
    .sort((a, b) => b.count - a.count)

  // ── Distribution: verification delivery stats ─────────────────────
  const totalVerifications = usageLogs?.length ?? 0
  const avgScore = totalVerifications > 0
    ? Math.round((usageLogs ?? []).reduce((s, l) => s + (l.score ?? 0), 0) / totalVerifications)
    : 0
  const avgMs = totalVerifications > 0
    ? Math.round((usageLogs ?? []).reduce((s, l) => s + (l.processing_ms ?? 0), 0) / totalVerifications)
    : 0

  // Verdicts
  const { data: verdictLogs } = await supabase
    .from('vg_usage_logs')
    .select('verdict')

  const verdictMap: Record<string, number> = {}
  for (const v of verdictLogs ?? []) {
    const vd = v.verdict ?? 'UNKNOWN'
    verdictMap[vd] = (verdictMap[vd] ?? 0) + 1
  }
  const verdicts = Object.entries(verdictMap).map(([verdict, count]) => ({ verdict, count }))
    .sort((a, b) => b.count - a.count)

  // Daily verifications (last 30 days)
  const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString()
  const { data: recentLogs } = await supabase
    .from('vg_usage_logs')
    .select('created_at')
    .gte('created_at', thirtyDaysAgo)

  const dailyMap: Record<string, number> = {}
  for (const l of recentLogs ?? []) {
    const day = l.created_at?.slice(0, 10)
    if (day) dailyMap[day] = (dailyMap[day] ?? 0) + 1
  }
  const daily = Object.entries(dailyMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, count]) => ({ day, count }))

  const distribution: DistributionStat = {
    total_verifications: totalVerifications,
    verdicts,
    avg_score: avgScore,
    avg_ms: avgMs,
    daily,
  }

  return (
    <SupplyChainClient
      suppliers={suppliers}
      inventory={inventory}
      providers={providers}
      distribution={distribution}
    />
  )
}
