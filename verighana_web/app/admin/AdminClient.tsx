'use client'

import { useState, useMemo } from 'react'
import type { CrmUser } from './page'

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
  crmUsers: CrmUser[]
}

type TriggerKey = 'rss' | 'html' | 'embed'

export function AdminClient({ stats, adminKey, apiUrl, crmUsers }: Props) {
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

  // ── CRM computed data ─────────────────────────────────────────────────
  const now = new Date()
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 86400000)
  const sevenDaysAgo  = new Date(now.getTime() - 7 * 86400000)

  const newThisMonth = crmUsers.filter(u => new Date(u.created_at) >= thirtyDaysAgo).length
  const newThisWeek  = crmUsers.filter(u => new Date(u.created_at) >= sevenDaysAgo).length
  const paying       = crmUsers.filter(u => u.tier !== 'free').length
  const active       = crmUsers.filter(u => u.subscription_status === 'active' || !u.subscription_status).length
  const churned      = crmUsers.filter(u => u.subscription_status === 'cancelled' || u.subscription_status === 'expired').length
  const conversionRate = crmUsers.length > 0 ? ((paying / crmUsers.length) * 100).toFixed(1) : '0'

  // Signup chart: last 12 weeks
  const signupChart = useMemo(() => {
    const weeks: { label: string; count: number }[] = []
    for (let i = 11; i >= 0; i--) {
      const weekStart = new Date(now.getTime() - (i + 1) * 7 * 86400000)
      const weekEnd   = new Date(now.getTime() - i * 7 * 86400000)
      const count     = crmUsers.filter(u => {
        const d = new Date(u.created_at)
        return d >= weekStart && d < weekEnd
      }).length
      weeks.push({
        label: weekStart.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }),
        count,
      })
    }
    return weeks
  }, [crmUsers])

  const maxSignup = Math.max(...signupChart.map(w => w.count), 1)

  // Segmentation
  const segments = useMemo(() => {
    const powerUsers = crmUsers.filter(u => u.daily_queries_used >= 3 || u.tier !== 'free').length
    const newUsers   = crmUsers.filter(u => new Date(u.created_at) >= sevenDaysAgo).length
    const atRisk     = crmUsers.filter(u =>
      u.tier !== 'free' && (u.subscription_status === 'cancelled' || u.daily_queries_used === 0)
    ).length
    const casual     = crmUsers.length - powerUsers - newUsers - atRisk
    return [
      { label: 'Power Users',   count: powerUsers, color: 'bg-blue-500',  desc: 'Active or paid' },
      { label: 'New (7d)',       count: newUsers,   color: 'bg-green-500', desc: 'Signed up this week' },
      { label: 'At Risk',       count: atRisk,      color: 'bg-red-500',   desc: 'Paid but inactive/cancelled' },
      { label: 'Casual',        count: Math.max(casual, 0), color: 'bg-slate-400', desc: 'Low engagement free tier' },
    ]
  }, [crmUsers])

  const kpis = stats
    ? [
        { label: 'Total Users',     value: stats.users.toLocaleString(),    color: 'text-[#0f2240]' },
        { label: 'Articles',        value: stats.articles.toLocaleString(), color: 'text-blue-600' },
        { label: 'Pro Subs',        value: stats.pro_subs.toLocaleString(), color: 'text-blue-600' },
        { label: 'Institutional',   value: stats.inst_subs.toLocaleString(), color: 'text-teal-600' },
        { label: 'Revenue',         value: `$${stats.revenue_usd.toFixed(2)}`, color: 'text-green-600' },
        { label: 'Payments',        value: stats.payments.toLocaleString(), color: 'text-green-600' },
        { label: 'Open Tickets',    value: stats.tickets.toLocaleString(), color: 'text-amber-600' },
        { label: 'Trusted Sources', value: stats.sources.toLocaleString(), color: 'text-slate-600' },
      ]
    : []

  const PIPELINE: { key: TriggerKey; label: string; desc: string; path: string }[] = [
    { key: 'rss',   label: 'RSS Scraper',  desc: 'Parse 3 RSS feeds → fact_entries',      path: '/scrape/rss' },
    { key: 'html',  label: 'HTML Scraper', desc: 'Scrape 65+ Ghanaian news/gov sites',    path: '/scrape/html' },
    { key: 'embed', label: 'Embedder',     desc: 'Generate Gemini embeddings (pgvector)', path: '/embed' },
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

      {/* ── CRM Overview ───────────────────────────────────────────────── */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">CRM Overview</p>

        {/* CRM KPI row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {[
            { label: 'New (30d)',      value: newThisMonth, color: 'text-green-600' },
            { label: 'New (7d)',       value: newThisWeek,  color: 'text-green-600' },
            { label: 'Paying',         value: paying,       color: 'text-blue-600' },
            { label: 'Conversion',     value: `${conversionRate}%`, color: 'text-blue-600' },
            { label: 'Churned',        value: churned,      color: churned > 0 ? 'text-red-500' : 'text-slate-400' },
          ].map(k => (
            <div key={k.label} className="bg-slate-50 rounded-lg px-3 py-3 text-center">
              <div className={`font-display text-lg font-bold ${k.color}`}>{k.value}</div>
              <div className="text-[0.65rem] text-slate-400 mt-0.5">{k.label}</div>
            </div>
          ))}
        </div>

        {/* Signup trend chart (12 weeks) */}
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-3">Weekly Signups (12 weeks)</p>
        <div className="flex items-end gap-1.5 h-24 mb-6">
          {signupChart.map(w => (
            <div key={w.label} className="flex-1 flex flex-col items-center gap-1 min-w-0">
              <span className="text-[0.55rem] text-slate-400 font-mono-vg hidden md:block">{w.count || ''}</span>
              <div
                className="w-full bg-blue-500 rounded-t-sm min-h-[2px] transition-all"
                style={{ height: `${(w.count / maxSignup) * 100}%` }}
              />
              <span className="text-[0.5rem] text-slate-400 font-mono-vg truncate w-full text-center hidden lg:block">{w.label}</span>
            </div>
          ))}
        </div>

        {/* Customer Segments */}
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-3">Customer Segments</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {segments.map(s => (
            <div key={s.label} className="flex items-center gap-3 bg-slate-50 rounded-lg px-3 py-3">
              <div className={`w-3 h-3 rounded-full shrink-0 ${s.color}`} />
              <div>
                <div className="font-display font-bold text-[#0f2240] text-sm">{s.count}</div>
                <div className="text-[0.6rem] text-slate-400">{s.label}</div>
                <div className="text-[0.55rem] text-slate-300">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

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
            { label: 'Users',            href: '/admin/users' },
            { label: 'Reports',          href: '/admin/reports' },
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
