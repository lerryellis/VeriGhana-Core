'use server'

import { revalidatePath } from 'next/cache'
import { createClient } from '@/lib/supabase/server'

async function adminClient() {
  const { createClient: createAdmin } = await import('@supabase/supabase-js')
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!
  const key = process.env.SUPABASE_SERVICE_KEY!
  return createAdmin(url, key, { auth: { autoRefreshToken: false, persistSession: false } })
}

export async function deleteUser(userId: string): Promise<{ error?: string }> {
  try {
    // Only admins may call this — verify caller's session
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return { error: 'Unauthorized' }

    const { data: profile } = await supabase
      .from('user_profiles')
      .select('role')
      .eq('user_id', user.id)
      .single()
    if (profile?.role !== 'admin') return { error: 'Forbidden' }

    const admin = await adminClient()
    const { error } = await admin.auth.admin.deleteUser(userId)
    if (error) return { error: error.message }

    revalidatePath('/admin/users')
    return {}
  } catch (e) {
    return { error: String(e) }
  }
}

export async function changeUserPlan(
  userId: string,
  tier: 'free' | 'pro' | 'institutional'
): Promise<{ error?: string }> {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return { error: 'Unauthorized' }

    const { data: profile } = await supabase
      .from('user_profiles')
      .select('role')
      .eq('user_id', user.id)
      .single()
    if (profile?.role !== 'admin') return { error: 'Forbidden' }

    const admin = await adminClient()
    const { error } = await admin
      .from('user_profiles')
      .update({ tier, subscription_status: tier === 'free' ? 'active' : 'active' })
      .eq('user_id', userId)
    if (error) return { error: error.message }

    revalidatePath('/admin/users')
    return {}
  } catch (e) {
    return { error: String(e) }
  }
}
