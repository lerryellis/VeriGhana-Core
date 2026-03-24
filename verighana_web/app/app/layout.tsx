import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { AppNav } from '@/components/app/AppNav'

type Tier = 'free' | 'pro' | 'institutional'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) redirect('/login')

  // user_profiles is linked to Supabase Auth via user_id = auth.uid()
  const { data: profile } = await supabase
    .from('user_profiles')
    .select('tier, role')
    .eq('user_id', user.id)
    .single()

  const tier = (profile?.tier ?? 'free') as Tier
  const role = profile?.role ?? 'client'

  // Count tickets with an unread admin reply
  const { count: unreadCount } = await supabase
    .from('support_tickets')
    .select('id', { count: 'exact', head: true })
    .eq('user_id', user.id)
    .not('admin_reply', 'is', null)
    .eq('admin_reply_read', false)

  return (
    <div className="min-h-screen bg-[#f0f4f8] flex flex-col">
      <AppNav email={user.email ?? ''} tier={tier} role={role} unreadCount={unreadCount ?? 0} />
      <main className="flex-1 px-4 md:px-8 py-6 max-w-5xl mx-auto w-full">
        {children}
      </main>
    </div>
  )
}
