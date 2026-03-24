'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { TierChip } from '@/components/ui/TierChip'
import type { UserProfile } from './page'

type Tier = 'free' | 'pro' | 'institutional'

interface Props {
  profile: UserProfile | null
  authEmail: string
  totalVerifications: number
}

const TIER_LIMITS: Record<string, string> = {
  free:          '5 verifications/day',
  pro:           'Unlimited verifications',
  institutional: 'Unlimited + bulk (20 claims)',
}

export function AccountClient({ profile, authEmail, totalVerifications }: Props) {
  const router = useRouter()
  const tier   = (profile?.tier ?? 'free') as Tier

  const [fullName, setFullName]       = useState(profile?.full_name ?? '')
  const [organisation, setOrg]        = useState(profile?.organisation ?? '')
  const [phone, setPhone]             = useState(profile?.phone ?? '')
  const [country, setCountry]         = useState(profile?.country ?? '')
  const [saving, setSaving]           = useState(false)
  const [saveMsg, setSaveMsg]         = useState<string | null>(null)
  const [showPassForm, setPassForm]   = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [passMsg, setPassMsg]         = useState<string | null>(null)
  const [passLoading, setPassLoading] = useState(false)

  const [cancelConfirm, setCancelConfirm] = useState(false)
  const [cancelling, setCancelling]       = useState(false)
  const [cancelMsg, setCancelMsg]         = useState<string | null>(null)
  const [cancelled, setCancelled]         = useState(
    profile?.cancelled_at !== null && profile?.cancelled_at !== undefined
  )

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSaveMsg(null)
    const supabase = createClient()
    const { error } = await supabase
      .from('user_profiles')
      .update({ full_name: fullName, organisation, phone, country })
      .eq('user_id', profile?.user_id)
    setSaving(false)
    setSaveMsg(error ? `Error: ${error.message}` : 'Profile saved.')
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault()
    if (newPassword.length < 8) { setPassMsg('Min. 8 characters.'); return }
    setPassLoading(true)
    setPassMsg(null)
    const supabase = createClient()
    const { error } = await supabase.auth.updateUser({ password: newPassword })
    setPassLoading(false)
    if (error) { setPassMsg(`Error: ${error.message}`); return }
    setPassMsg('Password updated.')
    setNewPassword('')
    setPassForm(false)
  }

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  async function cancelSubscription() {
    setCancelling(true)
    setCancelMsg(null)
    const supabase = createClient()
    const { error } = await supabase
      .from('user_profiles')
      .update({ cancelled_at: new Date().toISOString() })
      .eq('user_id', profile?.user_id)
    setCancelling(false)
    if (error) {
      setCancelMsg(`Error: ${error.message}`)
    } else {
      setCancelled(true)
      setCancelConfirm(false)
      setCancelMsg('Subscription cancelled. You keep access until the period ends.')
    }
  }

  const expiresAt  = profile?.subscription_expires_at
  const isPaid     = tier !== 'free'
  const isCancelled = profile?.cancelled_at !== null && profile?.cancelled_at !== undefined
  const memberSince = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
    : '—'

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <h1 className="font-display text-2xl font-bold text-[#0f2240]">Account</h1>

      {/* Profile card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-full bg-blue-600/10 border-2 border-blue-500/20 flex items-center justify-center text-xl font-bold text-blue-600 font-mono-vg">
            {authEmail.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <p className="font-display font-bold text-[#0f2240] text-lg">{fullName || authEmail}</p>
            <p className="text-sm text-slate-400">{authEmail}</p>
            <div className="flex items-center gap-2 mt-1">
              <TierChip tier={tier} />
              <span className="text-xs text-slate-400">Member since {memberSince}</span>
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: 'Plan',        value: tier.charAt(0).toUpperCase() + tier.slice(1) },
            { label: 'Verifications', value: totalVerifications.toLocaleString() },
            { label: 'Daily Limit', value: tier === 'free' ? `${profile?.daily_queries_used ?? 0}/5` : '∞' },
          ].map(s => (
            <div key={s.label} className="bg-slate-50 rounded-lg px-4 py-3 text-center">
              <div className="font-display font-bold text-[#0f2240]">{s.value}</div>
              <div className="text-xs text-slate-400 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Edit profile form */}
        <form onSubmit={saveProfile} className="space-y-3">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-2">Profile Details</p>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="Full Name"    value={fullName}      onChange={setFullName}      placeholder="Your name" />
            <FormField label="Organisation" value={organisation}  onChange={setOrg}           placeholder="Organisation" />
            <FormField label="Phone"        value={phone}         onChange={setPhone}          placeholder="+233 …" />
            <FormField label="Country"      value={country}       onChange={setCountry}        placeholder="Ghana" />
          </div>

          <div className="flex items-center gap-3 pt-1">
            <button
              type="submit"
              disabled={saving}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
            >
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
            {saveMsg && (
              <span className={`text-xs font-mono-vg ${saveMsg.startsWith('Error') ? 'text-red-500' : 'text-green-600'}`}>
                {saveMsg}
              </span>
            )}
          </div>
        </form>
      </div>

      {/* Subscription card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Subscription</p>

        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <TierChip tier={tier} />
              {isCancelled && (
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Cancelled</span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1">{TIER_LIMITS[tier]}</p>
            {isPaid && expiresAt && (
              <p className="text-xs text-slate-400 mt-1 font-mono-vg">
                {isCancelled ? 'Access until' : 'Renews'}{' '}
                {new Date(expiresAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
              </p>
            )}
          </div>

          {!isPaid && (
            <a
              href="/app/billing"
              className="shrink-0 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              Upgrade →
            </a>
          )}

          {isPaid && !cancelled && (
            <button
              type="button"
              onClick={() => setCancelConfirm(true)}
              className="shrink-0 text-sm text-slate-400 hover:text-red-500 transition-colors"
            >
              Cancel plan
            </button>
          )}
        </div>

        {/* Cancel confirmation */}
        {isPaid && !cancelled && cancelConfirm && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-sm text-slate-700 mb-3">
              Are you sure? You&apos;ll keep access until{' '}
              <span className="font-medium">
                {expiresAt
                  ? new Date(expiresAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
                  : 'the end of your billing period'}
              </span>
              , then your account reverts to Free.
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={cancelSubscription}
                disabled={cancelling}
                className="bg-red-600 hover:bg-red-500 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
              >
                {cancelling ? 'Cancelling…' : 'Yes, cancel subscription'}
              </button>
              <button
                type="button"
                onClick={() => setCancelConfirm(false)}
                className="text-sm text-slate-400 hover:text-slate-600"
              >
                Keep subscription
              </button>
            </div>
          </div>
        )}

        {cancelMsg && (
          <p className={`mt-3 text-xs font-mono-vg ${cancelMsg.startsWith('Error') ? 'text-red-500' : 'text-green-600'}`}>
            {cancelMsg}
          </p>
        )}

        {!isPaid && (
          <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 gap-3">
            <PlanTeaser
              name="Pro"
              price="$9.99/mo"
              perks={['Unlimited verifications', 'All AI models', 'API key access', 'History export']}
              href="/app/billing?plan=pro"
              accent="blue"
            />
            <PlanTeaser
              name="Institutional"
              price="$79.99/mo"
              perks={['Everything in Pro', 'Bulk verify (20 claims)', 'Team seats', 'Priority support']}
              href="/app/billing?plan=institutional"
              accent="teal"
            />
          </div>
        )}
      </div>

      {/* Security */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Security</p>

        {!showPassForm ? (
          <button
            type="button"
            onClick={() => setPassForm(true)}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Change password →
          </button>
        ) : (
          <form onSubmit={changePassword} className="space-y-3 max-w-sm">
            <FormField label="New Password" value={newPassword} onChange={setNewPassword} placeholder="Min. 8 characters" type="password" />
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={passLoading}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
              >
                {passLoading ? 'Updating…' : 'Update Password'}
              </button>
              <button type="button" onClick={() => setPassForm(false)} className="text-sm text-slate-400 hover:text-slate-600">
                Cancel
              </button>
              {passMsg && (
                <span className={`text-xs font-mono-vg ${passMsg.startsWith('Error') ? 'text-red-500' : 'text-green-600'}`}>
                  {passMsg}
                </span>
              )}
            </div>
          </form>
        )}

        <div className="mt-4 pt-4 border-t border-slate-100">
          <button
            type="button"
            onClick={signOut}
            className="text-sm text-slate-400 hover:text-red-500 transition-colors"
          >
            Sign out of all devices
          </button>
        </div>
      </div>
    </div>
  )
}

