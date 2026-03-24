'use client'

import { useState } from 'react'

type Stats = {
  articles: number
  sources: number
  tickets: number
  users: number
  payments: number
  revenue_usd: number
  pro_subs: number
  inst_subs: number
} | null

interface Props {
  stats: Stats
  adminKey: string
  apiUrl: string
}

type TriggerKey = 'rss' | 'html' | 'embed'

export function AdminClient({ stats, adminKey, apiUrl }: Props) {
  const [triggers, setTriggers] = useState<Record<TriggerKey, 'idle' | 'loading' | 'done' | 'error'>>({
    rss: 'idle', html: 'idle', embed: 'idle',
  })

  async function trigger(key: TriggerKey, path: string) {
    setTriggers(t => ({ ...t, [key]: 'loading' }))
    try {
      const res = await fetch(`${apiUrl}${path}`, {
        method: 'POST',
        headers: { 'X-Admin-Key': adminKey },
      })
      setTriggers(t => ({ ...t, [key]: res.ok ? 'done' : 'error' }))
    } catch {
      setTriggers(t => ({ ...t, [key]: 'error' }))
    }
  }

  const kpis = stats
    ? [
        { label: 'Total Users',     value: stats.users.toLocaleString(),            color: 'text-[#0f2240]' },
        { label: 'Articles',        value: stats.articles.toLocaleString(),          color: 'text-blue-600' },
        { label: 'Pro Subs',        value: stats.pro_subs.toLocaleString(),          color: 'text-blue-600' },
        { label: 'Institutional',   value: stats.inst_subs.toLocaleString(),         color: 'text-teal-600' },
        { label: 'Revenue',         value: `$${stats.revenue_usd.toFixed(2)}`,       color: 'text-green-600' },
        { label: 'Payments',        value: stats.payments.toLocaleString(),          color: 'text-green-600' },
        { label: 'Open Tickets',    value: stats.tickets.toLocaleString(),           color: 'text-amber-600' },
        { label: 'Trusted Sources', value: stats.sources.toLocaleString(),           color: 'text-slate-600' },
      ]
    : []

  const PIPELINE: { key: TriggerKey; label: string; desc: string; path: string }[] = [
    { key: 'rss',   label: 'RSS Scraper',  desc: 'Parse 3 RSS feeds → fact_entries',       path: '/scrape/rss' },
    { key: 'html',  label: 'HTML Scraper', desc: 'Scrape 65+ Ghanaian news/gov sites',     path: '/scrape/html' },
    { key: 'embed', label: 'Embedder',     desc: 'Generate Gemini embeddings (pgvector)',  path: '/embed' },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="font-display text-2xl font-bold text-[#0f2240]">Admin Dashboard</h1>

      {/* KPI grid */}
      {stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {kpis.map(k => (
            <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-4 text-center">
              <div className={`font-display text-2xl font-extrabold ${k.color}`}>{k.value}</div>
              <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm px-4 py-3 rounded-xl">
          Could not load stats — check that the FastAPI backend is running and ADMIN_API_KEY is set.
        </div>
      )}

      {/* Pipeline triggers */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Ingestion Pipeline</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {PIPELINE.map(p => {
            const state = triggers[p.key]
            return (
              <div key={p.key} className="border border-slate-200 rounded-xl p-4 flex flex-col gap-3">
                <div>
                  <p className="font-display font-bold text-[#0f2240] text-sm">{p.label}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{p.desc}</p>
                </div>
                <button
                  type="button"
                  onClick={() => trigger(p.key, p.path)}
                  disabled={state === 'loading'}
                  className={`text-xs font-medium px-4 py-2 rounded-lg transition-colors disabled:cursor-not-allowed ${
                    state === 'done'    ? 'bg-green-100 text-green-700' :
                    state === 'error'   ? 'bg-red-100 text-red-600' :
                    state === 'loading' ? 'bg-slate-100 text-slate-400' :
                    'bg-blue-600 hover:bg-blue-500 text-white'
                  }`}
                >
                  {state === 'loading' ? 'Running…' : state === 'done' ? '✓ Triggered' : state === 'error' ? '✗ Error' : 'Run Now'}
                </button>
              </div>
            )
          })}
        </div>
        <p className="text-xs text-slate-400 mt-3 font-mono-vg">
          Pipeline also runs automatically via GitHub Actions every 6 hours.
        </p>
      </div>

      {/* Quick links */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Quick Links</p>
        <div className="flex flex-wrap gap-3">
          {[
            { label: 'Support Tickets',  href: '/admin/tickets' },
            { label: 'Site Tester',      href: '/admin/tester' },
          ].map(l => (
            <a
              key={l.href}
              href={l.href}
              className="bg-slate-50 hover:bg-slate-100 border border-slate-200 text-[#0f2240] text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
            >
              {l.label} →
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
