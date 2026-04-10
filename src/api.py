"""
VeriGhana FastAPI Backend
=========================
Run:  uvicorn src.api:app --reload --port 8000

Endpoints
---------
  Public
    GET  /                  → serve index.html from project root
    GET  /health            → service health + module availability
    GET  /stats             → homepage counters (articles, sources, claims checked)
    GET  /models            → AI models available to caller's tier

  Verification  [Supabase Auth required]
    POST /verify            → single claim  (rate-limited by tier)
    POST /verify/bulk       → up to 20 claims  (institutional only)

  Scraper pipeline  [X-Admin-Key header required]
    POST /scrape/rss        → trigger RSS scraper (background)
    POST /scrape/html       → trigger HTML scraper (background)
    POST /embed             → trigger pgvector embedder (background)

  Site tester  [X-Admin-Key header required]
    POST /test-site         → test a single URL for scrapability
    GET  /test-sites/list   → return the full 65-site test list

  Support  [X-Admin-Key header required]
    POST /support/reply     → send Resend email reply to a ticket
    PATCH /admin/tickets/{id} → update ticket status

  Admin data  [X-Admin-Key header required]
    GET  /admin/stats       → platform KPIs
    GET  /admin/payments    → last 200 payment records
    GET  /admin/tickets     → last 200 support tickets

  Diagnostics  [X-Admin-Key header required]
    GET  /diagnostics       → live AI provider + DB health check

Required .env variables
-----------------------
  SUPABASE_URL
  SUPABASE_KEY              anon/public key
  SUPABASE_SERVICE_KEY      service_role key (bypasses RLS)
  SUPABASE_JWT_SECRET       Supabase Dashboard > Settings > API > JWT Secret
  ADMIN_API_KEY             any random secret for server-to-server calls
  ADMIN_EMAIL               email address that gets admin role
  GEMINI_API_KEY
  RESEND_API_KEY
  RESEND_FROM_EMAIL         (optional — defaults to onboarding@resend.dev)
  NOTIFY_FROM_NAME          (optional — defaults to VeriGhana Support)
  ALLOWED_ORIGINS           comma-separated, e.g. https://verighana.gh,http://localhost:3000
"""

from __future__ import annotations

import os, re, sys, time, json, base64, hmac
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import jwt as PyJWT
import requests as _http

# ── Bootstrap ────────────────────────────────────────────────────────────────
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

SUPABASE_URL     = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "")
SUPABASE_SVC_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_JWT_SEC = os.getenv("SUPABASE_JWT_SECRET", "")
ADMIN_EMAIL      = os.getenv("ADMIN_EMAIL", "")
ADMIN_API_KEY    = os.getenv("ADMIN_API_KEY", "")
RESEND_API_KEY    = os.getenv("RESEND_API_KEY", "")
RESEND_FROM       = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
NOTIFY_NAME       = os.getenv("NOTIFY_FROM_NAME", "VeriGhana Support")
PAYSTACK_SECRET   = os.getenv("PAYSTACK_SECRET_KEY", "")
ROOT_DIR          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Supabase helper ──────────────────────────────────────────────────────────
def _supa(service: bool = False):
    """Return a Supabase client. service=True uses service_role key (bypasses RLS)."""
    try:
        from supabase import create_client
        key = SUPABASE_SVC_KEY if service else SUPABASE_KEY
        if not SUPABASE_URL or not key:
            raise ValueError("SUPABASE_URL / key not configured.")
        return create_client(SUPABASE_URL, key)
    except Exception:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable.")


# ── Engine imports (graceful degradation) ────────────────────────────────────
try:
    from verifier import verify_claim, FREE_MODELS, DEFAULT_MODEL
    _VERIFIER_OK = True
except ImportError:
    _VERIFIER_OK  = False
    verify_claim  = None
    FREE_MODELS   = {"gemini-2.0-flash": "Gemini 2.0 Flash"}
    DEFAULT_MODEL = "gemini-2.0-flash"

try:
    from scrapers.html_scraper import run_html_ingestion
    _HTML_SCRAPER_OK = True
except ImportError:
    _HTML_SCRAPER_OK   = False
    run_html_ingestion = None

try:
    from scraper import run_ingestion_pipeline as run_scraper
    _RSS_SCRAPER_OK = True
except ImportError:
    _RSS_SCRAPER_OK = False
    run_scraper     = None

try:
    from embedder import embed_unprocessed_articles as run_embedder
    _EMBEDDER_OK = True
except ImportError:
    _EMBEDDER_OK = False
    run_embedder = None

_TESTER_OK   = False
test_site    = None
SITES_TO_TEST: list = []
try:
    from scrapers.site_tester import test_site, SITES_TO_TEST
    _TESTER_OK = True
except ImportError:
    try:
        from site_tester import test_site, SITES_TO_TEST   # type: ignore
        _TESTER_OK = True
    except ImportError:
        pass


# ── Tier configuration ───────────────────────────────────────────────────────
TIER_DAILY_LIMITS: dict[str, Optional[int]] = {
    "free":          5,
    "pro":           None,
    "institutional": None,
}
_all_model_ids = list(FREE_MODELS.keys()) if FREE_MODELS else ["gemini-2.0-flash"]
TIER_MODELS: dict[str, list[str]] = {
    "free":          [_all_model_ids[-1]],   # slowest / lightest only
    "pro":           _all_model_ids,
    "institutional": _all_model_ids,
}


