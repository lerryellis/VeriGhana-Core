'use server'

import { revalidatePath } from 'next/cache'
import { createClient } from '@/lib/supabase/server'

async function adminClient() {
  const { createClient: createAdmin } = await import('@supabase/supabase-js')
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!
  const key = process.env.SUPABASE_SERVICE_KEY!
  return createAdmin(url, key, { auth: { autoRefreshToken: false, persistSession: false } })
}

async function auditLog(adminEmail: string, action: string, targetId: string, targetEmail: string, details: Record<string, unknown> = {}) {
  try {
    const admin = await adminClient()
    await admin.from('admin_audit_log').insert({ admin_email: adminEmail, action, target_id: targetId, target_email: targetEmail, details })
  } catch { /* non-blocking */ }
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
    const { data: target } = await admin.from('user_profiles').select('email').eq('user_id', userId).single()
    const { error } = await admin.auth.admin.deleteUser(userId)
    if (error) return { error: error.message }

    await auditLog(user.email ?? '', 'delete_user', userId, target?.email ?? '', {})
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
    const { data: target } = await admin.from('user_profiles').select('email, tier').eq('user_id', userId).single()
    const { error } = await admin
      .from('user_profiles')
      .update({ tier, subscription_status: 'active' })
      .eq('user_id', userId)
    if (error) return { error: error.message }

    await auditLog(user.email ?? '', 'change_tier', userId, target?.email ?? '', { from: target?.tier, to: tier })
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
    const { data: target } = await admin.from('user_profiles').select('email, role').eq('user_id', userId).single()
    const { error } = await admin
      .from('user_profiles')
      .update({ role })
      .eq('user_id', userId)
    if (error) return { error: error.message }

    await auditLog(user.email ?? '', 'change_role', userId, target?.email ?? '', { from: target?.role, to: role })
    revalidatePath('/admin/users')
    return {}
  } catch (e) {
    return { error: String(e) }
  }
}

export type TimelineEvent = {
  type: 'signup' | 'payment' | 'ticket' | 'verification'
  date: string
  label: string
  detail: string
}

export async function getUserTimeline(userId: string, email: string): Promise<TimelineEvent[]> {
  try {
    const admin = await adminClient()
    const events: TimelineEvent[] = []

    // Payments
    const { data: payments } = await admin
      .from('payments').select('plan_label, amount, currency, created_at, status')
      .eq('user_id', userId).order('created_at', { ascending: false }).limit(10)
    for (const p of payments ?? []) {
      events.push({
        type: 'payment', date: p.created_at,
        label: `Payment: ${p.plan_label ?? 'Subscription'}`,
        detail: `$${p.amount} ${p.currency} — ${p.status}`,
      })
    }

    // Support tickets
    const { data: tickets } = await admin
      .from('support_tickets').select('subject, status, created_at, category')
      .eq('email', email).order('created_at', { ascending: false }).limit(10)
    for (const t of tickets ?? []) {
      events.push({
        type: 'ticket', date: t.created_at,
        label: `Ticket: ${t.subject}`,
        detail: `${t.category ?? 'General'} — ${t.status}`,
      })
    }

    // Verifications
    const { data: verifications } = await admin
      .from('vg_usage_logs').select('created_at, verdict, score, model_used')
      .eq('user_id', userId).order('created_at', { ascending: false }).limit(10)
    for (const v of verifications ?? []) {
      events.push({
        type: 'verification', date: v.created_at,
        label: `Verification: ${v.verdict ?? 'Unknown'}`,
        detail: `Score ${v.score ?? '—'} · ${v.model_used ?? 'Unknown model'}`,
      })
    }

    // Sort descending by date
    events.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    return events.slice(0, 20)
  } catch {
    return []
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
