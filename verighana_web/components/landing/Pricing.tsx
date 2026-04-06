'use client'

import { useState } from 'react'
import Link from 'next/link'

const plans = [
  {
    name: 'Free',
    monthlyPrice: '₵0',
    annualPrice: '₵0',
    period: '/mo',
    tagline: 'For curious citizens',
    features: ['5 fact-check queries per day', 'Basic Truth Meter scoring', 'Public fact database access', 'Source citations included'],
    cta: 'Get Started Free',
    href: '/register',
    style: 'ghost',
    headerClass: 'bg-slate-100',
    nameClass: 'text-[#0f2240]',
    featColor: 'text-green-600',
  },
  {
    name: 'Pro',
    monthlyPrice: '₵0.99',
    annualPrice: '₵0.79',
    period: '/mo',
    tagline: 'For journalists & researchers',
    features: ['Unlimited fact-check queries', 'Full AI verification reports', 'Detailed source citations', 'Personal REST API key', 'Real-time misinformation alerts', 'Verification history export'],
    cta: 'Get Pro Access',
    href: '/register?plan=pro',
    style: 'blue',
    featured: true,
    headerClass: 'bg-gradient-to-br from-[#1a3560] to-[#0f2240]',
    nameClass: 'text-white',
    featColor: 'text-blue-400',
  },
  {
    name: 'Institutional',
    monthlyPrice: '₵1.99',
    annualPrice: '₵1.59',
    period: '/mo',
    tagline: "For newsrooms, NGOs & gov't",
    features: ['Multi-user seat management', 'Bulk API processing', 'White-label reporting', 'Custom analytics dashboard', 'Priority SLA support', 'Research dataset access'],
    cta: 'Contact Sales',
    href: 'mailto:contact@verighana.gh',
    style: 'green',
    headerClass: 'bg-gradient-to-br from-teal-800 to-[#0f2240]',
    nameClass: 'text-white',
    featColor: 'text-green-400',
  },
]

export function Pricing() {
  const [annual, setAnnual]     = useState(false)
  const [hovered, setHovered]   = useState<string | null>(null)

  return (
    <section id="pricing" className="py-20 px-[5%] bg-white text-center">
      <p className="text-xs font-mono-vg text-blue-600 uppercase tracking-widest mb-2">Simple, transparent pricing</p>
      <h2 className="font-display text-3xl font-extrabold text-[#0f2240] tracking-tight mb-2">Choose Your Plan</h2>
      <p className="text-slate-500 mb-8">Start free. Upgrade when you need more power.</p>

      {/* Billing toggle */}
      <div className="flex items-center justify-center gap-3 mb-10">
        <span className={`text-sm ${!annual ? 'text-[#0f2240] font-semibold' : 'text-slate-400'}`}>Monthly</span>
        <button
          type="button"
          onClick={() => setAnnual(a => !a)}
          className={`relative w-11 h-6 rounded-full transition-colors ${annual ? 'bg-blue-600' : 'bg-slate-300'}`}
          aria-label="Toggle billing"
        >
          <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${annual ? 'translate-x-5' : ''}`} />
        </button>
        <span className={`text-sm ${annual ? 'text-[#0f2240] font-semibold' : 'text-slate-400'}`}>Annual</span>
        {annual && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-semibold">Save 20%</span>}
      </div>

      <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
        {plans.map(p => {
          const isHovered  = hovered === p.name
          const isDimmed   = hovered !== null && !isHovered
          return (
          <div
            key={p.name}
            onMouseEnter={() => setHovered(p.name)}
            onMouseLeave={() => setHovered(null)}
            className={`rounded-xl overflow-hidden border transition-all duration-200 cursor-pointer
              ${p.featured && !hovered ? 'border-blue-400/40 shadow-xl shadow-blue-900/20 scale-[1.02]' : ''}
              ${p.featured && isHovered  ? 'border-blue-400/60' : ''}
              ${!p.featured             ? 'border-slate-200' : ''}
              ${isHovered  ? 'scale-[1.05] shadow-2xl shadow-slate-300/60 z-10 relative' : ''}
              ${isDimmed   ? 'opacity-50 scale-[0.98]' : ''}
            `}
          >
            <div className={`px-6 py-5 ${p.headerClass}`}>
              <div className={`font-display font-extrabold text-base tracking-wide ${p.nameClass}`}>{p.name}</div>
              <div className="flex items-baseline gap-1 mt-1">
                <span className={`font-display text-3xl font-extrabold ${p.nameClass}`}>
                  {annual ? p.annualPrice : p.monthlyPrice}
                </span>
                <span className={`text-sm ${p.featured ? 'text-slate-300' : 'text-slate-500'}`}>{p.period}</span>
              </div>
              <p className={`text-xs mt-1 ${p.featured ? 'text-slate-300' : 'text-slate-500'}`}>{p.tagline}</p>
            </div>

            <div className="p-6 bg-white">
              <ul className="space-y-2 mb-6 text-left">
                {p.features.map(f => (
                  <li key={f} className="flex items-center gap-2 text-sm text-slate-600">
                    <span className={`font-bold ${p.featColor}`}>✓</span>{f}
                  </li>
                ))}
              </ul>

              <Link
                href={p.href}
                className={`block w-full text-center text-sm font-medium px-5 py-2.5 rounded-lg transition-all
                  ${p.style === 'blue' ? 'bg-blue-600 hover:bg-blue-500 text-white' :
                    p.style === 'green' ? 'bg-teal-600 hover:bg-teal-500 text-white' :
                    'border border-slate-300 hover:border-slate-400 text-[#0f2240]'}`}
              >
                {p.cta}
              </Link>
            </div>
          </div>
        )})}
      </div>
    </section>
  )
}
