'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { TierChip } from '@/components/ui/TierChip'
import type { UserProfile } from '../account/page'
import type { PaymentRecord } from './page'

const API_URL         = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const PAYSTACK_PK     = process.env.NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY ?? ''

import { GRA_TAX } from '@/lib/constants'
function toPesewas(ghs: number) { return Math.round(ghs * 100) }

declare global {
  interface Window {
    PaystackPop: {
      setup(opts: {
        key: string
        email: string
        amount: number
        currency?: string
        channels?: string[]
        phone?: string
        metadata?: Record<string, unknown>
        callback: (response: { reference: string }) => void
        onClose: () => void
        [key: string]: unknown
      }): { openIframe(): void }
    }
  }
}

type Plan = 'pro' | 'institutional'
type Billing = 'monthly' | 'annual'

const PLANS: Record<Plan, {
  name: string
  monthlyPrice: number
  annualPrice: number
  perks: string[]
  accent: string
  border: string
  bg: string
  btn: string
}> = {
  pro: {
    name: 'Pro',
    monthlyPrice: 0.99,
    annualPrice: 0.79,
    perks: ['Unlimited verifications', 'All AI models', 'API key access', 'History export', 'Priority support'],
    accent: 'text-blue-700',
    border: 'border-blue-300',
    bg: 'bg-blue-50',
    btn: 'bg-blue-600 hover:bg-blue-500',
  },
  institutional: {
    name: 'Institutional',
    monthlyPrice: 1.99,
    annualPrice: 1.59,
    perks: ['Everything in Pro', 'Bulk verify (20 claims)', 'Team seats', 'Priority + SLA support', 'Custom integrations'],
    accent: 'text-teal-700',
    border: 'border-teal-300',
    bg: 'bg-teal-50',
    btn: 'bg-teal-600 hover:bg-teal-500',
  },
}

const PAYMENT_METHODS = [
  { id: 'mtn_momo', label: 'MTN Mobile Money', flag: '🇬🇭' },
  { id: 'vodafone_cash', label: 'Vodafone Cash', flag: '🇬🇭' },
  { id: 'airteltigo_money', label: 'AirtelTigo Money', flag: '🇬🇭' },
  { id: 'card', label: 'Debit / Credit Card', flag: '💳' },
]

interface Props {
  profile: UserProfile | null
  authEmail: string
  accessToken: string
  payments: PaymentRecord[]
  role?: string
}

