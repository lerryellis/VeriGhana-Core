'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { AuthCard } from '@/components/auth/AuthCard'
import { GoogleButton } from '@/components/auth/GoogleButton'

function LoginForm() {
  const router       = useRouter()
  const searchParams = useSearchParams()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(
    searchParams.get('error') ? 'Google sign-in was cancelled or failed. Please try again.' : null
  )

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const supabase = createClient()
    const { error: err } = await supabase.auth.signInWithPassword({ email, password })

    if (err) {
      setError(err.message)
      setLoading(false)
      return
    }

    router.push('/app/verify')
    router.refresh()
  }

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Sign in to your VeriGhana account"
      footer={
        <>
          Don&apos;t have an account?{' '}
          <Link href="/register" className="text-blue-400 hover:text-blue-300 transition-colors">
            Create one free
          </Link>
        </>
      }
    >
      <GoogleButton />

      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-white/10" />
        </div>
        <div className="relative flex justify-center text-xs text-slate-500">
          <span className="bg-[#0e1f3d] px-3">or continue with email</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs text-slate-400 mb-1.5 font-mono-vg uppercase tracking-wider">
            Email
          </label>
          <input
            type="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full bg-white/[0.07] border border-white/15 text-white placeholder:text-slate-600 text-sm px-4 py-3 rounded-lg outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1.5 font-mono-vg uppercase tracking-wider">
            Password
          </label>
          <input
            type="password"
            required
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full bg-white/[0.07] border border-white/15 text-white placeholder:text-slate-600 text-sm px-4 py-3 rounded-lg outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm font-medium py-3 rounded-lg transition-colors flex items-center justify-center gap-2 mt-2"
        >
          {loading && <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
          {loading ? 'Signing in…' : 'Sign In'}
        </button>
      </form>
    </AuthCard>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
