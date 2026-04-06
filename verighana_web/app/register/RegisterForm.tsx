'use client'

import { useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { AuthCard } from '@/components/auth/AuthCard'
import { GoogleButton } from '@/components/auth/GoogleButton'

const PLAN_LABELS: Record<string, string> = {
  pro: 'Pro — ₵0.99/mo',
  institutional: 'Institutional — ₵1.99/mo',
}

export function RegisterForm() {
  const router       = useRouter()
  const searchParams = useSearchParams()
  const plan         = searchParams.get('plan') ?? ''

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const [success, setSuccess]   = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setLoading(true)
    const supabase = createClient()
    const { error: err } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/app/verify` },
    })

    if (err) {
      setError(err.message)
      setLoading(false)
      return
    }

    setSuccess(true)
    setTimeout(() => router.push(plan ? `/app/billing?plan=${plan}` : '/app/verify'), 2000)
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle="Free to start — no credit card required"
      footer={
        <>
          Already have an account?{' '}
          <Link href="/login" className="text-blue-400 hover:text-blue-300 transition-colors">
            Sign in
          </Link>
        </>
      }
    >
      {!success && (
        <>
          <GoogleButton />
          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10" />
            </div>
            <div className="relative flex justify-center text-xs text-slate-500">
              <span className="bg-[#0e1f3d] px-3">or sign up with email</span>
            </div>
          </div>
        </>
      )}

      {success ? (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 text-sm px-4 py-4 rounded-lg text-center">
          <div className="font-semibold mb-1">Account created!</div>
          Check your email to confirm your address, then you&apos;ll be redirected automatically.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <RegisterField label="Email"            type="email"    value={email}    onChange={setEmail}    placeholder="you@example.com" />
          <RegisterField label="Password"         type="password" value={password} onChange={setPassword} placeholder="Min. 8 characters" />
          <RegisterField label="Confirm Password" type="password" value={confirm}  onChange={setConfirm}  placeholder="••••••••" />

          {plan && PLAN_LABELS[plan] && (
            <div className="bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs px-4 py-2.5 rounded-lg">
              Selected plan: <span className="font-semibold">{PLAN_LABELS[plan]}</span>
              <span className="text-slate-500"> — you can upgrade after sign in</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-medium py-3 rounded-lg transition-colors flex items-center justify-center gap-2 mt-2"
          >
            {loading && <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
            {loading ? 'Creating account…' : 'Create Free Account'}
          </button>

          <p className="text-[0.7rem] text-slate-600 text-center">
            By registering you agree to our Terms of Service and Privacy Policy.
          </p>
        </form>
      )}
    </AuthCard>
  )
}

function RegisterField({
  label, type, value, onChange, placeholder,
}: {
  label: string; type: string; value: string
  onChange: (v: string) => void; placeholder: string
}) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-1.5 font-mono-vg uppercase tracking-wider">
        {label}
      </label>
      <input
        type={type}
        required
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-white/[0.07] border border-white/15 text-white placeholder:text-slate-600 text-sm px-4 py-3 rounded-lg outline-none focus:border-blue-500/50 transition-colors"
      />
    </div>
  )
}
