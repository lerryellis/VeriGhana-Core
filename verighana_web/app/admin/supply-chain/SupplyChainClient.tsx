'use client'

import { useState, useMemo } from 'react'
import { Pagination } from '@/components/ui/Pagination'
import type { Supplier, InventoryStat, ProviderStat, DistributionStat } from './page'

interface Props {
  suppliers: Supplier[]
  inventory: InventoryStat
  providers: ProviderStat[]
  distribution: DistributionStat
}

type Tab = 'suppliers' | 'pipeline' | 'partners' | 'distribution'

const TABS: { key: Tab; label: string }[] = [
  { key: 'suppliers',    label: 'Suppliers' },
  { key: 'pipeline',     label: 'Pipeline & Inventory' },
  { key: 'partners',     label: 'Partners' },
  { key: 'distribution', label: 'Distribution' },
]

const VERDICT_COLOR: Record<string, string> = {
  VERIFIED:       'bg-green-500',
  PARTIAL:        'bg-amber-500',
  FALSE:          'bg-red-500',
  UNCORROBORATED: 'bg-slate-400',
}

const PAGE_SIZE = 20

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function daysSince(iso: string | null) {
  if (!iso) return null
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
}

export function SupplyChainClient({ suppliers, inventory, providers, distribution }: Props) {
  const [tab, setTab] = useState<Tab>('suppliers')

  // Suppliers state
  const [catFilter, setCatFilter] = useState('all')
  const [supplierSearch, setSupplierSearch] = useState('')
  const [supplierPage, setSupplierPage] = useState(1)

  const categories = useMemo(() => {
    const set = new Set(suppliers.map(s => s.category ?? 'Unknown'))
    return ['all', ...Array.from(set).sort()]
  }, [suppliers])

  const filteredSuppliers = useMemo(() => {
    const q = supplierSearch.toLowerCase()
    return suppliers.filter(s => {
      if (catFilter !== 'all' && (s.category ?? 'Unknown') !== catFilter) return false
      if (q && !s.source_name.toLowerCase().includes(q) && !s.official_url.toLowerCase().includes(q)) return false
      return true
    })
  }, [suppliers, catFilter, supplierSearch])

  const pagedSuppliers = filteredSuppliers.slice((supplierPage - 1) * PAGE_SIZE, supplierPage * PAGE_SIZE)

  const totalArticles = suppliers.reduce((s, x) => s + x.article_count, 0)
  const activeSuppliers = suppliers.filter(s => {
    const d = daysSince(s.latest_article)
    return d !== null && d < 7
  }).length

  // Distribution chart
  const maxDaily = Math.max(...distribution.daily.map(d => d.count), 1)

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <h1 className="font-display text-2xl font-bold text-[#0f2240]">Supply Chain Management</h1>
      <p className="text-sm text-slate-400">Data supply chain: sources → ingestion → AI processing → verification delivery</p>

      {/* Tab bar */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1">
        {TABS.map(t => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`flex-1 text-sm font-medium py-2.5 rounded-lg transition-colors ${
              tab === t.key ? 'bg-white text-[#0f2240] shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ═══════════════ SUPPLIERS TAB ═══════════════ */}
      {tab === 'suppliers' && (
        <div className="space-y-4">
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Total Sources',    value: suppliers.length,  color: 'text-[#0f2240]' },
              { label: 'Active (7d)',       value: activeSuppliers,   color: 'text-green-600' },
              { label: 'Total Articles',    value: totalArticles.toLocaleString(), color: 'text-blue-600' },
              { label: 'Categories',        value: categories.length - 1, color: 'text-slate-600' },
            ].map(k => (
              <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-4 text-center">
                <div className={`font-display text-2xl font-extrabold ${k.color}`}>{k.value}</div>
                <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
              </div>
            ))}
          </div>

          {/* Filters */}
          <div className="flex gap-3 flex-wrap">
            <input
              type="text"
              value={supplierSearch}
              onChange={e => { setSupplierSearch(e.target.value); setSupplierPage(1) }}
              placeholder="Search sources…"
              className="flex-1 min-w-[200px] bg-white border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400"
            />
            <select
              title="Filter by category"
              value={catFilter}
              onChange={e => { setCatFilter(e.target.value); setSupplierPage(1) }}
              className="bg-white border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400"
            >
              {categories.map(c => (
                <option key={c} value={c}>{c === 'all' ? 'All categories' : c}</option>
              ))}
            </select>
          </div>

          {/* Table */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    {['Source', 'Category', 'URL', 'Articles', 'Last Scraped', 'Status'].map(h => (
                      <th key={h} className="text-left text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pagedSuppliers.map(s => {
                    const days = daysSince(s.latest_article)
                    const status = days === null ? 'No data' : days < 2 ? 'Active' : days < 7 ? 'Recent' : 'Stale'
                    const statusColor = status === 'Active' ? 'bg-green-100 text-green-700' : status === 'Recent' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-600'
                    return (
                      <tr key={s.id} className="border-b border-slate-50 hover:bg-slate-50/50">
                        <td className="px-4 py-3 text-sm font-medium text-[#0f2240]">{s.source_name}</td>
                        <td className="px-4 py-3">
                          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{s.category ?? 'Unknown'}</span>
                        </td>
                        <td className="px-4 py-3 text-xs text-blue-600 truncate max-w-[200px]">
                          <a href={s.official_url} target="_blank" rel="noopener noreferrer" className="hover:underline">{s.official_url}</a>
                        </td>
                        <td className="px-4 py-3 text-sm font-mono-vg text-slate-700">{s.article_count}</td>
                        <td className="px-4 py-3 text-xs text-slate-500 font-mono-vg">{fmtDate(s.latest_article)}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor}`}>{status}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-4 pb-3">
              <Pagination page={supplierPage} totalPages={Math.ceil(filteredSuppliers.length / PAGE_SIZE)} onPageChange={setSupplierPage} totalItems={filteredSuppliers.length} pageSize={PAGE_SIZE} />
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════ PIPELINE & INVENTORY TAB ═══════════════ */}
      {tab === 'pipeline' && (
        <div className="space-y-4">
          {/* Pipeline flow diagram */}
          <div className="bg-white border border-slate-200 rounded-xl p-6">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Ingestion Pipeline Flow</p>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              {[
                { step: '1', label: 'RSS Feeds', desc: '3 RSS sources', color: 'bg-blue-500' },
                { step: '→', label: '', desc: '', color: '' },
                { step: '2', label: 'HTML Scraper', desc: `${suppliers.length} sites`, color: 'bg-blue-500' },
                { step: '→', label: '', desc: '', color: '' },
                { step: '3', label: 'Fact Entries', desc: `${inventory.total_articles.toLocaleString()} articles`, color: 'bg-green-500' },
                { step: '→', label: '', desc: '', color: '' },
                { step: '4', label: 'Embedder', desc: `${inventory.with_embeddings.toLocaleString()} embedded`, color: 'bg-purple-500' },
                { step: '→', label: '', desc: '', color: '' },
                { step: '5', label: 'Vector Search', desc: 'pgvector similarity', color: 'bg-teal-500' },
              ].map((s, i) =>
                s.step === '→' ? (
                  <span key={i} className="text-slate-300 text-lg hidden md:block">→</span>
                ) : (
                  <div key={i} className="flex items-center gap-3 bg-slate-50 rounded-lg px-4 py-3 flex-1 min-w-[140px]">
                    <div className={`w-8 h-8 rounded-full ${s.color} text-white text-xs font-bold flex items-center justify-center shrink-0`}>{s.step}</div>
                    <div>
                      <p className="text-sm font-medium text-[#0f2240]">{s.label}</p>
                      <p className="text-xs text-slate-400">{s.desc}</p>
                    </div>
                  </div>
                )
              )}
            </div>
          </div>

          {/* Inventory KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Total Articles',    value: inventory.total_articles.toLocaleString(), color: 'text-[#0f2240]' },
              { label: 'With Embeddings',   value: inventory.with_embeddings.toLocaleString(), color: 'text-purple-600' },
              { label: 'Embedding Rate',    value: inventory.total_articles > 0 ? `${Math.round(inventory.with_embeddings / inventory.total_articles * 100)}%` : '0%', color: 'text-green-600' },
              { label: 'Source Categories',  value: inventory.categories.length, color: 'text-slate-600' },
            ].map(k => (
              <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-4 text-center">
                <div className={`font-display text-2xl font-extrabold ${k.color}`}>{k.value}</div>
                <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
              </div>
            ))}
          </div>

          {/* Category breakdown + recent articles */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Articles by Source Category</p>
              <div className="space-y-2">
                {inventory.categories.map(c => {
                  const pct = inventory.total_articles > 0 ? (c.count / inventory.total_articles * 100) : 0
                  return (
                    <div key={c.category} className="flex items-center gap-3">
                      <span className="text-xs text-slate-600 w-24 shrink-0 truncate">{c.category}</span>
                      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-slate-400 font-mono-vg w-16 text-right">{c.count.toLocaleString()}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Recently Ingested</p>
              <div className="space-y-3">
                {inventory.recent_articles.map((a, i) => (
                  <div key={i} className="border-b border-slate-50 pb-2 last:border-0">
                    <p className="text-sm text-[#0f2240] font-medium truncate">{a.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-slate-400">{a.source_name}</span>
                      <span className="text-xs text-slate-300 font-mono-vg">{fmtDate(a.created_at)}</span>
                    </div>
                  </div>
                ))}
                {inventory.recent_articles.length === 0 && (
                  <p className="text-xs text-slate-400 italic">No articles ingested yet.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════ PARTNERS TAB ═══════════════ */}
      {tab === 'partners' && (
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-6">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">AI Provider Cascade</p>
            <p className="text-sm text-slate-500 mb-4">
              VeriGhana uses a multi-provider fallback cascade for maximum reliability. If the primary provider fails, the next one is tried automatically.
            </p>
            <div className="flex items-center gap-2 flex-wrap mb-6">
              {['Gemini 2.0 Flash', 'Gemini 1.5 Flash', 'Groq (Llama)', 'Cohere', 'OpenRouter', 'Heuristic'].map((name, i) => (
                <div key={name} className="flex items-center gap-2">
                  {i > 0 && <span className="text-slate-300">→</span>}
                  <span className={`text-xs font-medium px-3 py-1.5 rounded-full ${
                    i === 0 ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'bg-slate-100 text-slate-600 border border-slate-200'
                  }`}>
                    {name}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Provider usage table */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  {['Provider / Model', 'Requests', 'Avg Score', 'Avg Response Time', 'Share'].map(h => (
                    <th key={h} className="text-left text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-wider px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {providers.length === 0 ? (
                  <tr><td colSpan={5} className="text-center text-slate-400 text-sm py-10">No verification data yet.</td></tr>
                ) : providers.map(p => {
                  const share = distribution.total_verifications > 0 ? (p.count / distribution.total_verifications * 100).toFixed(1) : '0'
                  return (
                    <tr key={p.model} className="border-b border-slate-50 hover:bg-slate-50/50">
                      <td className="px-4 py-3 text-sm font-medium text-[#0f2240]">{p.model}</td>
                      <td className="px-4 py-3 text-sm font-mono-vg text-slate-700">{p.count.toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono-vg text-slate-700">{p.avg_score}</span>
                          <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500 rounded-full" style={{ width: `${p.avg_score}%` }} />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm font-mono-vg text-slate-700">{p.avg_ms.toLocaleString()}ms</td>
                      <td className="px-4 py-3 text-sm font-mono-vg text-slate-500">{share}%</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══════════════ DISTRIBUTION TAB ═══════════════ */}
      {tab === 'distribution' && (
        <div className="space-y-4">
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Total Verifications', value: distribution.total_verifications.toLocaleString(), color: 'text-[#0f2240]' },
              { label: 'Avg Confidence',       value: `${distribution.avg_score}/100`, color: 'text-blue-600' },
              { label: 'Avg Response',          value: `${distribution.avg_ms.toLocaleString()}ms`, color: 'text-green-600' },
              { label: 'Verdict Types',         value: distribution.verdicts.length, color: 'text-slate-600' },
            ].map(k => (
              <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-4 text-center">
                <div className={`font-display text-2xl font-extrabold ${k.color}`}>{k.value}</div>
                <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
              </div>
            ))}
          </div>

          {/* Verdict breakdown + daily chart */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Verdict Breakdown</p>
              {distribution.verdicts.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No data yet.</p>
              ) : (
                <div className="space-y-3">
                  {distribution.verdicts.map(v => {
                    const pct = distribution.total_verifications > 0 ? (v.count / distribution.total_verifications * 100) : 0
                    return (
                      <div key={v.verdict} className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full shrink-0 ${VERDICT_COLOR[v.verdict] ?? 'bg-slate-300'}`} />
                        <span className="text-sm text-slate-600 w-32 shrink-0">{v.verdict}</span>
                        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${VERDICT_COLOR[v.verdict] ?? 'bg-slate-300'}`} style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-slate-400 font-mono-vg w-20 text-right">{v.count} ({pct.toFixed(1)}%)</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Daily Verifications (30d)</p>
              {distribution.daily.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No data yet.</p>
              ) : (
                <div className="flex items-end gap-1 h-28">
                  {distribution.daily.map(d => (
                    <div key={d.day} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                      <span className="text-[0.5rem] text-slate-400 font-mono-vg hidden lg:block">{d.count || ''}</span>
                      <div
                        className="w-full bg-blue-500 rounded-t-sm min-h-[2px] transition-all"
                        style={{ height: `${(d.count / maxDaily) * 100}%` }}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Delivery explanation */}
          <div className="bg-white border border-slate-200 rounded-xl p-6">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Delivery Process</p>
            <div className="grid md:grid-cols-4 gap-4">
              {[
                { step: '1', label: 'User submits claim', desc: 'Via web app or API' },
                { step: '2', label: 'Vector search', desc: 'Find relevant articles from fact_entries using pgvector' },
                { step: '3', label: 'AI verification', desc: 'Multi-provider cascade analyses claim against sources' },
                { step: '4', label: 'Verdict delivered', desc: 'Score (0–100), verdict, explanation, and source notes' },
              ].map(s => (
                <div key={s.step} className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-[#0f2240] text-white text-xs font-bold flex items-center justify-center shrink-0">{s.step}</div>
                  <div>
                    <p className="text-sm font-medium text-[#0f2240]">{s.label}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{s.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
