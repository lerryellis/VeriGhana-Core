'use server'

const API_URL   = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

export async function testSiteAction(url: string): Promise<Record<string, unknown>> {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 120_000) // 2 min timeout

    const res = await fetch(`${API_URL}/test-site`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
      body: JSON.stringify({ url }),
      signal: controller.signal,
    })

    clearTimeout(timeout)

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
      return { url, status: 'error', error: err.detail ?? `HTTP ${res.status}` }
    }

    const data = await res.json()
    return { url, ...data }
  } catch (err: unknown) {
    const msg = (err as Error).name === 'AbortError'
      ? 'Request timed out (>2 minutes). The site may be very slow or require JS rendering.'
      : (err as Error).message
    return { url, status: 'error', error: msg }
  }
}
