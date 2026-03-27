'use client'

import { useState } from 'react'

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

type Endpoint = {
  method: Method
  path: string
  auth: 'None' | 'Bearer Token' | 'X-Admin-Key' | 'Bearer Token (Pro+)'
  tag: string
  summary: string
  description: string
  request?: { name: string; type: string; required: boolean; description: string }[]
  response: string
  example?: string
  adminOnly?: boolean
  internalOnly?: boolean
}

const METHOD_COLORS: Record<Method, string> = {
  GET:    'bg-blue-100 text-blue-700',
  POST:   'bg-green-100 text-green-700',
  PATCH:  'bg-amber-100 text-amber-700',
  DELETE: 'bg-red-100 text-red-600',
}

const AUTH_COLORS: Record<string, string> = {
  'None':                    'bg-slate-100 text-slate-500',
  'Bearer Token':            'bg-purple-100 text-purple-700',
  'Bearer Token (Pro+)':     'bg-indigo-100 text-indigo-700',
  'X-Admin-Key':             'bg-red-100 text-red-700',
}

const ENDPOINTS: Endpoint[] = [
  // ── Public ────────────────────────────────────────────────────────────────
  {
    method: 'GET', path: '/health', auth: 'None', tag: 'Public',
    summary: 'Health Check',
    description: 'Confirms the API server is online and reachable. Used by monitoring tools, the homepage, and the Site Tester to detect whether the backend is running. Returns a simple JSON status.',
    response: '{ "status": "ok" }',
    example: 'curl https://api.verighana.com/health',
  },
  {
    method: 'GET', path: '/stats', auth: 'None', tag: 'Public',
    summary: 'Platform Statistics',
    description: 'Returns public-facing platform statistics shown on the homepage — total articles indexed, number of trusted sources tracked, and the number of users. Safe to expose publicly as it contains no sensitive data.',
    response: '{ "articles": 42000, "sources": 65, "users": 300 }',
    example: 'curl https://api.verighana.com/stats',
  },
  {
    method: 'GET', path: '/models', auth: 'None', tag: 'Public',
    summary: 'Available AI Models',
    description: 'Lists the AI models used in the verification cascade. Shows which providers are active and in what order they are tried. The cascade goes: Gemini 2.0 Flash → Gemini 1.5 Flash → Groq (Llama) → Cohere → OpenRouter → Heuristic fallback.',
    response: '{ "models": ["gemini-2.0-flash", "gemini-1.5-flash", "groq-llama", ...] }',
    example: 'curl https://api.verighana.com/models',
  },

  // ── Verification ──────────────────────────────────────────────────────────
  {
    method: 'POST', path: '/verify', auth: 'Bearer Token', tag: 'Verification',
    summary: 'Verify a Claim',
    description: 'The core endpoint of VeriGhana. Takes a text claim and returns a fact-check verdict. Internally it: (1) checks rate limits per tier, (2) runs a pgvector semantic search against 42,000+ indexed articles, (3) passes the claim + relevant articles through the AI cascade, and (4) logs the result to vg_usage_logs. Returns a structured verdict with a score, explanation, and source notes.\n\nVerdicts: VERIFIED | PARTIAL | FALSE | UNCORROBORATED\nScore: 0–100 (confidence level)',
    request: [
      { name: 'claim', type: 'string', required: true, description: 'The claim or statement to verify' },
      { name: 'context', type: 'string', required: false, description: 'Optional surrounding context to improve accuracy' },
      { name: 'lang', type: 'string', required: false, description: 'Language hint (default: "en")' },
    ],
    response: '{ "verdict": "PARTIAL", "score": 72, "explanation": "...", "summary": "...", "source_notes": "..." }',
    example: `curl -X POST https://api.verighana.com/verify \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"claim": "Ghana achieved 100% digital payment coverage in 2023"}'`,
  },
  {
    method: 'POST', path: '/verify/bulk', auth: 'Bearer Token (Pro+)', tag: 'Verification',
    summary: 'Bulk Verify Claims (Institutional)',
    description: 'Allows Institutional-tier subscribers to verify up to 20 claims in a single API request. Each claim is processed through the same AI cascade as a single verify call. Ideal for newsrooms or research teams processing many claims at once. Returns an array of VerifyResponse objects in the same order as the input.',
    request: [
      { name: 'claims', type: 'string[]', required: true, description: 'Array of claim strings (max 20)' },
    ],
    response: '{ "results": [{ "claim": "...", "verdict": "...", "score": 0, ... }] }',
    example: `curl -X POST https://api.verighana.com/verify/bulk \\
  -H "Authorization: Bearer YOUR_INSTITUTIONAL_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"claims": ["Claim 1", "Claim 2", "Claim 3"]}'`,
  },

  // ── Payment ───────────────────────────────────────────────────────────────
  {
    method: 'POST', path: '/payment/verify', auth: 'Bearer Token', tag: 'Payment',
    summary: 'Verify Paystack Payment & Upgrade Tier',
    description: 'Called by the billing UI after a user completes payment on Paystack. It: (1) verifies the transaction reference with Paystack\'s API, (2) checks the paid amount matches the expected plan price including 20% Ghana tax (VAT + NHIL + GETFund), (3) guards against reference reuse, (4) saves the payment record, and (5) upgrades the user\'s tier in Supabase.',
    request: [
      { name: 'reference', type: 'string', required: true, description: 'Paystack transaction reference from callback' },
      { name: 'plan_key', type: 'string', required: true, description: '"pro" or "institutional"' },
      { name: 'billing_cycle', type: 'string', required: true, description: '"monthly" or "annual"' },
      { name: 'full_name', type: 'string', required: false, description: 'Customer full name for the invoice' },
      { name: 'phone', type: 'string', required: false, description: 'Mobile Money number if applicable' },
      { name: 'promo_code', type: 'string', required: false, description: 'Discount promo code' },
      { name: 'payment_method', type: 'string', required: false, description: '"card", "mtn_momo", "vodafone_cash", "airteltigo_money"' },
    ],
    response: '{ "success": true, "plan": "pro", "expires_at": "2026-04-27T00:00:00Z" }',
  },

  // ── Support ───────────────────────────────────────────────────────────────
  {
    method: 'POST', path: '/support/reply', auth: 'X-Admin-Key', tag: 'Support',
    summary: 'Send Admin Reply to Support Ticket',
    description: 'Sends an admin reply to a user\'s support ticket. Updates the ticket status and, if Resend is configured, emails the user with the reply. Also optionally sends an SMS via a configured SMS provider.',
    request: [
      { name: 'ticket_id', type: 'string', required: true, description: 'UUID of the support ticket' },
      { name: 'reply', type: 'string', required: true, description: 'Admin reply message text' },
      { name: 'status', type: 'string', required: false, description: 'New status: "in_progress", "resolved", "closed"' },
    ],
    response: '{ "success": true }',
  },

  // ── Site Tester ───────────────────────────────────────────────────────────
  {
    method: 'GET', path: '/test-sites/list', auth: 'X-Admin-Key', tag: 'Site Tester',
    summary: 'List Scrape-Candidate Sites',
    description: 'Returns the list of all 65+ Ghanaian news and government sites that the HTML scraper is configured to crawl. Used by the admin Site Tester tool to show the full source list.',
    response: '{ "sites": [{ "url": "...", "name": "...", "category": "..." }] }',
    adminOnly: true,
  },
  {
    method: 'POST', path: '/test-site', auth: 'X-Admin-Key', tag: 'Site Tester',
    summary: 'Test Scrape a Single Site',
    description: 'Runs the full 6-strategy scrape cascade against a single URL and returns the articles found, the strategy that worked, and the time taken. The cascade tries: headline selector → container → list → document → anchor sweep → JavaScript rendering via Playwright. Useful for debugging why a source isn\'t being scraped.',
    request: [
      { name: 'url', type: 'string', required: true, description: 'The website URL to test scrape' },
    ],
    response: '{ "url": "...", "articles_found": 12, "strategy": "container", "time_ms": 843, "sample": [...] }',
    adminOnly: true,
  },

  // ── Admin ─────────────────────────────────────────────────────────────────
  {
    method: 'GET', path: '/admin/stats', auth: 'X-Admin-Key', tag: 'Admin',
    summary: 'Admin KPI Dashboard',
    description: 'Returns all key platform metrics for the admin dashboard: total users, total articles indexed, number of trusted sources, open support tickets, total payments processed, total revenue in USD, and counts of Pro vs Institutional subscriptions.',
    response: '{ "users": 300, "articles": 42000, "sources": 65, "tickets": 4, "payments": 28, "revenue_usd": 289.72, "pro_subs": 20, "inst_subs": 8 }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'GET', path: '/admin/payments', auth: 'X-Admin-Key', tag: 'Admin',
    summary: 'List All Payments',
    description: 'Returns a paginated list of all payment records. Supports filtering by date range, plan type, and status. Used by the Finance and Reports admin pages. Each record includes the customer email, amount, tax breakdown, payment method, Paystack reference, and subscription expiry date.',
    request: [
      { name: 'limit', type: 'integer', required: false, description: 'Max records to return (default 500)' },
      { name: 'date_from', type: 'string', required: false, description: 'ISO date filter start' },
      { name: 'date_to', type: 'string', required: false, description: 'ISO date filter end' },
      { name: 'plan_key', type: 'string', required: false, description: '"pro" or "institutional"' },
      { name: 'status', type: 'string', required: false, description: '"succeeded", "failed", "pending"' },
    ],
    response: '{ "payments": [{ "id": "...", "user_email": "...", "amount": 9.99, "tax_amount": 2.0, ... }] }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'GET', path: '/admin/payments/{payment_id}/invoice', auth: 'X-Admin-Key', tag: 'Admin',
    summary: 'Get Invoice Data',
    description: 'Returns the full payment record for a specific payment ID, formatted for invoice rendering. This is called by the invoice page to populate the receipt shown to users and admins. Includes all tax line items (VAT, NHIL, GETFund).',
    response: '{ "id": "...", "order_ref": "...", "amount": 9.99, "tax_amount": 2.0, ... }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'GET', path: '/admin/users', auth: 'X-Admin-Key', tag: 'Admin',
    summary: 'List All Users',
    description: 'Returns all registered user profiles including their subscription tier, role (admin/staff), organisation, country, daily query usage, and join date. Used by the Users admin page for user management, tier changes, and role promotion.',
    request: [
      { name: 'limit', type: 'integer', required: false, description: 'Max records (default 1000)' },
    ],
    response: '{ "users": [{ "user_id": "...", "email": "...", "tier": "pro", "role": "client", ... }] }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'GET', path: '/admin/tickets', auth: 'X-Admin-Key', tag: 'Admin',
    summary: 'List All Support Tickets',
    description: 'Returns all support tickets across all users, ordered by creation date. Includes the ticket status, user message, any admin reply, and user follow-up. Used by the Tickets admin page. Filter by status (open/in_progress/resolved/closed).',
    request: [
      { name: 'status', type: 'string', required: false, description: 'Filter by ticket status' },
      { name: 'limit', type: 'integer', required: false, description: 'Max records (default 500)' },
    ],
    response: '{ "tickets": [{ "id": "...", "subject": "...", "status": "open", ... }] }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'PATCH', path: '/admin/tickets/{ticket_id}', auth: 'X-Admin-Key', tag: 'Admin',
    summary: 'Update Ticket Status / Reply',
    description: 'Updates a support ticket — changes its status and/or saves an admin reply text. This is called by the Tickets admin page when an admin types a reply. The reply is also emailed to the user via Resend if configured.',
    request: [
      { name: 'status', type: 'string', required: false, description: 'New status for the ticket' },
      { name: 'admin_reply', type: 'string', required: false, description: 'Admin response text' },
      { name: 'user_followup_read', type: 'boolean', required: false, description: 'Mark user follow-up as read' },
    ],
    response: '{ "success": true }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'GET', path: '/diagnostics', auth: 'X-Admin-Key', tag: 'Admin',
    summary: 'System Diagnostics',
    description: 'Returns a full diagnostic snapshot of the platform: which AI providers are configured and reachable, Supabase connection status, pgvector availability, last scrape timestamps, and embedding queue depth. Used to debug production issues.',
    response: '{ "supabase": "ok", "gemini": "ok", "groq": "ok", "pgvector": "ok", "embed_queue": 14 }',
    adminOnly: true,
  },

  // ── Internal / Pipeline ───────────────────────────────────────────────────
  {
    method: 'POST', path: '/scrape/rss', auth: 'X-Admin-Key', tag: 'Pipeline',
    summary: 'Trigger RSS Scraper',
    description: 'Manually triggers the RSS scraper as a background task. Normally runs every 6 hours via GitHub Actions. Parses 3 trusted Ghanaian RSS feeds (Ghana Web, MyJoyOnline, GhanaFact) and upserts new articles into the fact_entries table.',
    response: '{ "message": "RSS scrape triggered in background" }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'POST', path: '/scrape/html', auth: 'X-Admin-Key', tag: 'Pipeline',
    summary: 'Trigger HTML Scraper',
    description: 'Manually triggers the HTML scraper for 65+ Ghanaian news and government sites. Uses a 6-strategy cascade: headline selector → article container → list items → full document → anchor sweep → Playwright JS rendering. Results are saved to fact_entries. This is the heaviest pipeline job — it can take several minutes.',
    response: '{ "message": "HTML scrape triggered in background" }',
    adminOnly: true, internalOnly: true,
  },
  {
    method: 'POST', path: '/embed', auth: 'X-Admin-Key', tag: 'Pipeline',
    summary: 'Trigger Embedder',
    description: 'Manually triggers the embedding pipeline as a background task. Finds all fact_entries rows where content_embedding is NULL and generates 3072-dimensional Gemini text-embedding-004 vectors for each. These embeddings enable the semantic search that powers claim verification. Normally runs after each scrape cycle.',
    response: '{ "message": "Embedding triggered in background" }',
    adminOnly: true, internalOnly: true,
  },
]

