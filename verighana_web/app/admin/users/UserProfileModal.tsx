'use client'

import { useTransition, useState, useEffect } from 'react'
import type { AdminUser } from './page'
import { deleteUser, changeUserPlan, getUserLastPayment, type UserPayment } from './actions'

interface Props {
  user: AdminUser
  onClose: () => void
  onDeleted: (id: string) => void
  onTierChanged: (id: string, tier: AdminUser['tier']) => void
}

const TIER_LIMIT: Record<string, number | null> = {
  free: 5, pro: null, institutional: null,
}

const TIER_LABEL: Record<string, string> = {
  free: 'Free Plan', pro: 'Pro Plan', institutional: 'Institutional Plan',
}

function Avatar({ name, email }: { name: string | null; email: string }) {
  const letter = (name || email).charAt(0).toUpperCase()
  return (
    <div className="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold text-white mx-auto"
      style={{ background: 'linear-gradient(135deg,#94a3b8,#64748b)' }}>
      {letter}
    </div>
  )
}

export function UserProfileModal({ user, onClose, onDeleted, onTierChanged }: Props) {
  const [isPending,    startTransition]     = useTransition()
  const [confirmDel,   setConfirmDel]       = useState(false)
  const [planPending,  startPlanTransition] = useTransition()
  const [editingPlan,  setEditingPlan]      = useState(false)
  const [tier,         setTier]             = useState<AdminUser['tier']>(user.tier)
  const [err,          setErr]              = useState<string | null>(null)
  const [resetSent,    setResetSent]        = useState(false)
  const [payment,      setPayment]          = useState<UserPayment | null | 'loading'>('loading')

  useEffect(() => {
    getUserLastPayment(user.user_id).then(setPayment)
  }, [user.user_id])

  const limit   = TIER_LIMIT[tier]
  const used    = user.daily_queries_used ?? 0
  const pct     = limit ? Math.min((used / limit) * 100, 100) : 100
  const barFill = limit && used >= limit ? '#dc2626' : '#2563eb'

  function handleDelete() {
    startTransition(async () => {
      const res = await deleteUser(user.user_id)
      if (res.error) { setErr(res.error); setConfirmDel(false) }
      else { onDeleted(user.user_id); onClose() }
    })
  }

  function handlePlanSave(newTier: AdminUser['tier']) {
    startPlanTransition(async () => {
      const res = await changeUserPlan(user.user_id, newTier)
      if (res.error) { setErr(res.error) }
      else { setTier(newTier); onTierChanged(user.user_id, newTier); setEditingPlan(false) }
    })
  }

  const displayName = user.full_name?.toUpperCase() || user.email.split('@')[0].toUpperCase()

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.35)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden animate-fade-in">

        {/* Header */}
        <div className="bg-[#f5f5f5] px-8 pt-8 pb-6 text-center border-b border-slate-100 relative">
          <p className="text-xs font-bold tracking-[0.2em] text-slate-500 uppercase mb-4">User Profile</p>
          <Avatar name={user.full_name} email={user.email} />
          <p className="mt-3 text-sm font-semibold text-slate-600">
            {user.full_name || user.email.split('@')[0]}
          </p>

          {/* Delete button */}
          {confirmDel ? (
            <div className="absolute top-6 right-6 flex gap-2">
              <button type="button" onClick={handleDelete} disabled={isPending}
                className="text-xs bg-red-600 text-white px-3 py-1.5 rounded-lg disabled:opacity-50">
                {isPending ? '…' : 'Confirm delete'}
              </button>
              <button type="button" onClick={() => setConfirmDel(false)}
                className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1.5">
                Cancel
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => setConfirmDel(true)}
              className="absolute top-6 right-6 flex items-center gap-2 border border-red-300 text-red-600 hover:bg-red-50 text-xs font-medium px-4 py-2 rounded-lg transition-colors">
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M2 4h12M5 4V2.5A.5.5 0 0 1 5.5 2h5a.5.5 0 0 1 .5.5V4M6 7v5M10 7v5M3 4l1 9.5A.5.5 0 0 0 4.5 14h7a.5.5 0 0 0 .5-.5L13 4" />
              </svg>
              Delete Account
            </button>
          )}
        </div>

        {err && (
          <div className="bg-red-50 border-b border-red-100 px-8 py-2 text-xs text-red-600">{err}</div>
        )}

        {/* Two-column body */}
        <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-100">

          {/* Left — Account Details */}
          <div className="px-8 py-6">
            <p className="text-[0.6rem] font-bold tracking-[0.18em] text-slate-400 uppercase mb-4">Account Details</p>
            <table className="w-full text-sm">
              <tbody className="space-y-1">
                {[
                  { label: 'Name',         value: displayName },
                  { label: 'Email',        value: user.email },
                  { label: 'Organisation', value: user.organisation || '—' },
                  { label: 'Country',      value: user.country || '—' },
                  { label: 'Role',         value: user.role },
                ].map(row => (
                  <tr key={row.label} className="align-top">
                    <td className="text-slate-400 text-xs py-1.5 pr-4 whitespace-nowrap w-1/3">{row.label}</td>
                    <td className="text-slate-700 text-xs py-1.5 font-medium">{row.value}</td>
                  </tr>
                ))}
                <tr className="align-middle">
                  <td className="text-slate-400 text-xs py-1.5 pr-4 whitespace-nowrap">Tier</td>
                  <td className="text-xs py-1.5">
                    {editingPlan ? (
                      <div className="flex items-center gap-2">
                        <select
                          title="Change plan"
                          defaultValue={tier}
                          disabled={planPending}
                          onChange={e => handlePlanSave(e.target.value as AdminUser['tier'])}
                          className="text-xs border border-slate-300 rounded px-2 py-0.5 outline-none focus:border-blue-400"
                        >
                          <option value="free">Free Plan</option>
                          <option value="pro">Pro Plan</option>
                          <option value="institutional">Institutional Plan</option>
                        </select>
                        <button type="button" onClick={() => setEditingPlan(false)}
                          className="text-[10px] text-slate-400 hover:text-slate-600">✕</button>
                      </div>
                    ) : (
                      <button type="button" onClick={() => setEditingPlan(true)}
                        className="font-medium text-slate-700 hover:text-blue-600 transition-colors flex items-center gap-1 group">
                        {TIER_LABEL[tier]}
                        <svg className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M8 2l2 2-5 5H3V7l5-5z"/>
                        </svg>
                      </button>
                    )}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Right — Usage & Status */}
          <div className="px-8 py-6 flex flex-col gap-6">
            <div>
              <p className="text-[0.6rem] font-bold tracking-[0.18em] text-slate-400 uppercase mb-4">Usage &amp; Status</p>
              <table className="w-full text-sm">
                <tbody>
                  <tr>
                    <td className="text-slate-400 text-xs py-1.5 pr-4 w-1/2">Sub Status</td>
                    <td className="py-1.5">
                      <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold tracking-wider px-2.5 py-0.5 rounded-full
                        ${user.subscription_status === 'active' ? 'bg-slate-100 text-slate-500' : 'bg-red-50 text-red-500'}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${user.subscription_status === 'active' ? 'bg-slate-400' : 'bg-red-400'}`} />
                        {(user.subscription_status ?? 'none').toUpperCase()}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="text-slate-400 text-xs py-1.5 pr-4 align-middle">Queries Today</td>
                    <td className="py-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-700 whitespace-nowrap">
                          {used}{limit ? ` / ${limit}` : ' / ∞'}
                        </span>
                        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden min-w-[40px]">
                          <div className="h-full rounded-full transition-all duration-500"
                            style={{ width: `${pct}%`, background: barFill }} />
                        </div>
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td className="text-slate-400 text-xs py-1.5 pr-4">Joined</td>
                    <td className="text-xs font-medium text-slate-700 py-1.5">
                      {new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                    </td>
                  </tr>
                </tbody>
              </table>
              {/* Payment Method */}
            <div>
              <p className="text-[0.6rem] font-bold tracking-[0.18em] text-slate-400 uppercase mb-4">Payment Method</p>
              {payment === 'loading' ? (
                <div className="h-4 w-32 bg-slate-100 rounded animate-pulse" />
              ) : payment === null ? (
                <p className="text-xs text-slate-400 italic">No payments on record</p>
              ) : (
                <table className="w-full text-sm">
                  <tbody>
                    <tr>
                      <td className="text-slate-400 text-xs py-1.5 pr-4 w-1/2">Method</td>
                      <td className="py-1.5">
                        <span className="flex items-center gap-2 text-xs font-medium text-slate-700">
                          <svg className="w-5 h-4 text-slate-400" viewBox="0 0 24 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <rect x="1" y="1" width="22" height="14" rx="2"/>
                            <path d="M1 5h22"/>
                          </svg>
                          {payment.payment_method === 'card' ? 'Card' : payment.payment_method}
                        </span>
                      </td>
                    </tr>
                    <tr>
                      <td className="text-slate-400 text-xs py-1.5 pr-4">Plan Paid</td>
                      <td className="text-xs font-medium text-slate-700 py-1.5">{payment.plan_label}</td>
                    </tr>
                    <tr>
                      <td className="text-slate-400 text-xs py-1.5 pr-4">Amount</td>
                      <td className="text-xs font-medium text-slate-700 py-1.5">
                        ${payment.amount.toFixed(2)} {payment.currency}
                      </td>
                    </tr>
                    <tr>
                      <td className="text-slate-400 text-xs py-1.5 pr-4">Last Payment</td>
                      <td className="text-xs font-medium text-slate-700 py-1.5">
                        {new Date(payment.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}
            </div>
          </div>
          </div>
        </div>

        {/* Actions row */}
        <div className="bg-[#f5f5f5] border-t border-slate-100 px-8 py-5">
          <p className="text-[0.6rem] font-bold tracking-[0.18em] text-slate-400 uppercase mb-3">Actions</p>
          <div className="flex flex-wrap gap-2">
            {[
              {
                label: 'Upgrade Plan',
                icon: <path d="M1 4l5-3 5 3M6 1v10M2 7l4 3 4-3" strokeWidth="1.6"/>,
                onClick: () => setEditingPlan(true),
              },
              {
                label: resetSent ? 'Email Sent ✓' : 'Reset Password',
                icon: <><rect x="3" y="7" width="10" height="6" rx="1" strokeWidth="1.6"/><path d="M5 7V5a3 3 0 0 1 6 0v2" strokeWidth="1.6"/></>,
                onClick: () => setResetSent(true),
                disabled: resetSent,
              },
            ].map(btn => (
              <button
                key={btn.label}
                type="button"
                onClick={btn.onClick}
                disabled={btn.disabled}
                className="flex items-center gap-2 text-xs font-medium text-slate-600 hover:text-[#0f2240] bg-white hover:bg-slate-50 border border-slate-200 px-4 py-2 rounded-lg transition-colors disabled:opacity-60"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor">
                  {btn.icon}
                </svg>
                {btn.label}
              </button>
            ))}

            <button type="button" onClick={onClose}
              className="ml-auto text-xs font-medium text-slate-400 hover:text-slate-600 px-4 py-2 rounded-lg transition-colors">
              Close ✕
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
