// ── Verification ──────────────────────────────────────────
export interface SourceCitation {
  title: string
  url: string | null
  source: string
}

export interface RateLimitStatus {
  used: number
  limit: number
  remaining: number
  resets_at: string
}

export interface VerifyRequest {
  claim: string
  model?: string
}

export interface VerifyResponse {
  verdict: 'VERIFIED' | 'PARTIAL' | 'FALSE' | 'UNCORROBORATED' | 'ERROR'
  score: number
  explanation: string
  sources: SourceCitation[]
  model_used: string
  search_method: string
  processing_ms: number
  rate_limit?: RateLimitStatus
}

export interface BulkVerifyRequest {
  claims: string[]
  model?: string
}

export interface BulkVerifyResponse {
  results: VerifyResponse[]
  total: number
  processing_ms: number
}

// ── Public ────────────────────────────────────────────────
export interface HealthResponse {
  status: string
  version: string
  supabase: string
  embeddings: string
}

export interface StatsResponse {
  total_articles: number
  articles_with_embeddings: number
  total_verifications: number
  sources_tracked: number
  last_scrape?: string
}

export interface ModelInfo {
  id: string
  name: string
  provider: string
  tier_required: string
}

export interface ModelsResponse {
  models: ModelInfo[]
  default: string
}

// ── Admin ─────────────────────────────────────────────────
export interface AdminStats {
  total_users: number
  pro_users: number
  institutional_users: number
  total_verifications: number
  verifications_today: number
  total_revenue_usd: number
}

export interface PaymentRecord {
  id: string
  user_email: string
  tier: string
  amount_usd: number
  status: string
  created_at: string
}

export interface SupportTicket {
  id: string
  user_email: string
  subject: string
  message: string
  status: 'open' | 'in_progress' | 'resolved'
  created_at: string
  updated_at: string
}

// ── Site Tester ───────────────────────────────────────────
export interface SiteTestResult {
  url: string
  success: boolean
  articles_found: number
  strategy_used: string
  error?: string
  duration_ms: number
}

// ── API error ─────────────────────────────────────────────
export interface ApiError {
  detail: string
  status: number
}
