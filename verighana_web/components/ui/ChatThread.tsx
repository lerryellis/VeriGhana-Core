'use client'

import { useState, useEffect, useRef } from 'react'
import { createClient } from '@/lib/supabase/client'

export type ChatMessage = {
  id: string
  ticket_id: number
  sender_role: 'user' | 'admin' | 'staff'
  sender_email: string
  body: string
  created_at: string
}

interface Props {
  ticketId: number
  currentEmail: string
  currentRole: 'user' | 'admin' | 'staff'
}

function fmtTime(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  return `${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} ${time}`
}

export function ChatThread({ ticketId, currentEmail, currentRole }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)
  const supabase = createClient()

  // Load existing messages
  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from('ticket_messages')
        .select('*')
        .eq('ticket_id', ticketId)
        .order('created_at', { ascending: true })
      setMessages((data ?? []) as ChatMessage[])
      setLoading(false)
    }
    load()
  }, [ticketId])

  // Subscribe to new messages via Supabase Realtime
  useEffect(() => {
    const channel = supabase
      .channel(`ticket-${ticketId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'ticket_messages',
          filter: `ticket_id=eq.${ticketId}`,
        },
        (payload) => {
          const newMsg = payload.new as ChatMessage
          setMessages(prev => {
            if (prev.some(m => m.id === newMsg.id)) return prev
            return [...prev, newMsg]
          })
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [ticketId])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    const body = input.trim()
    if (!body) return
    setSending(true)
    const { error } = await supabase.from('ticket_messages').insert({
      ticket_id: ticketId,
      sender_role: currentRole,
      sender_email: currentEmail,
      body,
    })
    setSending(false)
    if (!error) {
      setInput('')
      // Also reopen ticket if user sends a message
      if (currentRole === 'user') {
        await supabase.from('support_tickets').update({ status: 'open' }).eq('id', ticketId)
      }
    }
  }

  const isOwnMessage = (msg: ChatMessage) => msg.sender_email === currentEmail

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2 min-h-[200px] max-h-[400px] bg-slate-50 rounded-lg">
        {loading ? (
          <div className="flex items-center justify-center h-full text-xs text-slate-400">
            <span className="w-3 h-3 border-2 border-slate-200 border-t-slate-500 rounded-full animate-spin mr-2" />
            Loading messages…
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-slate-400">
            No messages yet. Start the conversation below.
          </div>
        ) : (
          messages.map(msg => (
            <div
              key={msg.id}
              className={`flex ${isOwnMessage(msg) ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[75%] rounded-xl px-3.5 py-2 ${
                isOwnMessage(msg)
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : msg.sender_role === 'admin' || msg.sender_role === 'staff'
                  ? 'bg-white border border-slate-200 text-slate-700 rounded-bl-sm'
                  : 'bg-white border border-slate-200 text-slate-700 rounded-bl-sm'
              }`}>
                {!isOwnMessage(msg) && (
                  <p className={`text-[0.6rem] font-semibold mb-0.5 ${
                    msg.sender_role === 'admin' ? 'text-amber-600' :
                    msg.sender_role === 'staff' ? 'text-blue-600' :
                    'text-slate-400'
                  }`}>
                    {msg.sender_role === 'admin' ? 'Admin' : msg.sender_role === 'staff' ? 'Staff' : msg.sender_email.split('@')[0]}
                  </p>
                )}
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.body}</p>
                <p className={`text-[0.55rem] mt-1 ${
                  isOwnMessage(msg) ? 'text-blue-200' : 'text-slate-300'
                }`}>
                  {fmtTime(msg.created_at)}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="flex gap-2 mt-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Type a message…"
          disabled={sending}
          className="flex-1 bg-white border border-slate-200 text-slate-700 text-sm px-3 py-2.5 rounded-xl outline-none focus:border-blue-400 transition-colors"
        />
        <button
          type="button"
          onClick={send}
          disabled={sending || !input.trim()}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2.5 rounded-xl transition-colors shrink-0"
        >
          {sending ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
