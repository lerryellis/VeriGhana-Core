'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { StatsResponse } from '@/types/api'

export function StatsBar() {
  const [stats, setStats] = useState<StatsResponse | null>(null)

  useEffect(() => {
    api.stats().then(setStats).catch(() => {})
  }, [])

  const fmt = (n?: number) => n && n > 0 ? n.toLocaleString() : '—'

  const fmtDate = (iso?: string | null) => {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    } catch {
      return '—'
    }
  }

  return (
    <div className="bg-[#0f2240] border-y border-white/[0.08] px-[5%] py-5 grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
      {[
        { num: fmt(stats?.total_articles),      label: 'Articles Indexed' },
        { num: fmt(stats?.sources_tracked),      label: 'Trusted Sources' },
        { num: fmt(stats?.total_verifications),  label: 'Claims Checked' },
        { num: fmtDate(stats?.last_scrape),      label: 'Last Updated' },
      ].map(({ num, label }) => (
        <div key={label}>
          <div className={`font-display text-2xl font-bold ${stats ? 'text-white' : 'text-white/30 animate-pulse'}`}>{num}</div>
          <div className="text-xs text-slate-400 mt-0.5">{label}</div>
        </div>
      ))}
    </div>
  )
}