export function BillingClient({ profile, authEmail, accessToken, payments, role = 'user' }: Props) {
  const router = useRouter()
  const isPrivileged = role === 'admin' || role === 'staff'
  const tier = profile?.tier ?? 'free'
  const isPaid = tier !== 'free'
  const isCancelled = !!(profile?.cancelled_at)
  const expiresAt = profile?.subscription_expires_at

  // URL ?plan= pre-selection
  const [billing, setBilling] = useState<Billing>('monthly')
  const [selectedPlan, setSelectedPlan] = useState<Plan>('pro')

  // Form state
  const [payMethod, setPayMethod] = useState(PAYMENT_METHODS[0].id)
  const [phone, setPhone] = useState(profile?.phone ?? '')
  const [fullName, setFullName] = useState(profile?.full_name ?? '')
  const [promoCode, setPromoCode] = useState('')
  const [promoDiscount, setPromoDiscount] = useState(0)
  const [promoValid, setPromoValid] = useState<boolean | null>(null)
  const [promoChecking, setPromoChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  async function validatePromo() {
    const code = promoCode.trim().toUpperCase()
    if (!code) { setPromoValid(null); setPromoDiscount(0); return }
    setPromoChecking(true)
    try {
      const supabase = createClient()
      const { data } = await supabase
        .from('vg_promo_codes')
        .select('discount_pct, is_active, max_uses, uses_count, valid_until')
        .eq('code', code)
        .single()
      if (!data || !data.is_active) {
        setPromoValid(false); setPromoDiscount(0)
      } else if (data.max_uses && data.uses_count >= data.max_uses) {
        setPromoValid(false); setPromoDiscount(0)
      } else if (data.valid_until && new Date(data.valid_until) < new Date()) {
        setPromoValid(false); setPromoDiscount(0)
      } else {
        setPromoValid(true); setPromoDiscount(data.discount_pct ?? 0)
      }
    } catch {
      setPromoValid(false); setPromoDiscount(0)
    } finally {
      setPromoChecking(false)
    }
  }

  const plan       = PLANS[selectedPlan]
  const basePrice  = billing === 'annual' ? plan.annualPrice : plan.monthlyPrice
  const price      = promoDiscount > 0 ? Math.round(basePrice * (1 - promoDiscount / 100) * 100) / 100 : basePrice
  const savingsPct = Math.round((1 - plan.annualPrice / plan.monthlyPrice) * 100)

  // Tax breakdown (all levies applied on subtotal per GRA re-coupling 2026)
  const subtotal     = billing === 'annual' ? price * 12 : price
  const vatAmount    = Math.round(subtotal * GRA_TAX.vat     * 100) / 100
  const nhilAmount   = Math.round(subtotal * GRA_TAX.nhil    * 100) / 100
  const getfundAmount = Math.round(subtotal * GRA_TAX.getfund * 100) / 100
  const totalTax     = Math.round((vatAmount + nhilAmount + getfundAmount) * 100) / 100
  const totalPrice   = Math.round((subtotal + totalTax) * 100) / 100

  // Load Paystack script
  useEffect(() => {
    if (document.getElementById('paystack-js')) return
    const s = document.createElement('script')
    s.id  = 'paystack-js'
    s.src = 'https://js.paystack.co/v1/inline.js'
    document.body.appendChild(s)
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!fullName.trim()) { setMsg({ type: 'error', text: 'Full name is required.' }); return }
    if (payMethod !== 'card' && !phone.trim()) { setMsg({ type: 'error', text: 'Mobile Money number is required.' }); return }
    if (!PAYSTACK_PK) { setMsg({ type: 'error', text: 'Payment not configured. Contact support.' }); return }
    if (!window.PaystackPop) { setMsg({ type: 'error', text: 'Payment script not loaded. Refresh and try again.' }); return }

    setMsg(null)

    const isCard    = payMethod === 'card'
    const channels  = isCard ? ['card'] : ['mobile_money']
    const amount    = toPesewas(totalPrice)   // tax-inclusive total in pesewas

    const handler = window.PaystackPop.setup({
      key:      PAYSTACK_PK,
      email:    authEmail,
      amount,
      currency: 'GHS',
      channels,
      phone:    phone || undefined,
      metadata: {
        custom_fields: [
          { display_name: 'Full Name',     variable_name: 'full_name',     value: fullName },
          { display_name: 'Plan',          variable_name: 'plan_key',      value: selectedPlan },
          { display_name: 'Billing Cycle', variable_name: 'billing_cycle', value: billing },
          { display_name: 'Phone',         variable_name: 'phone',         value: phone },
          { display_name: 'Promo Code',    variable_name: 'promo_code',    value: promoCode },
        ],
        plan_key:      selectedPlan,
        billing_cycle: billing,
        full_name:     fullName,
        phone,
        promo_code:    promoCode,
      },
      callback: (response: { reference: string }) => {
        setSubmitting(true)
        fetch(`${API_URL}/payment/verify`, {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            reference:      response.reference,
            plan_key:       selectedPlan,
            billing_cycle:  billing,
            full_name:      fullName,
            phone:          phone || undefined,
            promo_code:     promoCode || undefined,
            payment_method: payMethod,
          }),
        })
          .then(res => {
            if (!res.ok) return res.json().catch(() => ({})).then((e: { detail?: string }) => { throw new Error(e.detail ?? `Verification failed (${res.status})`) })
            setMsg({ type: 'success', text: `Payment successful! Your ${plan.name} plan is now active.` })
            setTimeout(() => router.refresh(), 1500)
          })
          .catch((err: Error) => {
            setMsg({ type: 'error', text: err.message })
          })
          .finally(() => {
            setSubmitting(false)
          })
      },
      onClose: () => {
        setMsg({ type: 'error', text: 'Payment window closed. Try again when ready.' })
      },
    })

    handler.openIframe()
  }

  if (isPrivileged) {
    return (
      <div className="max-w-2xl mx-auto space-y-5">
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">Billing</h1>
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center">
          <p className="text-2xl mb-2">🔑</p>
          <p className="font-semibold text-[#0f2240]">Admin accounts are not tied to a subscription plan.</p>
          <p className="text-sm text-slate-400 mt-1">You have full platform access. Billing only applies to regular user accounts.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <h1 className="font-display font-bold text-2xl text-[#0f2240]">Billing</h1>

      {/* Current plan */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Current Plan</p>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <TierChip tier={tier as 'free' | 'pro' | 'institutional'} />
            {isCancelled && (
              <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Cancelled</span>
            )}
          </div>
          {isPaid && expiresAt && (
            <p className="text-xs text-slate-400 font-mono-vg">
              {isCancelled ? 'Access until' : 'Renews'}{' '}
              {new Date(expiresAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          )}
        </div>
        {tier === 'free' && (
          <p className="text-sm text-slate-500 mt-2">5 verifications/day · Basic models only</p>
        )}
      </div>

      {/* Entitlements — what you get on your current plan */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Your Plan Includes</p>
        <div className="space-y-2">
          {[
            { feature: 'Daily verifications',     free: '5 / day',      pro: 'Unlimited',  inst: 'Unlimited' },
            { feature: 'AI verification models',  free: 'Basic only',   pro: 'All models', inst: 'All models' },
            { feature: 'Bulk claim verification', free: false,          pro: false,        inst: 'Up to 20 claims' },
            { feature: 'Verification history',    free: 'Last 7 days',  pro: 'Full history', inst: 'Full history' },
            { feature: 'History export (CSV)',    free: false,          pro: true,         inst: true },
            { feature: 'API key access',          free: false,          pro: true,         inst: true },
            { feature: 'Team seats',              free: false,          pro: false,        inst: true },
            { feature: 'Support',                 free: 'Community',    pro: 'Priority email', inst: 'Priority + SLA' },
            { feature: 'Custom integrations',     free: false,          pro: false,        inst: true },
            { feature: 'Invoice & receipts',      free: false,          pro: true,         inst: true },
          ].map(row => {
            const val = tier === 'institutional' ? row.inst : tier === 'pro' ? row.pro : row.free
            const included = val !== false
            return (
              <div key={row.feature} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                <span className="text-sm text-slate-600">{row.feature}</span>
                <span className={`text-sm font-medium ${included ? 'text-green-600' : 'text-slate-300'}`}>
                  {val === true ? '✓' : val === false ? '—' : String(val)}
                </span>
              </div>
            )
          })}
        </div>
        {tier === 'free' && (
          <p className="text-xs text-slate-400 mt-4 font-mono-vg">Upgrade to unlock more features →</p>
        )}
      </div>

      {/* Upgrade section — hidden if already on institutional */}
      {tier !== 'institutional' && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-5">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Upgrade Plan</p>
            {/* Billing toggle */}
            <div className="flex items-center gap-1 bg-slate-100 rounded-full p-1">
              {(['monthly', 'annual'] as Billing[]).map(b => (
                <button
                  key={b}
                  type="button"
                  onClick={() => setBilling(b)}
                  className={`text-xs px-3 py-1 rounded-full transition-colors font-medium ${
                    billing === b ? 'bg-white text-[#0f2240] shadow-sm' : 'text-slate-500'
                  }`}
                >
                  {b === 'annual' ? `Annual (save ${savingsPct}%)` : 'Monthly'}
                </button>
              ))}
            </div>
          </div>

          {/* Plan cards */}
          <div className="grid grid-cols-2 gap-3">
            {(Object.entries(PLANS) as [Plan, typeof PLANS[Plan]][]).map(([key, p]) => (
              <button
                key={key}
                type="button"
                onClick={() => setSelectedPlan(key)}
                className={`text-left border-2 rounded-xl p-4 transition-all ${
                  selectedPlan === key
                    ? `${p.border} ${p.bg}`
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className={`font-display font-bold text-sm ${p.accent}`}>{p.name}</div>
                  {selectedPlan === key && (
                    <span className="w-4 h-4 rounded-full bg-blue-600 flex items-center justify-center">
                      <span className="text-white text-[0.6rem]">✓</span>
                    </span>
                  )}
                </div>
                <div className={`text-2xl font-display font-extrabold ${p.accent} mb-1`}>
                  ₵{billing === 'annual' ? p.annualPrice : p.monthlyPrice}
                  <span className="text-xs font-normal text-slate-400">/mo</span>
                </div>
                {billing === 'annual' && (
                  <div className="text-[0.65rem] text-slate-400 mb-2">billed annually</div>
                )}
                <ul className="space-y-1">
                  {p.perks.map(perk => (
                    <li key={perk} className={`text-xs flex items-start gap-1.5 ${p.accent}`}>
                      <span className="font-bold mt-px">✓</span>{perk}
                    </li>
                  ))}
                </ul>
              </button>
            ))}
          </div>

          {/* Checkout form */}
          <form onSubmit={handleSubmit} className="space-y-4 pt-2 border-t border-slate-100">
            <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest">Payment Details</p>

            {/* Name */}
            <div>
              <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Your full name"
                className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
              />
            </div>

            {/* Payment method */}
            <div>
              <label className="block text-xs text-slate-400 mb-2 font-mono-vg uppercase tracking-wider">Payment Method</label>
              <div className="grid grid-cols-2 gap-2">
                {PAYMENT_METHODS.map(pm => (
                  <button
                    key={pm.id}
                    type="button"
                    onClick={() => setPayMethod(pm.id)}
                    className={`flex items-center gap-2 border rounded-lg px-3 py-2.5 text-sm transition-colors ${
                      payMethod === pm.id
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-slate-200 text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <span>{pm.flag}</span>
                    <span className="text-xs font-medium">{pm.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Phone — only for MoMo methods */}
            {payMethod !== 'card' && (
              <div>
                <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Mobile Money Number</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={e => setPhone(e.target.value)}
                  placeholder="+233 XX XXX XXXX"
                  className="w-full bg-slate-50 border border-slate-200 text-slate-700 text-sm px-3 py-2 rounded-lg outline-none focus:border-blue-400 transition-colors"
                />
              </div>
            )}

            {/* Promo code */}
            <div>
              <label className="block text-xs text-slate-400 mb-1 font-mono-vg uppercase tracking-wider">Promo Code (optional)</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={promoCode}
                  onChange={e => { setPromoCode(e.target.value.toUpperCase()); setPromoValid(null); setPromoDiscount(0) }}
                  placeholder="GIMPA2026"
                  className={`flex-1 bg-slate-50 border text-slate-700 text-sm px-3 py-2 rounded-lg outline-none transition-colors font-mono-vg ${
                    promoValid === true ? 'border-green-400' : promoValid === false ? 'border-red-300' : 'border-slate-200 focus:border-blue-400'
                  }`}
                />
                <button
                  type="button"
                  onClick={validatePromo}
                  disabled={!promoCode.trim() || promoChecking}
                  className="text-xs font-medium px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors disabled:opacity-40"
                >
                  {promoChecking ? '…' : 'Apply'}
                </button>
              </div>
              {promoValid === true && (
                <p className="text-xs text-green-600 mt-1 font-mono-vg">{promoDiscount}% discount applied!</p>
              )}
              {promoValid === false && (
                <p className="text-xs text-red-500 mt-1 font-mono-vg">Invalid, expired, or fully used code.</p>
              )}
            </div>

            {/* Order summary with tax breakdown */}
            <div className="bg-slate-50 rounded-xl px-4 py-3 space-y-2">
              <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-3">Order Summary</p>
              <div className="flex justify-between text-sm text-slate-600">
                <span>{plan.name} · {billing === 'annual' ? 'Annual' : 'Monthly'}</span>
                <span>₵{subtotal.toFixed(2)}</span>
              </div>
              {promoDiscount > 0 && (
                <div className="flex justify-between text-sm text-green-600">
                  <span>Promo discount (−{promoDiscount}%)</span>
                  <span>−₵{(basePrice * (billing === 'annual' ? 12 : 1) * promoDiscount / 100).toFixed(2)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm text-slate-500">
                <span>VAT (15%)</span>
                <span>+₵{vatAmount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm text-slate-500">
                <span>NHIL (2.5%)</span>
                <span>+₵{nhilAmount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm text-slate-500">
                <span>GETFund Levy (2.5%)</span>
                <span>+₵{getfundAmount.toFixed(2)}</span>
              </div>
              <div className="border-t border-slate-200 pt-2 flex justify-between items-baseline">
                <span className="text-sm font-medium text-slate-600">Total due</span>
                <span className="text-xl font-display font-extrabold text-[#0f2240]">₵{totalPrice.toFixed(2)}</span>
              </div>
              <p className="text-[0.65rem] text-slate-400 font-mono-vg text-right">Taxes per GRA (VAT + NHIL + GETFund = 20%)</p>
            </div>

            {/* Status message */}
            {msg && (
              <div className={`text-sm px-4 py-3 rounded-xl ${
                msg.type === 'success'
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-600'
              }`}>
                {msg.text}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              {submitting
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Processing…</>
                : `Upgrade to ${plan.name} — ₵${price}/mo`
              }
            </button>

            <p className="text-xs text-slate-400 text-center">
              By upgrading you agree to our Terms of Service. Cancel anytime.
            </p>
          </form>
        </div>
      )}

      {/* Payment history */}
      {payments.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-4">Payment History</p>
          <div className="space-y-2">
            {payments.map(p => (
              <div key={p.id} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-[#0f2240] capitalize">{p.plan} plan</p>
                  <p className="text-xs text-slate-400 font-mono-vg">
                    {new Date(p.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                    {p.payment_method && ` · ${p.payment_method.replace(/_/g, ' ')}`}
                  </p>
                  {p.order_ref && (
                    <p className="text-xs text-slate-400 font-mono-vg mt-0.5">Ref: {p.order_ref}</p>
                  )}
                </div>
                <div className="text-right flex flex-col items-end gap-1">
                  <p className="text-sm font-display font-bold text-[#0f2240]">
                    {p.currency} {p.amount.toFixed(2)}
                  </p>
                  <span className={`text-xs font-mono-vg px-2 py-0.5 rounded-full ${
                    p.status === 'completed' || p.status === 'success' || p.status === 'succeeded'
                      ? 'bg-green-100 text-green-700'
                      : p.status === 'pending'
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {p.status}
                  </span>
                  {p.id && (
                    <a
                      href={`/app/billing/invoice/${p.id}`}
                      className="text-xs text-blue-600 hover:underline font-mono-vg"
                    >
                      Invoice ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
