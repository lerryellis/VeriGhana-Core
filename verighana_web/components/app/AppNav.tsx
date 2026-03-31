'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { ShieldCheck, Clock, UserCircle, CreditCard, HelpCircle, Star } from 'lucide-react'
import { TierChip } from '@/components/ui/TierChip'

type Tier = 'free' | 'pro' | 'institutional'

interface AppNavProps {
  email: string
  tier: Tier
  role: string
  unreadCount?: number
}

type Tab = { label: string; href: string; icon: React.ElementType; badge?: number }

export function AppNav({ email, tier, role, unreadCount = 0 }: AppNavProps) {
  const pathname = usePathname()
  const router   = useRouter()

  const USER_TABS: Tab[] = [
    { label: 'Verify',    href: '/app/verify',   icon: ShieldCheck },
    { label: 'History',   href: '/app/history',  icon: Clock },
    { label: 'Account',   href: '/app/account',  icon: UserCircle },
    { label: 'Billing',   href: '/app/billing',  icon: CreditCard },
    { label: 'Support',   href: '/app/contact',  icon: HelpCircle, badge: unreadCount },
    { label: 'Feedback',  href: '/app/feedback', icon: Star },
  ]

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const initials = email.slice(0, 2).toUpperCase()

  return (
    <header className="sticky top-0 z-50 bg-[#06111f] border-b border-white/[0.07]">
      {/* Top bar */}
      <div className="flex items-center h-[60px] px-5 gap-4">
        <Link href="/" className="font-display font-extrabold text-[17px] text-white tracking-tight mr-auto">
          Veri<span className="text-blue-400">Ghana</span>
        </Link>

        <TierChip tier={tier} />

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-blue-600/25 border border-blue-500/30 flex items-center justify-center text-xs font-bold text-blue-300">
            {initials}
          </div>
          <span className="hidden md:block text-xs text-slate-400 max-w-[180px] truncate">{email}</span>
        </div>

        <button
          type="button"
          onClick={signOut}
          className="text-xs text-slate-500 hover:text-slate-200 transition-colors px-3 py-1.5 rounded-lg border border-white/[0.07] hover:border-white/20 hover:bg-white/[0.05]"
        >
          Sign out
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-0.5 px-4 pb-2 overflow-x-auto scrollbar-none">
        {USER_TABS.map(tab => {
          const active = pathname === tab.href || pathname.startsWith(tab.href + '/')
          const Icon = tab.icon
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`relative shrink-0 flex items-center gap-2 text-sm px-3.5 py-2 rounded-lg font-medium transition-all duration-150
                ${active
                  ? 'bg-blue-500/[0.12] text-white'
                  : 'text-slate-400 hover:text-white hover:bg-white/[0.05]'
                }`}
            >
              <Icon
                size={15}
                className={`shrink-0 ${active ? 'text-blue-400' : 'text-slate-500'}`}
              />
              {tab.label}
              {!!tab.badge && tab.badge > 0 && (
                <span className="min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center leading-none">
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
