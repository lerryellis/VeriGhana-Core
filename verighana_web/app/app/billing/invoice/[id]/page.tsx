import { redirect, notFound } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { PrintButton } from './PrintButton'

const API_URL   = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

type Payment = {
  id: string
  order_ref: string
  created_at: string
  user_email: string
  full_name: string
  plan_label: string
  plan_key: string
  amount: number
  tax_rate: number | null
  tax_amount: number | null
  currency: string
  payment_method: string
  status: string
  country: string
  promo_code: string | null
}

export default async function InvoicePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const res = await fetch(`${API_URL}/admin/payments/${id}/invoice`, {
    headers: { 'X-Admin-Key': ADMIN_KEY },
    cache: 'no-store',
  })
  if (!res.ok) notFound()
  const p: Payment = await res.json()

  // Access control: only the payment owner or admin can view this invoice
  const adminEmails = (process.env.ADMIN_EMAIL ?? '').split(',').map(e => e.trim().toLowerCase())
  const isAdmin = adminEmails.includes((user.email ?? '').toLowerCase())
  const { data: profile } = await supabase.from('user_profiles').select('role').eq('user_id', user.id).single()
  const isOwner = p.user_email?.toLowerCase() === (user.email ?? '').toLowerCase()
  if (!isOwner && !isAdmin && profile?.role !== 'admin' && profile?.role !== 'staff') notFound()

  const date       = new Date(p.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
  const planMap: Record<string, string> = { pro: 'Pro Plan', institutional: 'Institutional Plan' }
  const planName   = planMap[p.plan_key] ?? p.plan_label ?? 'Subscription'
  const subtotal      = parseFloat(String(p.amount))
  // GRA levies (Jan 2026): VAT 15% + NHIL 2.5% + GETFund 2.5% = 20%
  const vatAmount     = Math.round(subtotal * 0.15  * 100) / 100
  const nhilAmount    = Math.round(subtotal * 0.025 * 100) / 100
  const getfundAmount = Math.round(subtotal * 0.025 * 100) / 100
  const totalTaxAmt   = p.tax_amount ?? Math.round((vatAmount + nhilAmount + getfundAmount) * 100) / 100
  const total         = Math.round((subtotal + totalTaxAmt) * 100) / 100
  const currency      = (p.currency ?? 'USD').toUpperCase()

  return (
    <>
      {/* Print button — hidden when printing */}
      <div className="print:hidden flex justify-end gap-3 px-8 pt-6 pb-2 max-w-3xl mx-auto">
        <PrintButton />
        <a
          href="/app/billing"
          className="text-sm text-slate-500 hover:text-slate-700 px-4 py-2.5 rounded-lg border border-slate-200 transition-colors"
        >
          ← Back to Billing
        </a>
      </div>

      {/* Invoice document */}
      <div id="invoice" className="max-w-3xl mx-auto px-8 py-8 print:p-0 print:max-w-none">
        {/* Header */}
        <div className="flex items-start justify-between mb-10">
          <div>
            <div className="font-display font-extrabold text-2xl text-[#0f2240]">
              Veri<span className="text-blue-500">Ghana</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">fact-checking platform</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-400 uppercase tracking-widest font-mono">Invoice</p>
            <p className="font-display font-bold text-lg text-[#0f2240] mt-0.5">{p.order_ref}</p>
            <p className="text-xs text-slate-500 mt-0.5">{date}</p>
          </div>
        </div>

        {/* Bill to */}
        <div className="grid grid-cols-2 gap-8 mb-10">
          <div>
            <p className="text-[0.65rem] text-slate-400 uppercase tracking-widest font-mono mb-2">Bill To</p>
            <p className="font-medium text-[#0f2240]">{p.full_name || '—'}</p>
            <p className="text-sm text-slate-500">{p.user_email}</p>
            {p.country && <p className="text-sm text-slate-500">{p.country}</p>}
          </div>
          <div>
            <p className="text-[0.65rem] text-slate-400 uppercase tracking-widest font-mono mb-2">Payment Details</p>
            <p className="text-sm text-slate-600">Method: <span className="font-medium text-slate-800">{p.payment_method?.replace(/_/g, ' ')}</span></p>
            <p className="text-sm text-slate-600 mt-0.5">Status: <span className={`font-medium ${p.status === 'succeeded' ? 'text-green-600' : 'text-red-500'}`}>{p.status}</span></p>
            {p.promo_code && <p className="text-sm text-slate-600 mt-0.5">Promo: <span className="font-medium text-blue-600">{p.promo_code}</span></p>}
          </div>
        </div>

        {/* Line items */}
        <table className="w-full mb-8">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="text-left text-[0.65rem] text-slate-400 uppercase tracking-widest font-mono pb-2">Description</th>
              <th className="text-right text-[0.65rem] text-slate-400 uppercase tracking-widest font-mono pb-2">Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-slate-100">
              <td className="py-4">
                <p className="font-medium text-[#0f2240]">{planName}</p>
                <p className="text-xs text-slate-400 mt-0.5">VeriGhana subscription — {date}</p>
              </td>
              <td className="py-4 text-right font-medium text-[#0f2240]">{currency} {subtotal.toFixed(2)}</td>
            </tr>
            <tr className="border-b border-slate-100">
              <td className="py-2 text-sm text-slate-500">VAT (15%) — Ghana Revenue Authority</td>
              <td className="py-2 text-right text-sm text-slate-500">+{currency} {vatAmount.toFixed(2)}</td>
            </tr>
            <tr className="border-b border-slate-100">
              <td className="py-2 text-sm text-slate-500">NHIL (2.5%) — National Health Insurance Levy</td>
              <td className="py-2 text-right text-sm text-slate-500">+{currency} {nhilAmount.toFixed(2)}</td>
            </tr>
            <tr className="border-b border-slate-100">
              <td className="py-2 text-sm text-slate-500">GETFund Levy (2.5%)</td>
              <td className="py-2 text-right text-sm text-slate-500">+{currency} {getfundAmount.toFixed(2)}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td className="pt-4 text-sm text-slate-500">Total</td>
              <td className="pt-4 text-right font-display font-bold text-xl text-[#0f2240]">{currency} {total.toFixed(2)}</td>
            </tr>
          </tfoot>
        </table>

        {/* Footer */}
        <div className="border-t border-slate-100 pt-6 text-xs text-slate-400 text-center space-y-1">
          <p>VeriGhana · support@verighana.com · verighana.com</p>
          <p>This is an official receipt for your subscription payment.</p>
        </div>
      </div>

      <style>{`
        @media print {
          body { background: white; }
          nav, header, .print\\:hidden { display: none !important; }
          #invoice { margin: 0; padding: 40px; }
        }
      `}</style>
    </>
  )
}
