import type {
  VerifyRequest,
  VerifyResponse,
  BulkVerifyRequest,
  BulkVerifyResponse,
  HealthResponse,
  StatsResponse,
  ModelsResponse,
  AdminStats,
  PaymentRecord,
  SupportTicket,
  SiteTestResult,
  ApiError,
} from '@/types/api'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ── Core fetch wrapper ────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const err = (await res.json()) as { detail?: string }
      detail = err.detail ?? detail
    } catch {
      // non-JSON error body
    }
    const error: ApiError = { detail, status: res.status }
    throw error
  }

  return res.json() as Promise<T>
}

// ── Public endpoints ──────────────────────────────────────

export const api = {
  health(): Promise<HealthResponse> {
    return apiFetch('/health')
  },

  stats(): Promise<StatsResponse> {
    return apiFetch('/stats')
  },

  models(token?: string): Promise<ModelsResponse> {
    return apiFetch('/models', {}, token)
  },

  // ── Verification ────────────────────────────────────────

  verify(body: VerifyRequest, token: string): Promise<VerifyResponse> {
    return apiFetch('/verify', { method: 'POST', body: JSON.stringify(body) }, token)
  },

  verifyBulk(body: BulkVerifyRequest, token: string): Promise<BulkVerifyResponse> {
    return apiFetch('/verify/bulk', { method: 'POST', body: JSON.stringify(body) }, token)
  },

  // ── Admin ────────────────────────────────────────────────

  adminStats(adminKey: string): Promise<AdminStats> {
    return apiFetch('/admin/stats', {
      headers: { 'X-Admin-Key': adminKey },
    })
  },

  adminPayments(adminKey: string): Promise<PaymentRecord[]> {
    return apiFetch('/admin/payments', {
      headers: { 'X-Admin-Key': adminKey },
    })
  },

  adminTickets(adminKey: string): Promise<SupportTicket[]> {
    return apiFetch('/admin/tickets', {
      headers: { 'X-Admin-Key': adminKey },
    })
  },

  adminUpdateTicket(
    ticketId: string,
    status: SupportTicket['status'],
    adminKey: string
  ): Promise<SupportTicket> {
    return apiFetch(
      `/admin/tickets/${ticketId}`,
      { method: 'PATCH', body: JSON.stringify({ status }) },
      undefined
    )
  },

  // ── Scraper / Admin triggers ─────────────────────────────

  scrapeRss(adminKey: string): Promise<{ message: string }> {
    return apiFetch('/scrape/rss', {
      method: 'POST',
      headers: { 'X-Admin-Key': adminKey },
    })
  },

  scrapeHtml(adminKey: string): Promise<{ message: string }> {
    return apiFetch('/scrape/html', {
      method: 'POST',
      headers: { 'X-Admin-Key': adminKey },
    })
  },

  embed(adminKey: string): Promise<{ message: string }> {
    return apiFetch('/embed', {
      method: 'POST',
      headers: { 'X-Admin-Key': adminKey },
    })
  },

  // ── Site Tester ──────────────────────────────────────────

  testSitesList(): Promise<string[]> {
    return apiFetch('/test-sites/list')
  },

  testSite(url: string, adminKey: string): Promise<SiteTestResult> {
    return apiFetch(
      '/test-site',
      { method: 'POST', body: JSON.stringify({ url }) },
      undefined
    )
  },

  // ── Support ──────────────────────────────────────────────

  supportReply(
    ticketId: string,
    message: string,
    adminKey: string
  ): Promise<{ message: string }> {
    return apiFetch('/support/reply', {
      method: 'POST',
      body: JSON.stringify({ ticket_id: ticketId, message }),
      headers: { 'X-Admin-Key': adminKey },
    })
  },

  // ── Diagnostics ──────────────────────────────────────────

  diagnostics(adminKey: string): Promise<Record<string, unknown>> {
    return apiFetch('/diagnostics', {
      headers: { 'X-Admin-Key': adminKey },
    })
  },
}