# ══════════════════════════════════════════════════════════════════════════════
#  FASTAPI APP
# ══════════════════════════════════════════════════════════════════════════════
app = FastAPI(
    title       = "VeriGhana API",
    description = "Ghana's AI-Powered Fact Verification Platform",
    version     = "2.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = _allow_origins,
    allow_credentials = True,
    allow_methods     = ["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers     = ["Authorization", "Content-Type", "X-Admin-Key"],
)


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH — Supabase JWT verification
# ══════════════════════════════════════════════════════════════════════════════

class User(BaseModel):
    id:    str
    email: str
    tier:  str = "free"
    role:  str = "client"


def _decode_supabase_jwt(token: str) -> dict:
    """
    Verify a Supabase-issued JWT.

    Strategy (in order):
    1. Use the Supabase admin client (get_user) — algorithm-agnostic, works with
       both HS256 and RS256 projects, and validates the token server-side.
    2. Fall back to PyJWT with HS256 if the Supabase service key is unavailable
       but SUPABASE_JWT_SECRET is set.
    3. Dev-only last resort: decode without verification.
    """
    # ── Strategy 1: Supabase admin get_user (preferred) ──────────────────────
    if SUPABASE_URL and SUPABASE_SVC_KEY:
        try:
            from supabase import create_client
            admin = create_client(SUPABASE_URL, SUPABASE_SVC_KEY)
            response = admin.auth.get_user(token)
            user = response.user
            if not user:
                raise HTTPException(status_code=401, detail="Invalid or expired session.")
            return {
                "sub":   user.id,
                "email": user.email or "",
                "role":  getattr(user, "role", "authenticated"),
            }
        except HTTPException:
            raise
        except Exception as exc:
            err = str(exc).lower()
            if "expired" in err or "invalid" in err:
                raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
            # Supabase client unavailable — fall through to PyJWT
            pass

    # ── Strategy 2: PyJWT with project JWT secret ────────────────────────────
    if SUPABASE_JWT_SEC:
        try:
            return PyJWT.decode(
                token,
                SUPABASE_JWT_SEC,
                algorithms=["HS256", "RS256"],
                options={"verify_aud": False},
            )
        except PyJWT.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
        except PyJWT.InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    # ── Strategy 3: Dev-only — decode without verification ───────────────────
    # Never allow unverified decoding outside local development
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        padding = "=" * (4 - len(token.split(".")[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(token.split(".")[1] + padding))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token.")


def _profile_for(user_id: str, email: str) -> tuple[str, str]:
    """
    Return (tier, role) for a user.
    Checks ADMIN_EMAIL env override first, then looks up user_profiles table.
    """
    if ADMIN_EMAIL and email.lower().strip() == ADMIN_EMAIL.lower().strip():
        return "institutional", "admin"
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        return "free", "client"
    try:
        sb  = _supa(service=True)
        row = (sb.table("user_profiles")
                 .select("tier,role")
                 .eq("user_id", user_id)
                 .limit(1)
                 .maybe_single()
                 .execute())
        if row and row.data:
            return row.data.get("tier", "free"), row.data.get("role", "client")
    except Exception:
        pass
    return "free", "client"


async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """Dependency: require a valid Supabase Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header required: Bearer <supabase_access_token>",
        )
    token   = authorization.removeprefix("Bearer ").strip()
    payload = _decode_supabase_jwt(token)
    uid     = payload.get("sub", "")
    email   = payload.get("email", "")
    if not uid:
        raise HTTPException(status_code=401, detail="Token is missing user id (sub).")
    tier, role = _profile_for(uid, email)
    return User(id=uid, email=email, tier=tier, role=role)


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
) -> Optional[User]:
    """Dependency: return User if token present and valid, else None."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


def require_admin_key(x_admin_key: Optional[str] = Header(None)) -> str:
    """
    Dependency: validate X-Admin-Key header for server-to-server calls.
    Used by GitHub Actions scraper, Next.js admin server actions, etc.
    """
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY not set on server.")
    if not x_admin_key or not hmac.compare_digest(x_admin_key.strip(), ADMIN_API_KEY.strip()):
        raise HTTPException(status_code=403, detail="Invalid admin API key.")
    return x_admin_key


# ── Rate limit helpers ────────────────────────────────────────────────────────
def _queries_today(user_id: str) -> int:
    """Count /verify calls made by this user today (UTC)."""
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        return 0
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sb    = _supa(service=True)
        resp  = (sb.table("vg_usage_logs")
                   .select("id", count="exact")
                   .eq("user_id", user_id)
                   .gte("created_at", f"{today}T00:00:00Z")
                   .lte("created_at", f"{today}T23:59:59Z")
                   .execute())
        return resp.count or 0
    except Exception:
        return 0


def _log_usage(user_id: str, claim: str, verdict: str,
               score: int, model: str, ms: int, ip: Optional[str]):
    """Insert a usage log row (silently fails if table doesn't exist yet)."""
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        return
    try:
        _supa(service=True).table("vg_usage_logs").insert({
            "user_id":       user_id,
            "endpoint":      "/verify",
            "claim_text":    claim[:500],
            "verdict":       verdict,
            "score":         score,
            "model_used":    model,
            "processing_ms": ms,
            "ip_address":    ip,
            "created_at":    datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  PYDANTIC SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class VerifyRequest(BaseModel):
    claim:    str         = Field(..., min_length=5, max_length=10_000)
    model:    Optional[str] = None
    model_id: Optional[str] = None   # alias — matches verifier.py signature


class SourceOut(BaseModel):
    title:          str
    url:            str
    source:         str
    category:       Optional[str] = None
    published_date: Optional[str] = None
    stance:         Optional[str] = None


class RateLimitOut(BaseModel):
    used:      int
    limit:     Optional[int]
    remaining: Optional[int]
    allowed:   bool


class NarrativeDeltaVariation(BaseModel):
    source:  str
    framing: str
    tone:    str

class NarrativeDelta(BaseModel):
    aspect:         str
    variations:     List[NarrativeDeltaVariation] = []
    delta_analysis: str

class BiasSignal(BaseModel):
    source: str
    signal: str
    type:   str

class VerifyResponse(BaseModel):
    verdict:       str
    score:         int
    explanation:   str
    summary:       Optional[str]        = None
    sources:       List[SourceOut]      = []
    source_notes:             List[dict]           = []
    categories:               Optional[dict]       = None
    convergence:              List[str]            = []
    narrative_delta:          List[NarrativeDelta] = []
    bias_signals:             List[BiasSignal]     = []
    triangulation_confidence: str                  = "low"
    triangulation_note:       str                  = ""
    model_used:    str
    provider:      Optional[str]        = None
    search_method: str
    processing_ms: int
    web_search:    bool                  = False
    disclaimer:    Optional[str]         = None
    rate_limit:    Optional[RateLimitOut] = None


class BulkVerifyRequest(BaseModel):
    claims: List[str]     = Field(..., min_length=1, max_length=20)
    model:  Optional[str] = None

    @field_validator("claims")
    @classmethod
    def validate_claim_lengths(cls, v: List[str]) -> List[str]:
        for i, c in enumerate(v):
            if len(c) < 5 or len(c) > 10_000:
                raise ValueError(f"Claim {i+1} must be 5–10,000 characters.")
        return v


class BulkVerifyResponse(BaseModel):
    results:       List[VerifyResponse]
    total:         int
    processing_ms: int


class SupportReplyRequest(BaseModel):
    to_email:   str
    to_name:    str
    subject:    str
    body:       str
    ticket_id:  Optional[str] = None
    new_status: Optional[str] = None


_PRIVATE_HOSTS = re.compile(
    r"^(localhost|127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|0\.0\.0\.0|::1|169\.254\.)",
    re.IGNORECASE,
)

class TestSiteRequest(BaseModel):
    url:               str           = Field(..., max_length=2048)
    name:              Optional[str] = None
    category:          Optional[str] = "Custom"
    update_on_success: bool          = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https.")
        host = parsed.hostname or ""
        if _PRIVATE_HOSTS.match(host):
            raise ValueError("URL must point to a public host.")
        return v


class TicketStatusUpdate(BaseModel):
    status:              Optional[str]  = None
    user_followup_read:  Optional[bool] = None


class PaymentVerifyRequest(BaseModel):
    reference:      str
    plan_key:       str                   # pro | institutional
    billing_cycle:  str                   # monthly | annual
    full_name:      Optional[str] = None
    phone:          Optional[str] = None
    promo_code:     Optional[str] = None
    payment_method: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def serve_homepage():
    index = os.path.join(ROOT_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, media_type="text/html")
    return {"message": "VeriGhana API v2.0 — visit /docs for the API reference."}


@app.get("/health", tags=["Public"])
async def health():
    """
    Service health check.
    Reports which internal modules loaded successfully.
    Use this to verify your deployment after pushing code.
    """
    return {
        "status":    "ok",
        "version":   "2.0.0",
        "modules": {
            "verifier":     _VERIFIER_OK,
            "html_scraper": _HTML_SCRAPER_OK,
            "rss_scraper":  _RSS_SCRAPER_OK,
            "embedder":     _EMBEDDER_OK,
            "site_tester":  _TESTER_OK,
        },
        "db_configured":     bool(SUPABASE_URL and SUPABASE_KEY),
        "admin_key_set":     bool(ADMIN_API_KEY),
        "jwt_secret_set":    bool(SUPABASE_JWT_SEC),
        "timestamp":         datetime.now(timezone.utc).isoformat(),
    }


@app.get("/stats", tags=["Public"])
async def public_stats():
    """
    Live database counters for the homepage stats bar.
    Returns zeros gracefully if DB is unreachable.
    """
    out = {"total_articles": 0, "sources_tracked": 0, "total_verifications": 0, "last_scrape": None}
    if not (SUPABASE_URL and SUPABASE_KEY):
        return out

    # Public reads — anon key
    try:
        sb = _supa()
        out["total_articles"] = sb.table("fact_entries").select("id", count="exact").execute().count or 0
        out["sources_tracked"] = sb.table("trusted_sources").select("id", count="exact").execute().count or 0
    except Exception:
        pass

    # Claims checked — service key bypasses RLS on usage_logs
    try:
        sb = _supa(service=True)
        out["total_verifications"] = sb.table("vg_usage_logs").select("id", count="exact").execute().count or 0
    except Exception:
        pass

    # Last scrape — most recent article inserted by the scraper
    try:
        sb     = _supa()
        latest = (sb.table("fact_entries")
                    .select("created_at")
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute())
        if latest.data:
            out["last_scrape"] = latest.data[0]["created_at"]
    except Exception:
        pass

    return out


@app.get("/models", tags=["Public"])
async def list_models(user: Optional[User] = Depends(get_current_user_optional)):
    """
    Return the AI models available to the caller's tier.
    Unauthenticated: free-tier model only.
    Pro / Institutional: all models.
    """
    tier    = user.tier if user else "free"
    allowed = TIER_MODELS.get(tier, TIER_MODELS["free"])
    return {
        "models":  [{"id": m, "name": m.replace("-", " ").title()} for m in allowed],
        "default": allowed[0],
        "tier":    tier,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def _run_verify(claim: str, model_id: str) -> dict:
    """Call verifier.py. Returns a safe fallback dict if engine is unavailable."""
    if not _VERIFIER_OK or verify_claim is None:
        return {
            "verdict":       "UNCORROBORATED",
            "score":         0,
            "explanation":   "Verification engine unavailable (verifier.py not found).",
            "summary":       "",
            "sources":       [],
            "source_notes":  [],
            "model_used":    model_id,
            "provider":      "none",
            "search_method": "none",
            "processing_ms": 0,
        }
    return verify_claim(claim, model_id=model_id)


def _build_rl(user_id: str, tier: str) -> RateLimitOut:
    limit     = TIER_DAILY_LIMITS.get(tier)
    used      = _queries_today(user_id) if limit is not None else 0
    remaining = max(0, limit - used) if limit is not None else None
    return RateLimitOut(
        used      = used,
        limit     = limit,
        remaining = remaining,
        allowed   = (limit is None) or (used < limit),
    )


def _source_label(s: dict) -> str:
    name = s.get("source_name") or s.get("source") or ""
    if name and name != "Unknown":
        return name
    url = s.get("url_link") or s.get("url") or ""
    if url and url != "#":
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc or ""
            # strip www. prefix and take the first label, e.g. "www.myjoyonline.com" → "myjoyonline"
            host = host.removeprefix("www.")
            domain = host.split(".")[0]
            if domain:
                return domain
        except Exception:
            pass
    return "Unknown"


def _normalise_sources(raw: list) -> List[SourceOut]:
    return [
        SourceOut(
            title          = s.get("title", "Untitled"),
            url            = s.get("url_link") or s.get("url", "#"),
            source         = _source_label(s),
            category       = s.get("category") or None,
            published_date = s.get("published_date") or None,
            stance         = s.get("stance") or None,
        )
        for s in raw
    ]


@app.post("/verify", response_model=VerifyResponse, tags=["Verification"])
async def verify(
    req:     VerifyRequest,
    request: Request,
    user:    User = Depends(get_current_user),
):
    """
    Verify a claim against 65+ trusted Ghanaian sources.

    Rate limits by tier:
    - **Free**: 5 per day, slowest model only
    - **Pro**: unlimited, all models
    - **Institutional**: unlimited, all models + bulk endpoint
    """
    if not req.claim or not req.claim.strip():
        raise HTTPException(status_code=400, detail="claim must not be empty.")

    # Rate limit
    rl = _build_rl(user.id, user.tier)
    if not rl.allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of {rl.limit} verifications reached. Upgrade to Pro for unlimited access.",
            headers={"Retry-After": "86400"},
        )

    # Clamp model to tier's allowed set
    allowed  = TIER_MODELS.get(user.tier, TIER_MODELS["free"])
    model_id = req.model_id or req.model or allowed[0]
    if model_id not in allowed:
        model_id = allowed[0]

    # Run engine
    t0     = time.time()
    result = _run_verify(req.claim.strip(), model_id)
    ms     = int((time.time() - t0) * 1000)

    # Log (fire-and-forget)
    ip = request.client.host if request.client else None
    _log_usage(user.id, req.claim, result.get("verdict", ""), result.get("score", 0), model_id, ms, ip)

    return VerifyResponse(
        verdict                  = result.get("verdict", "UNCORROBORATED"),
        score                    = int(result.get("score", 0)),
        explanation              = result.get("explanation", ""),
        summary                  = result.get("summary"),
        sources                  = _normalise_sources(result.get("sources", [])),
        source_notes             = result.get("source_notes", []),
        categories               = result.get("categories"),
        convergence              = result.get("convergence", []),
        narrative_delta          = result.get("narrative_delta", []),
        bias_signals             = result.get("bias_signals", []),
        triangulation_confidence = result.get("triangulation_confidence", "low"),
        triangulation_note       = result.get("triangulation_note", ""),
        model_used               = result.get("model_used", model_id),
        provider                 = result.get("provider"),
        search_method            = result.get("search_method", "vector"),
        processing_ms            = result.get("processing_ms", ms),
        web_search               = result.get("web_search", False),
        disclaimer               = result.get("disclaimer"),
        rate_limit               = _build_rl(user.id, user.tier),
    )


@app.post("/verify/bulk", response_model=BulkVerifyResponse, tags=["Verification"])
async def verify_bulk(
    req:  BulkVerifyRequest,
    user: User = Depends(get_current_user),
):
    """Verify up to 20 claims. **Institutional tier only.**"""
    if user.tier != "institutional":
        raise HTTPException(status_code=403, detail="Bulk verification requires an Institutional subscription.")
    if not req.claims:
        raise HTTPException(status_code=400, detail="Provide at least one claim.")
    if len(req.claims) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 claims per bulk request.")

    allowed  = TIER_MODELS["institutional"]
    model_id = req.model or allowed[0]
    if model_id not in allowed:
        model_id = allowed[0]

    t_all, results = time.time(), []
    for claim in req.claims:
        t0  = time.time()
        res = _run_verify(claim, model_id)
        ms  = int((time.time() - t0) * 1000)
        results.append(VerifyResponse(
            verdict                  = res.get("verdict", "UNCORROBORATED"),
            score                    = int(res.get("score", 0)),
            explanation              = res.get("explanation", ""),
            summary                  = res.get("summary"),
            sources                  = _normalise_sources(res.get("sources", [])),
            source_notes             = res.get("source_notes", []),
            categories               = res.get("categories"),
            convergence              = res.get("convergence", []),
            narrative_delta          = res.get("narrative_delta", []),
            bias_signals             = res.get("bias_signals", []),
            triangulation_confidence = res.get("triangulation_confidence", "low"),
            triangulation_note       = res.get("triangulation_note", ""),
            model_used               = res.get("model_used", model_id),
            provider                 = res.get("provider"),
            search_method            = res.get("search_method", "vector"),
            processing_ms            = ms,
        ))

    return BulkVerifyResponse(
        results       = results,
        total         = len(results),
        processing_ms = int((time.time() - t_all) * 1000),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPER PIPELINE  [X-Admin-Key required]
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/scrape/rss", tags=["Scraper"], include_in_schema=False)
async def scrape_rss(
    background: BackgroundTasks,
    _: str = Depends(require_admin_key),
):
    """Trigger the RSS scraper in the background. Returns immediately."""
    if not _RSS_SCRAPER_OK or run_scraper is None:
        raise HTTPException(status_code=503, detail="scraper.py not found in src/.")
    def _run():
        try:
            run_scraper()
            print("[RSS scraper] completed")
        except Exception as exc:
            print(f"[RSS scraper] error: {exc}")
    background.add_task(_run)
    return {"status": "started", "job": "rss_scraper"}


@app.post("/scrape/html", tags=["Scraper"], include_in_schema=False)
async def scrape_html(
    background: BackgroundTasks,
    _: str = Depends(require_admin_key),
):
    """Trigger the HTML scraper in the background. Returns immediately."""
    if not _HTML_SCRAPER_OK or run_html_ingestion is None:
        raise HTTPException(status_code=503, detail="scrapers/html_scraper.py not found in src/.")
    def _run():
        try:
            run_html_ingestion()
            print("[HTML scraper] completed")
        except Exception as exc:
            print(f"[HTML scraper] error: {exc}")
    background.add_task(_run)
    return {"status": "started", "job": "html_scraper"}


@app.post("/embed", tags=["Scraper"], include_in_schema=False)
async def run_embed(
    background: BackgroundTasks,
    _: str = Depends(require_admin_key),
):
    """Trigger the pgvector embedder in the background. Returns immediately."""
    if not _EMBEDDER_OK or run_embedder is None:
        raise HTTPException(status_code=503, detail="embedder.py not found in src/.")
    def _run():
        try:
            run_embedder()
            print("[Embedder] completed")
        except Exception as exc:
            print(f"[Embedder] error: {exc}")
    background.add_task(_run)
    return {"status": "started", "job": "embedder"}


# ══════════════════════════════════════════════════════════════════════════════
#  SITE TESTER  [X-Admin-Key required]
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/test-sites/list", tags=["Site Tester"])
async def get_sites_list(_: str = Depends(require_admin_key)):
    """Return the full list of sites used in scrapability testing."""
    if not _TESTER_OK:
        raise HTTPException(status_code=503, detail="site_tester.py not available.")
    return {"sites": SITES_TO_TEST, "total": len(SITES_TO_TEST)}


@app.post("/test-site", tags=["Site Tester"])
async def test_single_site(
    req: TestSiteRequest,
    _:   str = Depends(require_admin_key),
):
    """
    Test a single URL for scrapability.
    Returns status, headline count, detected tag/class, and up to 3 sample headlines.
    Runs in a thread pool to avoid blocking the async event loop.
    """
    if not _TESTER_OK or test_site is None:
        raise HTTPException(status_code=503, detail="site_tester.py not available.")
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: test_site(
                {"name": req.name or req.url, "url": req.url, "category": req.category},
                update_db=req.update_on_success,
            ),
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Site test failed: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
#  SUPPORT  [X-Admin-Key required]
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/support/reply", tags=["Support"])
async def send_support_reply(
    req: SupportReplyRequest,
    _:   str = Depends(require_admin_key),
):
    """
    Save admin reply in-app (always) and attempt email via Resend (best-effort).
    """
    if not req.ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id is required.")

    # ── Step 1: Save reply + status to DB (always succeeds or raises) ──────────
    update_payload: dict = {"admin_reply": req.body}
    if req.new_status:
        update_payload["status"] = req.new_status
    try:
        _supa(service=True).table("support_tickets").update(
            update_payload
        ).eq("id", req.ticket_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save reply: {exc}")

    # ── Step 2: Attempt email (best-effort, never blocks the response) ─────────
    email_sent  = False
    email_error = None

    if RESEND_API_KEY:
        ticket_ref = f"#{req.ticket_id[:7].upper()}"
        html_body = f"""
<div style="font-family:Arial,sans-serif;font-size:15px;color:#1e293b;
            max-width:600px;margin:0 auto;line-height:1.6;">
  <div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0;">
    <span style="font-weight:800;font-size:18px;color:#fff;">
      Veri<span style="color:#60a5fa;">Ghana</span>
    </span>
  </div>
  <div style="padding:24px;border:1px solid #e2e8f0;
              border-top:none;border-radius:0 0 8px 8px;background:#fff;">
    <p style="margin:0 0 16px;">Hi <strong>{req.to_name}</strong>,</p>
    <div style="white-space:pre-wrap;">{req.body}</div>
    <hr style="margin:24px 0;border:none;border-top:1px solid #e2e8f0;">
    <p style="font-size:12px;color:#94a3b8;margin:0;">
      {NOTIFY_NAME}<br>Ticket ref: {ticket_ref}
    </p>
  </div>
</div>"""
        plain = f"Hi {req.to_name},\n\n{req.body}\n\n— {NOTIFY_NAME}\nTicket ref: {ticket_ref}"
        try:
            resp = _http.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={
                    "from":     f"{NOTIFY_NAME} <{RESEND_FROM}>",
                    "to":       [req.to_email],
                    "subject":  f"Re: {req.subject}",
                    "html":     html_body,
                    "text":     plain,
                    "reply_to": os.getenv("NOTIFY_FROM_EMAIL", RESEND_FROM),
                },
                timeout=10,
            )
            email_sent = resp.status_code in (200, 201)
            if not email_sent:
                try:
                    email_error = resp.json().get("message", resp.text[:200])
                except Exception:
                    email_error = resp.text[:200]
        except Exception as exc:
            email_error = str(exc)
    else:
        email_error = "RESEND_API_KEY not configured"

    return {"saved": True, "email_sent": email_sent, "email_error": email_error}


# ══════════════════════════════════════════════════════════════════════════════
#  PAYMENT  [Supabase Auth required]
# ══════════════════════════════════════════════════════════════════════════════

PLAN_PRICES = {
    "pro":           {"monthly": 0.99,  "annual": 0.79},
    "institutional": {"monthly": 1.99, "annual": 1.59},
}
PLAN_EXPIRY_DAYS = {"monthly": 31, "annual": 366}

@app.post("/payment/verify", tags=["Payment"])
async def verify_payment(
    req:  PaymentVerifyRequest,
    user: User = Depends(get_current_user),
):
    """
    Verify a Paystack transaction reference and upgrade the user's tier.
    Called after Paystack popup callback with the transaction reference.
    """
    if not PAYSTACK_SECRET:
        raise HTTPException(status_code=503, detail="Payment gateway not configured.")

    # ── 1. Verify with Paystack ───────────────────────────────────────────────
    try:
        ps_resp = _http.get(
            f"https://api.paystack.co/transaction/verify/{req.reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"},
            timeout=15,
        )
        ps_data = ps_resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Payment gateway unreachable. Please try again.")

    if not ps_data.get("status") or ps_data.get("data", {}).get("status") != "success":
        raise HTTPException(status_code=402, detail="Payment not successful on Paystack.")

    tx = ps_data["data"]

    # ── 1b. Verify paid amount matches expected plan price ────────────────────
    plan_key_check = req.plan_key if req.plan_key in PLAN_PRICES else "pro"
    cycle_check    = req.billing_cycle if req.billing_cycle in ("monthly", "annual") else "monthly"
    GRA_TAX_RATE   = 0.20  # VAT 15% + NHIL 2.5% + GETFund 2.5% (GRA, Jan 2026)
    base_ghs       = PLAN_PRICES[plan_key_check][cycle_check]
    if cycle_check == "annual":
        base_ghs  *= 12
    expected_ghs   = round(base_ghs * (1 + GRA_TAX_RATE), 2)   # tax-inclusive total in GHS
    paid_pesewas   = tx.get("amount", 0)               # Paystack amounts are in pesewas
    paid_ghs       = paid_pesewas / 100                # convert pesewas → GHS
    if abs(paid_ghs - expected_ghs) > 0.10:            # allow ₵0.10 tolerance for rounding
        raise HTTPException(
            status_code=402,
            detail="Payment amount does not match the selected plan price.",
        )

    # ── 2. Guard against re-use of the same reference ────────────────────────
    existing = (
        _supa(service=True)
        .table("payments")
        .select("id")
        .eq("order_ref", req.reference)
        .execute()
        .data
    )
    if existing:
        raise HTTPException(status_code=409, detail="This payment reference has already been used.")

    # ── 3. Determine plan details ─────────────────────────────────────────────
    plan_key   = req.plan_key if req.plan_key in PLAN_PRICES else "pro"
    cycle      = req.billing_cycle if req.billing_cycle in ("monthly", "annual") else "monthly"
    base_price = PLAN_PRICES[plan_key][cycle]
    amount     = base_price * 12 if cycle == "annual" else base_price  # subtotal (pre-tax)
    tax_rate   = 20.0  # VAT 15% + NHIL 2.5% + GETFund 2.5% (GRA, Jan 2026)
    tax_amount = round(amount * 0.20, 2)
    expires    = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=PLAN_EXPIRY_DAYS[cycle])

    # ── 4. Save payment record ────────────────────────────────────────────────
    import uuid
    _supa(service=True).table("payments").insert({
        "id":             str(uuid.uuid4()),
        "user_id":        user.id,
        "order_ref":      req.reference,
        "user_email":     tx.get("customer", {}).get("email", ""),
        "full_name":      req.full_name or "",
        "plan_key":       plan_key,
        "plan_label":     f"{plan_key.title()} ({cycle})",
        "amount":         amount,
        "tax_rate":       tax_rate,
        "tax_amount":     tax_amount,
        "currency":       "GHS",
        "payment_method": req.payment_method or tx.get("channel", "card"),
        "status":         "succeeded",
        "promo_code":     req.promo_code,
        "country":        tx.get("customer", {}).get("customer_code", ""),
        "email_sent":     False,
        "sms_sent":       False,
    }).execute()

    # ── 5. Upgrade user tier ──────────────────────────────────────────────────
    _supa(service=True).table("user_profiles").update({
        "tier":                    plan_key,
        "subscription_status":     "active",
        "subscription_expires_at": expires.isoformat(),
        "cancelled_at":            None,
    }).eq("user_id", user.id).execute()

    return {
        "success":    True,
        "plan":       plan_key,
        "expires_at": expires.isoformat(),
        "reference":  req.reference,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN DATA  [X-Admin-Key required]
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/admin/stats", tags=["Admin"], include_in_schema=False)
async def admin_stats(_: str = Depends(require_admin_key)):
    """Platform-wide KPIs for the admin dashboard."""
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        raise HTTPException(status_code=503, detail="SUPABASE_SERVICE_KEY not configured.")
    sb, out = _supa(service=True), {}

    for table, label in [
        ("fact_entries",    "articles"),
        ("trusted_sources", "sources"),
        ("support_tickets", "tickets"),
        ("user_profiles",   "users"),
    ]:
        try:
            out[label] = sb.table(table).select("id", count="exact").execute().count or 0
        except Exception:
            out[label] = 0

    # Payment aggregates
    try:
        pays = sb.table("payments").select("amount,plan_key").eq("status", "succeeded").execute().data or []
        out["payments"]    = len(pays)
        out["revenue_usd"] = round(sum(float(p.get("amount", 0)) for p in pays), 2)
        out["pro_subs"]    = sum(1 for p in pays if p.get("plan_key") == "pro")
        out["inst_subs"]   = sum(1 for p in pays if p.get("plan_key") == "institutional")
    except Exception:
        out.update({"payments": 0, "revenue_usd": 0.0, "pro_subs": 0, "inst_subs": 0})

    return out


@app.get("/admin/payments", tags=["Admin"], include_in_schema=False)
async def admin_payments(
    limit:     int           = 500,
    date_from: Optional[str] = None,   # ISO date e.g. 2025-01-01
    date_to:   Optional[str] = None,   # ISO date e.g. 2025-12-31
    plan_key:  Optional[str] = None,   # pro | institutional
    status:    Optional[str] = None,   # succeeded | failed | pending
    _:         str           = Depends(require_admin_key),
):
    """Payment records with optional date/plan/status filtering."""
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        raise HTTPException(status_code=503, detail="SUPABASE_SERVICE_KEY not configured.")
    try:
        q = (
            _supa(service=True)
            .table("payments")
            .select("id,order_ref,created_at,user_email,full_name,plan_label,"
                    "amount,currency,payment_method,status,email_sent,sms_sent,"
                    "promo_code,country,plan_key")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            # include full day
            q = q.lte("created_at", date_to + "T23:59:59Z")
        if plan_key:
            q = q.eq("plan_key", plan_key)
        if status:
            q = q.eq("status", status)
        rows = q.execute().data or []
        return {"payments": rows, "total": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/admin/payments/{payment_id}/invoice", tags=["Admin"], include_in_schema=False)
async def download_invoice(
    payment_id: str,
    _: str = Depends(require_admin_key),
):
    """Return invoice data for a single payment (rendered as PDF in the browser)."""
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        raise HTTPException(status_code=503, detail="SUPABASE_SERVICE_KEY not configured.")
    try:
        rows = (
            _supa(service=True)
            .table("payments")
            .select("id,order_ref,created_at,user_email,full_name,plan_label,"
                    "amount,currency,payment_method,status,country,plan_key,promo_code")
            .eq("id", payment_id)
            .limit(1)
            .execute()
            .data or []
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Payment not found.")
        return rows[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/admin/users", tags=["Admin"], include_in_schema=False)
async def admin_users(
    limit:  int           = 500,
    search: Optional[str] = None,   # email or name substring
    tier:   Optional[str] = None,   # free | pro | institutional
    role:   Optional[str] = None,   # client | admin
    _:      str           = Depends(require_admin_key),
):
    """All user profiles, most recent first."""
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        raise HTTPException(status_code=503, detail="SUPABASE_SERVICE_KEY not configured.")
    try:
        q = (
            _supa(service=True)
            .table("user_profiles")
            .select("user_id,email,full_name,phone,organisation,country,tier,role,"
                    "subscription_status,subscription_expires_at,daily_queries_used,created_at")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if tier:
            q = q.eq("tier", tier)
        if role:
            q = q.eq("role", role)
        rows = q.execute().data or []
        # Search filter (case-insensitive in Python since PostgREST ilike needs %text%)
        if search:
            s = search.lower()
            rows = [r for r in rows if s in (r.get("email") or "").lower()
                    or s in (r.get("full_name") or "").lower()]
        return {"users": rows, "total": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/admin/tickets", tags=["Admin"], include_in_schema=False)
async def admin_tickets(
    limit:  int           = 200,
    status: Optional[str] = None,
    _:      str           = Depends(require_admin_key),
):
    """
    Support tickets, most recent first.
    Filter by status: open | in_progress | resolved | closed
    """
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        raise HTTPException(status_code=503, detail="SUPABASE_SERVICE_KEY not configured.")
    try:
        query = (
            _supa(service=True)
            .table("support_tickets")
            .select("id,created_at,updated_at,name,email,category,subject,message,status,user_followup")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        rows = query.execute().data or []
        return {"tickets": rows, "total": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/admin/tickets/{ticket_id}", tags=["Admin"], include_in_schema=False)
async def update_ticket_status(
    ticket_id: str,
    body:      TicketStatusUpdate,
    _:         str = Depends(require_admin_key),
):
    """Update a ticket's status field."""
    valid = {"open", "in_progress", "resolved", "closed"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of: {sorted(valid)}")
    if not (SUPABASE_URL and SUPABASE_SVC_KEY):
        raise HTTPException(status_code=503, detail="SUPABASE_SERVICE_KEY not configured.")
    try:
        payload: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if body.status is not None:
            payload["status"] = body.status
        if body.user_followup_read is not None:
            payload["user_followup_read"] = body.user_followup_read
        _supa(service=True).table("support_tickets").update(payload).eq("id", ticket_id).execute()
        return {"updated": True, "ticket_id": ticket_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
#  DIAGNOSTICS  [X-Admin-Key required]
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/diagnostics", tags=["Admin"])
async def diagnostics(_: str = Depends(require_admin_key)):
    """
    Live health check for every AI provider and the Supabase database.
    Returns a structured report used by the admin Site Tester panel.
    """
    results: list[dict] = []

    # Supabase
    try:
        sb  = _supa(service=True)
        cnt = sb.table("fact_entries").select("id", count="exact").execute().count or 0
        results.append({"provider":"Supabase","check":"Connection + row count","status":"PASS","detail":f"{cnt:,} rows in fact_entries"})
    except Exception as exc:
        results.append({"provider":"Supabase","check":"Connection + row count","status":"FAIL","detail":str(exc)[:120]})

    # Gemini
    gkey = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    if gkey:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gkey)
            r = genai.GenerativeModel("gemini-2.0-flash").generate_content(
                "Reply with the single word ONLINE",
                generation_config={"max_output_tokens": 5, "temperature": 0},
            )
            results.append({"provider":"Gemini","check":"API reachability","status":"PASS" if r.text else "FAIL","detail":"gemini-2.0-flash responded"})
        except Exception as exc:
            results.append({"provider":"Gemini","check":"API reachability","status":"FAIL","detail":str(exc)[:120]})
    else:
        results.append({"provider":"Gemini","check":"API reachability","status":"SKIP","detail":"No GEMINI_API_KEY in .env"})

    # Groq
    gq = os.getenv("GROQ_API_KEY", "")
    if gq:
        try:
            r = _http.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization":f"Bearer {gq}","Content-Type":"application/json"},
                json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"Reply: ONLINE"}],"max_tokens":5},
                timeout=12)
            r.raise_for_status()
            results.append({"provider":"Groq","check":"API reachability","status":"PASS","detail":"llama-3.3-70b-versatile"})
        except Exception as exc:
            results.append({"provider":"Groq","check":"API reachability","status":"FAIL","detail":str(exc)[:120]})
    else:
        results.append({"provider":"Groq","check":"API reachability","status":"SKIP","detail":"No GROQ_API_KEY in .env"})

    # Cohere
    ck = os.getenv("COHERE_API_KEY", "")
    if ck:
        try:
            r = _http.post("https://api.cohere.com/v2/chat",
                headers={"Authorization":f"Bearer {ck}","Content-Type":"application/json"},
                json={"model":"command-r-plus","messages":[{"role":"user","content":"Reply: ONLINE"}],"max_tokens":5},
                timeout=12)
            r.raise_for_status()
            results.append({"provider":"Cohere","check":"API reachability","status":"PASS","detail":"command-r-plus"})
        except Exception as exc:
            results.append({"provider":"Cohere","check":"API reachability","status":"FAIL","detail":str(exc)[:120]})
    else:
        results.append({"provider":"Cohere","check":"API reachability","status":"SKIP","detail":"No COHERE_API_KEY in .env"})

    # OpenRouter
    ok = os.getenv("OPENROUTER_API_KEY", "")
    if ok:
        try:
            r = _http.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization":f"Bearer {ok}","Content-Type":"application/json",
                         "HTTP-Referer":"https://verighana.gh","X-Title":"VeriGhana"},
                json={"model":"meta-llama/llama-3.3-70b-instruct:free",
                      "messages":[{"role":"user","content":"Reply: ONLINE"}],"max_tokens":5},
                timeout=12)
            r.raise_for_status()
            results.append({"provider":"OpenRouter","check":"API reachability","status":"PASS","detail":"llama-3.3-70b-instruct:free"})
        except Exception as exc:
            results.append({"provider":"OpenRouter","check":"API reachability","status":"FAIL","detail":str(exc)[:120]})
    else:
        results.append({"provider":"OpenRouter","check":"API reachability","status":"SKIP","detail":"No OPENROUTER_API_KEY in .env"})

    passes = sum(1 for r in results if r["status"] == "PASS")
    fails  = sum(1 for r in results if r["status"] == "FAIL")
    skips  = sum(1 for r in results if r["status"] == "SKIP")

    return {
        "results":   results,
        "summary":   {"pass": passes, "fail": fails, "skip": skips},
        "healthy":   fails == 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GLOBAL ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@app.exception_handler(404)
async def not_found(request: Request, _exc: Exception):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Not found: {request.url.path} — see /docs"},
    )

@app.exception_handler(500)
async def server_error(_request: Request, _exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error — check server logs."},
    )