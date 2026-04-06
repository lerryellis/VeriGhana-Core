'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { ChatThread } from '@/components/ui/ChatThread'
import type { SupportTicket } from './page'

const CATEGORIES = [
  'Billing / Subscription',
  'Verification accuracy',
  'Account access',
  'API / Integration',
  'Bug report',
  'Feature request',
  'Feedback',
  'Other',
]

const STATUS_STYLES: Record<SupportTicket['status'], string> = {
  open:        'bg-blue-100 text-blue-700',
  in_progress: 'bg-amber-100 text-amber-700',
  resolved:    'bg-green-100 text-green-700',
  closed:      'bg-slate-100 text-slate-500',
}

const STATUS_LABELS: Record<SupportTicket['status'], string> = {
  open:        'Open',
  in_progress: 'In Progress',
  resolved:    'Resolved',
  closed:      'Closed',
}

interface Props {
  authEmail: string
  fullName: string
  tier: 'free' | 'pro' | 'institutional'
  accessToken: string
  tickets: SupportTicket[]
}

export function ContactClient({ authEmail, fullName, tier, accessToken, tickets: initialTickets }: Props) {
  const [subject, setSubject]       = useState('')
  const [category, setCategory]     = useState(CATEGORIES[0])
  const [message, setMessage]       = useState('')
  const [submitting, setSubmitting]   = useState(false)
  const [msg, setMsg]               = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [tickets, setTickets]       = useState<SupportTicket[]>(initialTickets)
  const [expanded, setExpanded]     = useState<string | null>(null)
  const [followupText, setFollowupText] = useState<Record<string, string>>({})
  const [sendingFollowup, setSendingFollowup] = useState<string | null>(null)
  const [followupMsg, setFollowupMsg] = useState<Record<string, string>>({})
  const [deleting, setDeleting]     = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  async function markReplyRead(id: string) {
    const ticket = tickets.find(t => t.id === id)
    if (!ticket?.admin_reply || ticket.admin_reply_read) return
    const supabase = createClient()
    await supabase.from('support_tickets').update({ admin_reply_read: true }).eq('id', id)
    setTickets(prev => prev.map(t => t.id === id ? { ...t, admin_reply_read: true } : t))
  }

  async function sendFollowup(id: string) {
    const text = (followupText[id] ?? '').trim()
    if (!text) return
    setSendingFollowup(id)
    const supabase = createClient()
    const { error } = await supabase
      .from('support_tickets')
      .update({ user_followup: text, status: 'open' })
      .eq('id', id)
    setSendingFollowup(null)
    if (error) {
      setFollowupMsg(prev => ({ ...prev, [id]: `Error: ${error.message}` }))
    } else {
      setTickets(prev => prev.map(t => t.id === id ? { ...t, user_followup: text, status: 'open' } : t))
      setFollowupText(prev => ({ ...prev, [id]: '' }))
      setFollowupMsg(prev => ({ ...prev, [id]: 'Follow-up sent!' }))
    }
  }

  async function deleteTicket(id: string) {
    setDeleting(id)
    const supabase = createClient()
    const { error } = await supabase.from('support_tickets').delete().eq('id', id)
    setDeleting(null)
    setConfirmDelete(null)
    if (!error) {
      setTickets(prev => prev.filter(t => t.id !== id))
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!subject.trim() || !message.trim()) {
      setMsg({ type: 'error', text: 'Subject and message are required.' })
      return
    }

    setSubmitting(true)
    setMsg(null)

    const supabase = createClient()
    const { data: { user } } = await supabase.auth.getUser()
    const { data, error } = await supabase
      .from('support_tickets')
      .insert({
        subject: subject.trim(),
        category,
        message: message.trim(),
        status: 'open',
        email: authEmail,
        name: fullName || authEmail,
        user_id: user?.id ?? null,
      })
      .select('id, subject, status, created_at, updated_at')
      .single()

    setSubmitting(false)

    if (error) {
      setMsg({ type: 'error', text: `Failed to submit ticket: ${error.message}` })
      return
    }

    setMsg({ type: 'success', text: "Ticket submitted! We'll respond within 24 hours (Pro/Institutional: within 4 hours)." })
    setSubject('')
    setMessage('')
    if (data) setTickets(prev => [data as SupportTicket, ...prev])
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Support</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {tier === 'free'
            ? 'Response within 24 hours · Upgrade for priority support.'
            : tier === 'pro'
            ? 'Priority support · Response within 4 hours.'
            : 'Dedicated support · SLA guaranteed response within 2 hours.'}
        </p>
      </div>

      {/* New ticket form */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">New Support Ticket</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* From (read-only) */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">From</label>
              <input
                type="text"
                value={fullName || authEmail}
                readOnly
                aria-label="Sender name or email"
                className="w-full bg-slate-50 border border-slate-200 text-slate-500 text-sm px-3 py-2 rounded-lg outline-none cursor-default"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Category</label>
              <select
                aria-label="Support category"
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
              >
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Subject</label>
            <input
              type="text"
              value={subject}
              onChange={e => setSubject(e.target.value)}
              placeholder="Brief description of your issue"
              maxLength={200}
              className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Message</label>
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Describe your issue in detail…"
              rows={5}
              maxLength={2000}
              className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors resize-none"
            />
            <div className="text-right mt-0.5">
              <span className="text-[0.68rem] text-slate-400 font-mono-vg">{message.length}/2000</span>
            </div>
          </div>

          {msg && (
            <div className={`text-sm px-4 py-3 rounded-xl ${
              msg.type === 'success'
                ? 'bg-green-50 border border-green-200 text-green-700'
                : 'bg-red-50 border border-red-200 text-red-600'
            }`}>
              {msg.text}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-medium px-6 py-2.5 rounded-lg transition-colors flex items-center gap-2"
          >
            {submitting
              ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Submitting…</>
              : 'Submit Ticket'
            }
          </button>
        </form>
      </div>

      {/* Existing tickets */}
      {tickets.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Your Tickets</p>
          <div className="space-y-2">
            {tickets.map(t => (
              <div key={t.id} className="border-b border-slate-100 last:border-0">
                {/* Row header */}
                <button
                  type="button"
                  onClick={() => {
                    const opening = expanded !== t.id
                    setExpanded(opening ? t.id : null)
                    if (opening) markReplyRead(t.id)
                  }}
                  className="w-full text-left py-3 flex items-start justify-between hover:bg-slate-50 -mx-1 px-1 rounded-lg transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[#0f2240] truncate">{t.subject}</p>
                    <p className="text-xs text-slate-400 font-mono-vg mt-0.5">
                      {new Date(t.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                      {t.admin_reply && <span className="text-blue-500"> · Reply received</span>}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 ml-3 shrink-0">
                    <span className={`text-xs font-mono-vg px-2.5 py-1 rounded-full ${STATUS_STYLES[t.status]}`}>
                      {STATUS_LABELS[t.status]}
                    </span>
                    <span className="text-slate-400 text-xs">{expanded === t.id ? '▲' : '▼'}</span>
                  </div>
                </button>

                {/* Expanded panel — live chat */}
                {expanded === t.id && (
                  <div className="pb-4 space-y-3">
                    {/* Original message */}
                    {t.message && (
                      <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5">
                        <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-1">Original Message</p>
                        <p className="text-sm text-slate-600 whitespace-pre-wrap">{t.message}</p>
                      </div>
                    )}

                    {/* Live chat thread */}
                    <ChatThread
                      ticketId={t.id}
                      currentEmail={authEmail}
                      currentRole="user"
                    />

                    {/* Delete */}
                    <div className="flex items-center gap-2 pt-1">
                      {confirmDelete === t.id ? (
                        <>
                          <span className="text-xs text-slate-500">Delete this ticket?</span>
                          <button
                            type="button"
                            disabled={deleting === t.id}
                            onClick={() => deleteTicket(t.id)}
                            className="text-xs px-3 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white transition-colors disabled:opacity-50"
                          >
                            {deleting === t.id ? 'Deleting…' : 'Yes, delete'}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDelete(null)}
                            className="text-xs px-3 py-2 rounded-lg border border-slate-200 text-slate-500 hover:border-slate-400 transition-colors"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(t.id)}
                          className="text-xs px-3 py-2 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 transition-colors"
                        >
                          Delete ticket
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Contact info */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Other Ways to Reach Us</p>
        <div className="grid grid-cols-2 gap-4">
          {[
            { label: 'Email', value: 'support@verighana.com', icon: '✉️' },
            { label: 'Response Time', value: tier === 'free' ? '≤ 24h' : tier === 'pro' ? '≤ 4h' : '≤ 2h (SLA)', icon: '⏱️' },
          ].map(item => (
            <div key={item.label} className="flex items-start gap-3">
              <span className="text-lg">{item.icon}</span>
              <div>
                <p className="text-xs text-slate-400 font-mono-vg">{item.label}</p>
                <p className="text-sm font-medium text-[#0f2240]">{item.value}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