const TAGS = ['All', 'Public', 'Verification', 'Payment', 'Support', 'Site Tester', 'Admin', 'Pipeline']
const TAG_COLORS: Record<string, string> = {
  Public: 'bg-slate-100 text-slate-600',
  Verification: 'bg-blue-100 text-blue-700',
  Payment: 'bg-green-100 text-green-700',
  Support: 'bg-amber-100 text-amber-700',
  'Site Tester': 'bg-purple-100 text-purple-700',
  Admin: 'bg-red-100 text-red-700',
  Pipeline: 'bg-orange-100 text-orange-700',
}

function EndpointCard({ ep }: { ep: Endpoint }) {
  const [open, setOpen] = useState(false)

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${ep.internalOnly ? 'border-red-200' : 'border-slate-200'}`}>
      {/* Header row */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full text-left flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <span className={`text-xs font-bold font-mono-vg px-2.5 py-1 rounded w-16 text-center shrink-0 ${METHOD_COLORS[ep.method]}`}>
          {ep.method}
        </span>
        <code className="text-sm font-mono text-[#0f2240] flex-1">{ep.path}</code>
        <span className={`text-[0.65rem] font-mono-vg px-2 py-0.5 rounded-full shrink-0 ${TAG_COLORS[ep.tag] ?? 'bg-slate-100 text-slate-500'}`}>
          {ep.tag}
        </span>
        {ep.internalOnly && (
          <span className="text-[0.65rem] font-mono-vg px-2 py-0.5 rounded-full bg-red-100 text-red-600 shrink-0">Internal</span>
        )}
        <span className="text-slate-400 text-xs shrink-0">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-4 space-y-4 bg-slate-50/40">
          {/* Summary + auth */}
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="font-semibold text-[#0f2240]">{ep.summary}</p>
              <span className={`text-[0.65rem] font-mono-vg px-2 py-0.5 rounded-full mt-1 inline-block ${AUTH_COLORS[ep.auth]}`}>
                Auth: {ep.auth}
              </span>
            </div>
          </div>

          {/* Description */}
          <div>
            <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-1">Description</p>
            <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">{ep.description}</p>
          </div>

          {/* Request params */}
          {ep.request && ep.request.length > 0 && (
            <div>
              <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-2">Request Body / Parameters</p>
              <div className="space-y-1.5">
                {ep.request.map(r => (
                  <div key={r.name} className="flex items-start gap-3 text-sm">
                    <code className="font-mono text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded text-xs shrink-0">{r.name}</code>
                    <span className="text-slate-400 text-xs font-mono-vg shrink-0">{r.type}</span>
                    <span className={`text-[0.6rem] font-mono-vg px-1.5 py-0.5 rounded shrink-0 ${r.required ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-400'}`}>
                      {r.required ? 'required' : 'optional'}
                    </span>
                    <span className="text-slate-500 text-xs">{r.description}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Response */}
          <div>
            <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-1">Response</p>
            <pre className="text-xs bg-[#0f2240] text-green-300 font-mono p-3 rounded-lg overflow-x-auto">{ep.response}</pre>
          </div>

          {/* Example */}
          {ep.example && (
            <div>
              <p className="text-[0.65rem] text-slate-400 font-mono-vg uppercase tracking-widest mb-1">Example</p>
              <pre className="text-xs bg-slate-800 text-slate-100 font-mono p-3 rounded-lg overflow-x-auto">{ep.example}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ApiDocsPage() {
  const [activeTag, setActiveTag] = useState('All')
  const [search, setSearch] = useState('')

  const filtered = ENDPOINTS.filter(ep => {
    if (activeTag !== 'All' && ep.tag !== activeTag) return false
    if (search) {
      const q = search.toLowerCase()
      return ep.path.toLowerCase().includes(q) ||
        ep.summary.toLowerCase().includes(q) ||
        ep.description.toLowerCase().includes(q)
    }
    return true
  })

  const baseUrl = 'https://api.verighana.com'

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="font-display text-2xl font-bold text-[#0f2240]">API Reference</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          All endpoints — including internal admin and pipeline routes. Base URL:{' '}
          <code className="font-mono text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded text-xs">{baseUrl}</code>
        </p>
      </div>

      {/* Legend */}
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <p className="text-xs text-slate-400 font-mono-vg uppercase tracking-widest mb-3">Authentication Types</p>
        <div className="flex flex-wrap gap-3 text-xs">
          {Object.entries(AUTH_COLORS).map(([label, cls]) => (
            <span key={label} className={`px-2.5 py-1 rounded-full font-mono-vg ${cls}`}>{label}</span>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-3">
          <span className="font-medium text-red-600">Internal</span> — hidden from public /docs. Admin eyes only.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {TAGS.map(t => (
          <button key={t} type="button" onClick={() => setActiveTag(t)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors font-mono-vg ${
              activeTag === t
                ? 'bg-[#0f2240] border-[#0f2240] text-white'
                : 'border-slate-200 text-slate-500 hover:border-slate-400'
            }`}>
            {t}
          </button>
        ))}
        <input
          type="search"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search endpoints…"
          aria-label="Search API endpoints"
          className="text-sm bg-white border border-slate-200 text-slate-700 px-3 py-1 rounded-full outline-none focus:border-blue-400 transition-colors ml-auto"
        />
      </div>

      {/* Count */}
      <p className="text-xs text-slate-400 font-mono-vg">{filtered.length} endpoint{filtered.length !== 1 ? 's' : ''}</p>

      {/* Endpoint cards */}
      <div className="space-y-2">
        {filtered.map(ep => <EndpointCard key={`${ep.method}-${ep.path}`} ep={ep} />)}
      </div>
    </div>
  )
}
