'use client'

import { useState } from 'react'
import { markFollowupRead as serverMarkFollowupRead, updateTicketStatus, sendTicketReply } from './actions'
import type { AdminTicket } from './page'
import { Pagination } from '@/components/ui/Pagination'
import { ChatThread } from '@/components/ui/ChatThread'

type Status = AdminTicket['status']

const STATUS_STYLES: Record<Status, string> = {
  open:        'bg-blue-100 text-blue-700',
  in_progress: 'bg-amber-100 text-amber-700',
  resolved:    'bg-green-100 text-green-700',
  closed:      'bg-slate-100 text-slate-500',
}

const STATUSES: Status[] = ['open', 'in_progress', 'resolved', 'closed']

interface Props {
  tickets: AdminTicket[]
  adminEmail: string
  adminRole: 'admin' | 'staff'
}

const PAGE_SIZE = 25

export function TicketsClient({ tickets: initial, adminEmail, adminRole }: Props) {
  const [tickets, setTickets] = useState<AdminTicket[]>(initial)
  const [filter, setFilter]   = useState<Status | 'all'>('all')
  const [search, setSearch]   = useState('')
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [updating, setUpdating] = useState<string | null>(null)
  const [replyText, setReplyText]   = useState<Record<string, string>>({})
  const [replyStatus, setReplyStatus] = useState<Record<string, Status>>({})
  const [sending, setSending]   = useState<string | null>(null)
  const [replyMsg, setReplyMsg] = useState<Record<string, { type: 'success' | 'error'; text: string }>>({})

  const filtered = tickets.filter(t => {
    const matchStatus = filter === 'all' || t.status === filter
    const q = search.toLowerCase()
    const matchSearch = !q || t.subject.toLowerCase().includes(q) ||
      (t.email ?? '').toLowerCase().includes(q) ||
      (t.message ?? '').toLowerCase().includes(q)
    return matchStatus && matchSearch
  })

  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  async function handleMarkFollowupRead(id: string) {
    const t = tickets.find(x => x.id === id)
    if (!t?.user_followup || t.user_followup_read) return
    await serverMarkFollowupRead(id)
    setTickets(prev => prev.map(x => x.id === id ? { ...x, user_followup_read: true } : x))
  }

  async function updateStatus(id: string, status: Status) {
    setUpdating(id)
    try {
      const ok = await updateTicketStatus(id, status)
      if (ok) setTickets(prev => prev.map(t => t.id === id ? { ...t, status } : t))
    } finally {
      setUpdating(null)
    }
  }

  async function sendReply(t: AdminTicket) {
    const body = (replyText[t.id] ?? '').trim()
    if (!body) return
    const newStatus = replyStatus[t.id] ?? t.status
    setSending(t.id)
    setReplyMsg(prev => ({ ...prev, [t.id]: { type: 'success', text: '' } }))
    try {
      const result = await sendTicketReply({
        ticketId: t.id,
        toEmail: t.email,
        toName: t.name ?? t.email,
        subject: t.subject,
        body,
        newStatus,
      })
      if (result.ok) {
        setTickets(prev => prev.map(x => x.id === t.id ? { ...x, status: newStatus as Status } : x))
        setReplyText(prev => ({ ...prev, [t.id]: '' }))
        const emailNote = result.emailSent
          ? ` · Email sent to ${t.email}`
          : ` · In-app only (email: ${result.emailError ?? 'not configured'})`
        setReplyMsg(prev => ({ ...prev, [t.id]: { type: 'success', text: `Reply saved${emailNote}` } }))
      } else {
        setReplyMsg(prev => ({ ...prev, [t.id]: { type: 'error', text: result.error ?? 'Failed to send.' } }))
      }
    } catch (e: unknown) {
      setReplyMsg(prev => ({ ...prev, [t.id]: { type: 'error', text: (e as Error).message } }))
    } finally {
      setSending(null)
    }
  }

  const counts = STATUSES.reduce((acc, s) => {
    acc[s] = tickets.filter(t => t.status === s).length
    return acc
  }, {} as Record<Status, number>)

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Support Tickets</h1>
        <span className="text-sm text-slate-400 font-mono-vg">{tickets.length} total</span>
      </div>

      {/* Status filter pills */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => { setFilter('all'); setPage(1) }}
          className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
            filter === 'all' ? 'bg-[#0f2240] border-[#0f2240] text-white' : 'border-slate-200 text-slate-500 hover:border-slate-400'
          }`}
        >
          All ({tickets.length})
        </button>
        {STATUSES.map(s => (
          <button
            key={s}
            type="button"
            onClick={() => { setFilter(s); setPage(1) }}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              filter === s
                ? 'bg-[#0f2240] border-[#0f2240] text-white'
                : 'border-slate-200 text-slate-500 hover:border-slate-400'
            }`}
          >
            {s.replace('_', ' ')} ({counts[s]})
          </button>
        ))}
      </div>

      {/* Search */}
      <input
        type="text"
        value={search}
        onChange={e => { setSearch(e.target.value); setPage(1) }}
        placeholder="Search tickets…"
        className="w-full bg-white border border-slate-200 text-slate-700 text-sm px-4 py-2.5 rounded-xl outline-none focus:border-blue-400 transition-colors"
      />

      {/* Tickets */}
      <div className="space-y-2">
        {paged.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400 text-sm">
            No tickets found.
          </div>
        ) : (
          paged.map(t => (
            <div key={t.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <button
                type="button"
                onClick={() => {
                  const opening = expanded !== t.id
                  setExpanded(opening ? t.id : null)
                  if (opening) handleMarkFollowupRead(t.id)
                }}
                className="w-full text-left px-5 py-4 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#0f2240] truncate">{t.subject}</p>
                    <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                      <span className={`text-xs font-mono-vg px-2 py-0.5 rounded-full ${STATUS_STYLES[t.status]}`}>
                        {t.status.replace('_', ' ')}
                      </span>
                      {t.category && (
                        <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{t.category}</span>
                      )}
                      <span className="text-xs text-slate-400 font-mono-vg">
                        {t.email ?? 'unknown'}
                      </span>
                      <span className="text-xs text-slate-400 font-mono-vg">
                        {new Date(t.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </span>
                    </div>
                  </div>
                  <span className="text-slate-400 text-xs mt-1 shrink-0">{expanded === t.id ? '▲' : '▼'}</span>
                </div>
              </button>

              {expanded === t.id && (
                <div className="border-t border-slate-100 px-5 py-4 space-y-4">
                  {t.message && (
                    <div>
                      <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-1.5">Message</p>
                      <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{t.message}</p>
                    </div>
                  )}

                  {t.user_followup && (
                    <div className="bg-amber-50 border border-amber-100 rounded-lg px-3 py-2.5">
                      <p className="text-[0.65rem] text-amber-500 font-mono-vg uppercase tracking-widest mb-1">User Follow-up</p>
                      <p className="text-sm text-slate-700 whitespace-pre-wrap">{t.user_followup}</p>
                    </div>
                  )}

                  {/* Live chat */}
                  <div className="border border-slate-200 rounded-xl p-3">
                    <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-2">Live Chat</p>
                    <ChatThread
                      ticketId={t.id}
                      currentEmail={adminEmail}
                      currentRole={adminRole}
                    />
                  </div>

                  {/* Email reply form */}
                  <div className="space-y-3 pt-1">
                    <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Email Reply to {t.email}</p>
                    <textarea
                      value={replyText[t.id] ?? ''}
                      onChange={e => setReplyText(prev => ({ ...prev, [t.id]: e.target.value }))}
                      placeholder="Type your reply…"
                      rows={4}
                      className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors resize-none"
                    />
                    <div className="flex items-center gap-3 flex-wrap">
                      <select
                        aria-label="Set ticket status"
                        value={replyStatus[t.id] ?? t.status}
                        onChange={e => setReplyStatus(prev => ({ ...prev, [t.id]: e.target.value as Status }))}
                        className="bg-white border border-slate-200 text-slate-700 text-xs px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
                      >
                        {STATUSES.map(s => (
                          <option key={s} value={s}>{s.replace('_', ' ')}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        disabled={sending === t.id || !(replyText[t.id] ?? '').trim()}
                        onClick={() => sendReply(t)}
                        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-1.5"
                      >
                        {sending === t.id
                          ? <><span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />Sending…</>
                          : 'Send Reply →'
                        }
                      </button>
                      {/* Status-only update (no reply) */}
                      <button
                        type="button"
                        disabled={updating === t.id}
                        onClick={() => updateStatus(t.id, replyStatus[t.id] ?? t.status)}
                        className="text-xs px-3 py-2 rounded-lg border border-slate-200 text-slate-500 hover:border-slate-400 hover:text-slate-700 transition-colors disabled:opacity-50"
                      >
                        {updating === t.id ? '…' : 'Update status only'}
                      </button>
                    </div>
                    {replyMsg[t.id]?.text && (
                      <p className={`text-xs font-mono-vg ${replyMsg[t.id].type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                        {replyMsg[t.id].text}
                      </p>
                    )}
                  </div>

                  <div className="text-xs text-slate-400 font-mono-vg">
                    ID: {t.id} · Created: {new Date(t.created_at).toLocaleString('en-GB')}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <Pagination page={page} totalPages={Math.ceil(filtered.length / PAGE_SIZE)} onPageChange={setPage} totalItems={filtered.length} pageSize={PAGE_SIZE} />
    </div>
  )
}
