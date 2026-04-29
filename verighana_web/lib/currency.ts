'use client'
import { useState, useEffect } from 'react'

export const BASE_USD = {
  pro:           { monthly: 9.99,  annual: 7.99  },
  institutional: { monthly: 79.99, annual: 63.99 },
} as const

export type CurrencyInfo = { symbol: string; rate: number; code: string }

const GHS_RATE = 16.0

const COUNTRY_CURRENCY: Record<string, CurrencyInfo> = {
  GH: { symbol: '₵',   rate: GHS_RATE, code: 'GHS' },
  NG: { symbol: '₦',   rate: 1650,     code: 'NGN' },
  KE: { symbol: 'KSh', rate: 130,      code: 'KES' },
  ZA: { symbol: 'R',   rate: 18.5,     code: 'ZAR' },
  GB: { symbol: '£',   rate: 0.79,     code: 'GBP' },
  CA: { symbol: 'CA$', rate: 1.36,     code: 'CAD' },
  AU: { symbol: 'A$',  rate: 1.55,     code: 'AUD' },
  // EU countries share EUR
  DE: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  FR: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  IT: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  ES: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  NL: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  BE: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  PT: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  AT: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  FI: { symbol: '€',   rate: 0.92,     code: 'EUR' },
  IE: { symbol: '€',   rate: 0.92,     code: 'EUR' },
}

const USD: CurrencyInfo = { symbol: '$', rate: 1.0, code: 'USD' }

export function getCurrency(countryCode: string): CurrencyInfo {
  return COUNTRY_CURRENCY[countryCode] ?? USD
}

export function fmt(usd: number, c: CurrencyInfo): string {
  if (usd === 0) return `${c.symbol}0`
  const val = usd * c.rate
  return `${c.symbol}${val % 1 === 0 ? val.toFixed(0) : val.toFixed(2)}`
}

/** Convert USD amount to GHS pesewas for Paystack */
export function toGHSPesewas(usd: number): number {
  return Math.round(usd * GHS_RATE * 100)
}

/** Convert USD amount to GHS */
export function toGHS(usd: number): number {
  return usd * GHS_RATE
}

const GEO_CACHE_KEY = 'vg_country_v2'

export function useCurrency(): CurrencyInfo {
  const [currency, setCurrency] = useState<CurrencyInfo>(USD)

  useEffect(() => {
    try {
      const cached = sessionStorage.getItem(GEO_CACHE_KEY)
      if (cached) { setCurrency(getCurrency(cached)); return }
    } catch { /* SSR */ }

    fetch('/api/geo')
      .then(r => r.json())
      .then((d: { country_code?: string }) => {
        const code = d.country_code ?? 'US'
        try { sessionStorage.setItem(GEO_CACHE_KEY, code) } catch { /* SSR */ }
        setCurrency(getCurrency(code))
      })
      .catch(() => {})
  }, [])

  return currency
}
