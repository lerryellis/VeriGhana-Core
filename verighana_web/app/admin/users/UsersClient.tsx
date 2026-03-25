'use client'

import { useState, useMemo, useTransition } from 'react'
import type { AdminUser } from './page'
import { deleteUser, changeUserPlan } from './actions'

interface Props { users: AdminUser[] }

const TIER_STYLES = {
  free:          'bg-slate-100 text-slate-500',
  pro:           'bg-blue-100 text-blue-700',
  institutional: 'bg-purple-100 text-purple-700',
}

function toCSV(rows: AdminUser[]): string {
  const headers = ['Name','Email','Tier','Role','Organisation','Country','Sub Status','Queries Used','Joined']
  const lines = rows.map(u => [
    u.full_name ?? '', u.email, u.tier, u.role,
    u.organisation ?? '', u.country ?? '',
    u.subscription_status ?? '', u.daily_queries_used,
    new Date(u.created_at).toISOString().slice(0,10),
  ].map(v => `"${String(v).replace(/"/g,'""')}"`).join(','))
  return [headers.join(','), ...lines].join('\n')
}

function downloadCSV(content: string) {
  const blob = new Blob([content], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: 'verighana-users.csv' })
  a.click()
  URL.revokeObjectURL(url)
}

function UserRow({ u, onDeleted }: { u: AdminUser; onDeleted: (id: string) => void }) {
  const [isPending, startTransition] = useTransition()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [tier, setTier] = useState<AdminUser['tier']>(u.tier)
  const [planPending, startPlanTransition] = useTransition()
  const [err, setErr] = useState<string | null>(null)

  function handlePlanChange(newTier: AdminUser['tier']) {
    const prev = tier
    setTier(newTier)
    startPlanTransition(async () => {
      const result = await changeUserPlan(u.user_id, newTier)
      if (result.error) { setTier(prev); setErr(result.error) }
    })
  }

  function handleDelete() {
    startTransition(async () => {
      const result = await deleteUser(u.user_id)
      if (result.error) { setErr(result.error); setConfirmDelete(false) }
      else onDeleted(u.user_id)
    })
  }

  return (
    <tr className={`border-b border-slate-50 transition-colors ${isPending ? 'opacity-40' : 'hover:bg-slate-50'}`}>
      <td className="px-4 py-3">
        <p className="font-medium text-[#0f2240] text-xs">{u.full_name || '—'}</p>
        <p className="text-xs text-slate-400">{u.email}</p>
      </td>

      {/* Plan change inline */}
      <td className="px-4 py-3">
        <select
          value={tier}
          disabled={planPending}
          onChange={e => handlePlanChange(e.target.value as AdminUser['tier'])}
          className={`text-xs font-mono-vg px-2 py-0.5 rounded-full border-0 outline-none cursor-pointer
            ${TIER_STYLES[tier] ?? TIER_STYLES.free}
            ${planPending ? 'opacity-50' : ''}`}
        >
          <option value="free">free</option>
          <option value="pro">pro</option>
          <option value="institutional">institutional</option>
        </select>
      </td>

      <td className="px-4 py-3">
        <span className={`text-xs font-mono-vg px-2 py-0.5 rounded-full ${
          u.role === 'admin' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
        }`}>{u.role}</span>
      </td>
      <td className="px-4 py-3 text-xs text-slate-500">{u.organisation || '—'}</td>
      <td className="px-4 py-3 text-xs text-slate-500">{u.country || '—'}</td>
      <td className="px-4 py-3">
        {u.subscription_status ? (
          <span className={`text-xs font-mono-vg px-2 py-0.5 rounded-full ${
            u.subscription_status === 'active' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
          }`}>{u.subscription_status}</span>
        ) : <span className="text-xs text-slate-300">—</span>}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500 text-center">{u.daily_queries_used ?? 0}</td>
      <td className="px-4 py-3 text-xs text-slate-400 font-mono-vg whitespace-nowrap">
        {new Date(u.created_at).toLocaleDateString('en-GB', { day:'numeric', month:'short', year:'numeric' })}
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        {err && <p className="text-red-500 text-[10px] mb-1">{err}</p>}
        {confirmDelete ? (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleDelete}
              disabled={isPending}
              className="text-[10px] bg-red-600 hover:bg-red-500 text-white px-2 py-1 rounded transition-colors disabled:opacity-50"
            >
              {isPending ? '…' : 'Confirm'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmDelete(false)}
              className="text-[10px] text-slate-400 hover:text-slate-600 px-1"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            disabled={isPending}
            className="text-[10px] text-red-400 hover:text-red-600 hover:bg-red-50 border border-red-200 px-2 py-1 rounded transition-colors"
          >
            Delete
          </button>
        )}
      </td>
    </tr>
  )
}

