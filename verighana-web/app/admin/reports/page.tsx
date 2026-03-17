import { ReportsClient } from './ReportsClient'

const API_URL   = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

export type Payment = {
  id: string
  order_ref: string
  created_at: string
  user_email: string
  full_name: string
  plan_label: string
  plan_key: string
  amount: number
  currency: string
  payment_method: string
  status: string
  country: string
  promo_code: string | null
}

async function fetchPayments(): Promise<Payment[]> {
  try {
    const res = await fetch(`${API_URL}/admin/payments?limit=1000`, {
      headers: { 'X-Admin-Key': ADMIN_KEY },
      cache: 'no-store',
    })
    if (!res.ok) return []
    const data = await res.json() as { payments: Payment[] }
    return data.payments ?? []
  } catch {
    return []
  }
}

export default async function ReportsPage() {
  const payments = await fetchPayments()
  return <ReportsClient payments={payments} />
}
