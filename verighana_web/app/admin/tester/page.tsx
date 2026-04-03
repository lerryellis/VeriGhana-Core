import { TesterClient } from './TesterClient'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? ''

async function fetchSites(): Promise<string[]> {
  try {
    const res = await fetch(`${API_URL}/test-sites/list`, {
      headers: { 'X-Admin-Key': ADMIN_KEY },
      cache: 'no-store',
    })
    if (!res.ok) return []
    const data = await res.json() as { sites: { url: string }[] | string[] }
    // sites may be URL strings or objects with .url
    return (data.sites ?? []).map((s: { url: string } | string) =>
      typeof s === 'string' ? s : s.url
    )
  } catch {
    return []
  }
}

export default async function TesterPage() {
  const sites = await fetchSites()
  return <TesterClient sites={sites} />
}