export function UsersClient({ users: initial }: Props) {
  const [users, setUsers]         = useState(initial)
  const [search,      setSearch]      = useState('')
  const [tierFilter,  setTierFilter]  = useState('all')
  const [roleFilter,  setRoleFilter]  = useState('all')

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return users.filter(u => {
      if (tierFilter !== 'all' && u.tier !== tierFilter) return false
      if (roleFilter !== 'all' && u.role !== roleFilter) return false
      if (q && !u.email.toLowerCase().includes(q) &&
               !(u.full_name ?? '').toLowerCase().includes(q) &&
               !(u.organisation ?? '').toLowerCase().includes(q)) return false
      return true
    })
  }, [users, search, tierFilter, roleFilter])

  const counts = {
    free:          users.filter(u => u.tier === 'free').length,
    pro:           users.filter(u => u.tier === 'pro').length,
    institutional: users.filter(u => u.tier === 'institutional').length,
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Users</h1>
        <button
          type="button"
          onClick={() => downloadCSV(toCSV(filtered))}
          className="bg-[#0f2240] hover:bg-[#1a3a6e] text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
        >
          ↓ Export CSV
        </button>
      </div>

      {/* KPI pills */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total',          value: users.length,         color: 'text-[#0f2240]' },
          { label: 'Free',           value: counts.free,          color: 'text-slate-500' },
          { label: 'Pro',            value: counts.pro,           color: 'text-blue-600' },
          { label: 'Institutional',  value: counts.institutional, color: 'text-purple-600' },
        ].map(k => (
          <div key={k.label} className="bg-white border border-slate-200 rounded-xl px-4 py-3 text-center">
            <div className={`font-display text-2xl font-bold ${k.color}`}>{k.value}</div>
            <div className="text-xs text-slate-400 mt-0.5">{k.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap gap-3 items-end">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search name, email or organisation…"
          className="flex-1 min-w-[200px] bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
        />
        <select title="Filter by tier" value={tierFilter} onChange={e => setTierFilter(e.target.value)}
          className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400">
          <option value="all">All tiers</option>
          <option value="free">Free</option>
          <option value="pro">Pro</option>
          <option value="institutional">Institutional</option>
        </select>
        <select title="Filter by role" value={roleFilter} onChange={e => setRoleFilter(e.target.value)}
          className="bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400">
          <option value="all">All roles</option>
          <option value="client">Client</option>
          <option value="admin">Admin</option>
        </select>
        <span className="text-xs text-slate-400 font-mono-vg self-center">
          {filtered.length} of {users.length}
        </span>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                {['Name / Email','Tier','Role','Organisation','Country','Sub Status','Queries Today','Joined','Actions'].map(h => (
                  <th key={h} className="text-left text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={9} className="text-center text-slate-400 text-sm py-10">No users match the filter.</td></tr>
              ) : (
                filtered.map(u => (
                  <UserRow
                    key={u.user_id}
                    u={u}
                    onDeleted={id => setUsers(prev => prev.filter(x => x.user_id !== id))}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
