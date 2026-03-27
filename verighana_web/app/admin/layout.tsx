import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { AppNav } from '@/components/app/AppNav'

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const { data: profile } = await supabase
    .from('user_profiles')
    .select('tier, role')
    .eq('user_id', user.id)
    .single()

  const role = profile?.role ?? 'user'
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
    <div className="min-h-screen bg-[#f0f4f8] flex flex-col">
      <AppNav
        email={user.email ?? ''}
        tier={(profile?.tier ?? 'free') as 'free' | 'pro' | 'institutional'}
        role={role}
        unreadCount={unreadCount}
      />
      <main className="flex-1 px-4 md:px-8 py-6 max-w-5xl mx-auto w-full">
        {children}
      </main>
    </div>
  )
}
