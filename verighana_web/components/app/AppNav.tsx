'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { TierChip } from '@/components/ui/TierChip'

type Tier = 'free' | 'pro' | 'institutional'

interface AppNavProps {
  email: string
  tier: Tier
  role: string
  unreadCount?: number
}

type Tab = { label: string; href: string; badge?: number }

export function AppNav({ email, tier, role, unreadCount = 0 }: AppNavProps) {
  const pathname = usePathname()
  const router   = useRouter()

  const USER_TABS: Tab[] = [
    { label: 'Verify',    href: '/app/verify' },
    { label: 'History',   href: '/app/history' },
    { label: 'Account',   href: '/app/account' },
    { label: 'Billing',   href: '/app/billing' },
    { label: 'Support',   href: '/app/contact', badge: unreadCount },
    { label: 'Feedback',  href: '/app/feedback' },
  ]

  const ADMIN_TABS: Tab[] = [
    { label: 'Verify',      href: '/app/verify' },
    { label: 'Admin',       href: '/admin' },
    { label: 'Tickets',     href: '/admin/tickets',  badge: unreadCount },
    { label: 'Reports',     href: '/admin/reports' },
    { label: 'Finance',     href: '/admin/finance' },
    { label: 'Staff',       href: '/admin/staff' },
    { label: 'Feedback',    href: '/admin/feedback' },
    { label: 'Users',       href: '/admin/users' },
    { label: 'Site Tester', href: '/admin/tester' },
    { label: 'API Docs',    href: '/admin/api-docs' },
  ]

  const tabs = role === 'admin' ? ADMIN_TABS : USER_TABS

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const initials = email.slice(0, 2).toUpperCase()

  return (
    <header className="sticky top-0 z-50 bg-[rgba(15,34,64,0.97)] backdrop-blur-xl border-b border-white/[0.08]">
      {/* Top bar */}
      <div className="flex items-center h-14 px-5 gap-4">
        <Link href="/" className="font-display font-extrabold text-lg text-white tracking-tight mr-auto">
          Veri<span className="text-blue-400">Ghana</span>
        </Link>

        <TierChip tier={tier} />

        {/* Avatar + email */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-blue-600/30 border border-blue-500/30 flex items-center justify-center text-xs font-bold text-blue-300 font-mono-vg">
            {initials}
          </div>
          <span className="hidden md:block text-xs text-slate-400 max-w-[160px] truncate">{email}</span>
        </div>

        <button
          type="button"
          onClick={signOut}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded border border-white/[0.06] hover:border-white/20"
        >
          Sign out
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 px-5 overflow-x-auto scrollbar-none">
        {tabs.map(tab => {
          const active = pathname === tab.href || pathname.startsWith(tab.href + '/')
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`relative shrink-0 text-sm px-4 py-2.5 border-b-2 transition-colors ${
                active
                  ? 'border-blue-400 text-white font-medium'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.label}
              {!!tab.badge && tab.badge > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center leading-none">
                  {tab.badge > 99 ? '99+' : tab.badge}
                </span>
              )}
            </Link>
          )
        })}
      </div>
    </header>
  )
}