function FormField({
  label, value, onChange, placeholder, type = 'text',
}: {
  label: string; value: string; onChange: (v: string) => void
  placeholder: string; type?: string
}) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
      />
    </div>
  )
}

function PlanTeaser({
  name, price, perks, href, accent,
}: {
  name: string; price: string; perks: string[]; href: string; accent: 'blue' | 'teal'
}) {
  const bg  = accent === 'blue' ? 'bg-blue-50 border-blue-200' : 'bg-teal-50 border-teal-200'
  const btn = accent === 'blue' ? 'bg-blue-600 hover:bg-blue-500' : 'bg-teal-600 hover:bg-teal-500'
  const txt = accent === 'blue' ? 'text-blue-700' : 'text-teal-700'
  return (
    <div className={`border rounded-xl p-4 ${bg}`}>
      <div className={`font-display font-bold text-sm ${txt} mb-0.5`}>{name}</div>
      <div className={`text-xs font-mono-vg font-semibold ${txt} mb-3`}>{price}</div>
      <ul className="space-y-1 mb-3">
        {perks.map(p => (
          <li key={p} className={`text-xs flex items-center gap-1.5 ${txt}`}>
            <span className="font-bold">✓</span>{p}
          </li>
        ))}
      </ul>
      <a href={href} className={`block text-center text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${btn}`}>
        Upgrade to {name}
      </a>
    </div>
  )
}
