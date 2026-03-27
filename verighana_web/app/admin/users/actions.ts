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
      .update({ tier, subscription_status: 'active' })
      .eq('user_id', userId)
    if (error) return { error: error.message }

    revalidatePath('/admin/users')
    return {}
  } catch (e) {
    return { error: String(e) }
  }
}

export async function changeUserRole(
  userId: string,
  role: 'admin' | 'staff' | 'user'
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

    // Prevent removing your own admin role
    if (userId === user.id && role !== 'admin') return { error: 'Cannot remove your own admin role.' }

    const admin = await adminClient()
    const { error } = await admin
      .from('user_profiles')
      .update({ role })
      .eq('user_id', userId)
    if (error) return { error: error.message }

    revalidatePath('/admin/users')
    return {}
  } catch (e) {
    return { error: String(e) }
  }
}

export type UserPayment = {
  plan_label:     string
  amount:         number
  currency:       string
  payment_method: string
  created_at:     string
}

export async function getUserLastPayment(userId: string): Promise<UserPayment | null> {
  try {
    const admin = await adminClient()
    const { data } = await admin
      .from('payments')
      .select('plan_label,amount,currency,payment_method,created_at')
      .eq('user_id', userId)
      .eq('status', 'succeeded')
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()
    return data ?? null
  } catch {
    return null
  }
}
