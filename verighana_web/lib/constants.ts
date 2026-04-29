/** Fixed USD → GHS conversion rate used across billing, finance, and invoices */
export const USD_TO_GHS = 16

/** Ghana Revenue Authority tax rates (re-coupled Jan 2026) */
export const GRA_TAX = {
  vat: 0.15,
  nhil: 0.025,
  getfund: 0.025,
  combined: 0.20,
} as const
