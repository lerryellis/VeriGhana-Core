'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import {
  LayoutDashboard, ShieldCheck, Ticket, BarChart3, DollarSign,
  Users, MessageSquare, UserCog, Globe, BookOpen, LogOut,
  ChevronLeft, ChevronRight, Menu, X,
} from 'lucide-react'

type Tier = 'free' | 'pro' | 'institutional'

interface Props {
  email: string
  tier: Tier
  role: string
  unreadCount?: number
}

type NavItem = { label: string; href: string; icon: React.ElementType; badge?: number; exact?: boolean }

const TIER_COLOR: Record<string, string> = {
  free: 'text-slate-400',
  pro: 'text-blue-400',
  institutional: 'text-amber-400',
}
const TIER_LABEL: Record<string, string> = {
  free: 'Free', pro: 'Pro', institutional: 'Institutional',
}

const ADMIN_NAV: NavItem[] = [
  { label: 'Dashboard',   href: '/admin',           icon: LayoutDashboard, exact: true },
  { label: 'Verify',      href: '/app/verify',      icon: ShieldCheck },
  { label: 'Tickets',     href: '/admin/tickets',   icon: Ticket },
  { label: 'Reports',     href: '/admin/reports',   icon: BarChart3 },
  { label: 'Finance',     href: '/admin/finance',   icon: DollarSign },
  { label: 'Staff',       href: '/admin/staff',     icon: Users },
  { label: 'Feedback',    href: '/admin/feedback',  icon: MessageSquare },
  { label: 'Users',       href: '/admin/users',     icon: UserCog },
  { label: 'Site Tester', href: '/admin/tester',    icon: Globe },
  { label: 'API Docs',    href: '/admin/api-docs',  icon: BookOpen },
]

function NavList({
  nav, pathname, collapsed, unreadCount, onNav,
}: {
  nav: NavItem[]
  pathname: string
  collapsed: boolean
  unreadCount: number
  onNav?: () => void
}) {
  return (
    <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
      {nav.map(item => {
        const active = item.exact
          ? pathname === item.href
          : pathname === item.href || pathname.startsWith(item.href + '/')
        const Icon = item.icon
        const badge = item.href === '/admin/tickets' ? unreadCount : (item.badge ?? 0)
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNav}
            title={collapsed ? item.label : undefined}
            className={`relative flex items-center gap-3 rounded-lg text-sm font-medium transition-all duration-150 group
              ${collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2.5'}
              ${active
                ? 'bg-blue-500/[0.12] text-white'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.05]'
              }`}
          >
            {active && !collapsed && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-blue-400 rounded-r-full" />
            )}
            <Icon
              size={17}
              className={`shrink-0 transition-colors ${active ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'}`}
            />
            {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
            {!collapsed && badge > 0 && (
              <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                {badge > 99 ? '99+' : badge}
              </span>
            )}
            {collapsed && badge > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500" />
            )}
          </Link>
        )
      })}
    </nav>
  )
}

function UserFooter({
  email, tier, role, collapsed, onSignOut,
}: {
  email: string
  tier: Tier
  role: string
  collapsed: boolean
  onSignOut: () => void
}) {
  const initials = email.slice(0, 2).toUpperCase()
  return (
    <div className="border-t border-white/[0.07] p-2 shrink-0 space-y-1">
      <div className={`flex items-center gap-2.5 px-2 py-2 rounded-lg ${collapsed ? 'justify-center' : ''}`}>
        <div className="w-7 h-7 rounded-full bg-blue-600/25 border border-blue-500/30 flex items-center justify-center text-[11px] font-bold text-blue-300 shrink-0">
          {initials}
        </div>
        {!collapsed && (
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-white truncate leading-tight">{email}</p>
            <p className={`text-[10px] tracking-wide font-semibold ${TIER_COLOR[tier] ?? 'text-slate-400'}`}>
              {TIER_LABEL[tier]} &middot; {role}
            </p>
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={onSignOut}
        title={collapsed ? 'Sign out' : undefined}
        className={`flex items-center gap-2.5 w-full px-2 py-2 rounded-lg text-xs text-slate-500 hover:text-white hover:bg-white/[0.06] transition-colors ${collapsed ? 'justify-center' : ''}`}
      >
        <LogOut size={15} className="shrink-0" />
        {!collapsed && <span>Sign out</span>}
      </button>
    </div>
  )
}

export function AdminSidebar({ email, tier, role, unreadCount = 0 }: Props) {
  const pathname = usePathname()
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  const nav = role === 'admin' ? ADMIN_NAV : ADMIN_NAV.filter(n => n.href !== '/admin/finance')

  async function signOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  return (
    <>
      {/* ── Desktop sidebar ─────────────────────────────────────── */}
      <aside
        className={`hidden lg:flex flex-col h-screen sticky top-0 bg-[#06111f] border-r border-white/[0.07] shrink-0 transition-[width] duration-200
          ${collapsed ? 'w-[60px]' : 'w-[220px]'}`}
      >
        {/* Logo row */}
        <div className={`flex items-center h-[60px] border-b border-white/[0.07] px-3 shrink-0
          ${collapsed ? 'justify-center' : 'justify-between'}`}>
          {!collapsed && (
            <Link href="/" className="font-display font-extrabold text-[17px] text-white tracking-tight">
              Veri<span className="text-blue-400">Ghana</span>
            </Link>
          )}
          <button
            type="button"
            onClick={() => setCollapsed(c => !c)}
            className="w-7 h-7 flex items-center justify-center rounded-md text-slate-500 hover:text-white hover:bg-white/10 transition-colors"
          >
            {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        </div>

        <NavList nav={nav} pathname={pathname} collapsed={collapsed} unreadCount={unreadCount} />
        <UserFooter email={email} tier={tier} role={role} collapsed={collapsed} onSignOut={signOut} />
      </aside>

      {/* ── Mobile top bar ──────────────────────────────────────── */}
      <div className="lg:hidden sticky top-0 z-50 flex items-center h-14 px-4 gap-3 bg-[#06111f] border-b border-white/[0.07] shrink-0">
        <button
          type="button"
          onClick={() => setMobileOpen(o => !o)}
          className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white transition-colors"
        >
          {mobileOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
        <Link href="/" className="font-display font-extrabold text-lg text-white tracking-tight">
          Veri<span className="text-blue-400">Ghana</span>
        </Link>
        {unreadCount > 0 && (
          <span className="ml-auto min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </div>

      {/* ── Mobile drawer ───────────────────────────────────────── */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="w-64 h-full bg-[#06111f] border-r border-white/[0.07] flex flex-col overflow-y-auto">
            <div className="flex items-center justify-between h-14 px-4 border-b border-white/[0.07] shrink-0">
              <Link href="/" className="font-display font-extrabold text-lg text-white tracking-tight">
                Veri<span className="text-blue-400">Ghana</span>
              </Link>
              <button type="button" onClick={() => setMobileOpen(false)} title="Close menu" aria-label="Close menu" className="text-slate-400 hover:text-white">
                <X size={18} />
              </button>
            </div>
            <NavList
              nav={nav}
              pathname={pathname}
              collapsed={false}
              unreadCount={unreadCount}
              onNav={() => setMobileOpen(false)}
            />
            <UserFooter email={email} tier={tier} role={role} collapsed={false} onSignOut={signOut} />
          </div>
          <div className="flex-1 bg-black/60" onClick={() => setMobileOpen(false)} />
        </div>
      )}
    </>
  )
}
