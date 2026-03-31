import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { AdminSidebar } from '@/components/app/AdminSidebar'

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('tier, role')
    .eq('user_id', user.id)
    .single()

  // Env-based superuser override — these emails are always admin regardless of DB
  const adminEmails = (process.env.ADMIN_EMAIL ?? '').split(',').map(e => e.trim().toLowerCase())
  const isEnvAdmin  = adminEmails.includes((user.email ?? '').toLowerCase())
  const role        = isEnvAdmin ? 'admin' : (profile?.role ?? 'user')

  if (role !== 'admin' && role !== 'staff') redirect('/app/verify')

  // Count open tickets + unread user follow-ups
  const { count: openCount } = await supabase
    .from('support_tickets')
    .select('id', { count: 'exact', head: true })
    .eq('status', 'open')

  const { count: followupCount } = await supabase
    .from('support_tickets')
    .select('id', { count: 'exact', head: true })
    .not('user_followup', 'is', null)
    .eq('user_followup_read', false)

  const unreadCount = (openCount ?? 0) + (followupCount ?? 0)

  return (
    <div className="min-h-screen bg-[#f0f4f8] flex flex-col lg:flex-row">
      <AdminSidebar
        email={user.email ?? ''}
        tier={(profile?.tier ?? 'free') as 'free' | 'pro' | 'institutional'}
        role={role}
        unreadCount={unreadCount}
      />
      <main className="flex-1 min-w-0 px-4 md:px-8 py-6 max-w-5xl w-full mx-auto">
        {children}
      </main>
    </div>
  )
}
