"""
api.py — VeriGhana Main Backend
=================================
All API routes in one place, organized by router:

  /auth/*          — register, login, refresh, logout, password reset
  /me/*            — current user profile, subscription, API keys
  /verify          — single claim verification (rate-limited by tier)
  /verify/bulk     — bulk verification (institutional only)
  /subscription/*  — upgrade, cancel, promo codes
  /admin/*         — admin-only: users, stats, promos, tier management
  /seats/*         — institutional seat management

Run with:
    uvicorn src.api:app --reload --port 8000

Requires in .env:
    SUPABASE_URL
    SUPABASE_KEY           (anon key — for public reads)
    SUPABASE_SERVICE_KEY   (service_role — for admin operations)
    GEMINI_API_KEY
    JWT_SECRET_KEY
    JWT_REFRESH_SECRET
"""

import os, sys, time
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

# ── Internal modules
import auth as Auth
import db   as DB
from schemas import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    PasswordChangeRequest, PasswordResetRequest, PasswordResetConfirm,
    UserProfile, UserUpdateRequest, RateLimitStatus,
    VerifyRequest, VerifyResponse, BulkVerifyRequest, BulkVerifyResponse,
    SubscriptionInfo, UpgradeRequest,
    ApiKeyCreateRequest, ApiKeyResponse,
    PromoValidateRequest, PromoValidateResponse, PromoCreateRequest,
    AdminUserListResponse, AdminStatsResponse, AdminTierChangeRequest,
    SeatInviteRequest,
)

# ── VeriGhana core
try:
    from verifier import verify_claim, FREE_MODELS, DEFAULT_MODEL
except ImportError:
    print("WARNING: verifier.py not found — /verify will return mock results.")
    verify_claim  = None
    FREE_MODELS   = {"gemini-2.0-flash": "Gemini 2.0 Flash"}
    DEFAULT_MODEL = "gemini-2.0-flash"


# ══════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════
app = FastAPI(
    title       = "VeriGhana API",
    description = "Ghana's AI-Powered Fact Verification Platform — Backend API",
    version     = "2.0.0",
    docs_url    = "/docs",   # Swagger UI at /docs
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# Serve homepage (index.html must be in project root)
ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML = os.path.join(ROOT_DIR, "index.html")

@app.get("/", include_in_schema=False)
async def serve_homepage():
    if os.path.exists(INDEX_HTML):
        return FileResponse(INDEX_HTML, media_type="text/html")
    return {"message": "VeriGhana API v2.0 — visit /docs for the API reference."}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "service": "VeriGhana API"}


# ══════════════════════════════════════════════
#  AUTH ROUTES  /auth/*
# ══════════════════════════════════════════════

@app.post("/auth/register", response_model=TokenResponse, tags=["Auth"])
async def register(req: RegisterRequest):
    """Register a new user. Optionally apply a promo code at signup."""

    # Validate password strength
    errors = Auth.validate_password_strength(req.password)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    # Check email not already taken
    existing = await DB.get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    # Validate promo code if provided
    promo_data = None
    if req.promo_code:
        # We don't have a user_id yet — create user first, then redeem
        pass

    # Create user
    user = await DB.create_user(
        email        = req.email,
        password_hash= Auth.hash_password(req.password),
        full_name    = req.full_name,
        organisation = req.organisation,
    )
    if not user:
        raise HTTPException(status_code=500, detail="Could not create account. Please try again.")

    user_id = str(user["id"])

    # Apply promo code if provided
    if req.promo_code:
        promo_result = await DB.validate_promo(req.promo_code, user_id, "free")
        if promo_result["valid"]:
            promo = promo_result["promo"]
            if promo["type"] == "tier_unlock":
                await DB.create_subscription(
                    user_id=user_id, tier=promo["unlocks_tier"],
                    trial_days=promo["unlock_days"],
                    promo_code_id=promo["id"],
                )
                await DB.redeem_promo(promo["id"], user_id)
            elif promo["type"] == "discount" and promo["discount_pct"] == 100:
                # 100% discount = free month of pro
                await DB.create_subscription(
                    user_id=user_id, tier="pro", amount_usd=0,
                    discount_pct=100, promo_code_id=promo["id"],
                )
                await DB.redeem_promo(promo["id"], user_id)

    # Issue tokens
    access  = Auth.create_access_token(user_id, user["email"], user["role"], user["tier"])
    refresh, refresh_hash = Auth.create_refresh_token(user_id)
    await DB.store_refresh_token(
        user_id, refresh_hash,
        (datetime.now(timezone.utc) + timedelta(days=Auth.REFRESH_TOKEN_TTL)).isoformat()
    )

    return TokenResponse(
        access_token  = access,
        refresh_token = refresh,
        token_type    = "bearer",
        expires_in    = Auth.ACCESS_TOKEN_TTL * 60,
    )


@app.post("/auth/token", response_model=TokenResponse, tags=["Auth"])
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Login with email + password. Returns JWT access + refresh tokens."""
    user = await DB.get_user_by_email(form.username)  # OAuth2 form uses "username" field for email
    if not user or not Auth.verify_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="This account has been suspended.")

    await DB.update_last_login(str(user["id"]))

    access  = Auth.create_access_token(str(user["id"]), user["email"], user["role"], user["tier"])
    refresh, refresh_hash = Auth.create_refresh_token(str(user["id"]))
    await DB.store_refresh_token(
        str(user["id"]), refresh_hash,
        (datetime.now(timezone.utc) + timedelta(days=Auth.REFRESH_TOKEN_TTL)).isoformat()
    )
    return TokenResponse(
        access_token  = access,
        refresh_token = refresh,
        token_type    = "bearer",
        expires_in    = Auth.ACCESS_TOKEN_TTL * 60,
    )


@app.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh_token(req: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    payload = Auth.decode_refresh_token(req.refresh_token)
    token_hash = Auth.hash_refresh_token(req.refresh_token)

    stored = await DB.validate_refresh_token(token_hash)
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or has been revoked.")

    user = stored.get("vg_users") or await DB.get_user_by_id(payload["sub"])
    if not user or not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account is inactive.")

    # Rotate: revoke old, issue new
    await DB.revoke_refresh_token(token_hash)
    new_access = Auth.create_access_token(str(user["id"]), user["email"], user["role"], user["tier"])
    new_refresh, new_hash = Auth.create_refresh_token(str(user["id"]))
    await DB.store_refresh_token(
        str(user["id"]), new_hash,
        (datetime.now(timezone.utc) + timedelta(days=Auth.REFRESH_TOKEN_TTL)).isoformat()
    )
    return TokenResponse(
        access_token  = new_access,
        refresh_token = new_refresh,
        token_type    = "bearer",
        expires_in    = Auth.ACCESS_TOKEN_TTL * 60,
    )


@app.post("/auth/logout", tags=["Auth"])
async def logout(req: RefreshRequest):
    """Revoke the refresh token (client should also discard the access token)."""
    token_hash = Auth.hash_refresh_token(req.refresh_token)
    await DB.revoke_refresh_token(token_hash)
    return {"message": "Logged out successfully."}


@app.post("/auth/change-password", tags=["Auth"])
async def change_password(req: PasswordChangeRequest, user=Depends(Auth.get_current_user)):
    """Change the authenticated user's password."""
    full_user = await DB.get_user_by_id(user["sub"])
    if not Auth.verify_password(req.current_password, full_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    errors = Auth.validate_password_strength(req.new_password)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    await DB.update_user(user["sub"], password_hash=Auth.hash_password(req.new_password))
    await DB.revoke_all_refresh_tokens(user["sub"])
    return {"message": "Password changed. Please log in again."}


# ══════════════════════════════════════════════
#  ME ROUTES  /me/*
# ══════════════════════════════════════════════

@app.get("/me", response_model=UserProfile, tags=["Account"])
async def get_profile(user=Depends(Auth.get_current_user)):
    """Get the current user's profile."""
    full = await DB.get_user_by_id(user["sub"])
    if not full:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserProfile(**{k: full[k] for k in UserProfile.model_fields if k in full})


@app.patch("/me", response_model=UserProfile, tags=["Account"])
async def update_profile(req: UserUpdateRequest, user=Depends(Auth.get_current_user)):
    """Update profile fields (name, organisation)."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    updated = await DB.update_user(user["sub"], **updates)
    return UserProfile(**{k: updated[k] for k in UserProfile.model_fields if k in updated})


@app.get("/me/subscription", response_model=SubscriptionInfo, tags=["Account"])
async def get_subscription(user=Depends(Auth.get_current_user)):
    """Get the current subscription + feature flags for this user's tier."""
    sub = await DB.get_active_subscription(user["sub"])
    tier = user.get("tier", "free")
    features = Auth.TIER_FEATURES.get(tier, Auth.TIER_FEATURES["free"])
    return SubscriptionInfo(
        tier                = tier,
        status              = sub["status"]              if sub else "active",
        billing_cycle       = sub.get("billing_cycle")   if sub else None,
        amount_usd          = sub.get("amount_usd", 0)   if sub else 0,
        discount_pct        = sub.get("discount_pct", 0) if sub else 0,
        current_period_end  = sub.get("current_period_end") if sub else None,
        trial_ends_at       = sub.get("trial_ends_at")      if sub else None,
        features            = features,
    )


@app.get("/me/usage", response_model=RateLimitStatus, tags=["Account"])
async def get_usage(user=Depends(Auth.get_current_user)):
    """Check how many requests you've used today."""
    return await DB.check_rate_limit(user["sub"], user.get("tier","free"))


# ── API Keys ──────────────────────────────────

@app.get("/me/api-keys", tags=["API Keys"])
async def list_api_keys(user=Depends(Auth.get_current_user)):
    """List all API keys for the current user."""
    if not Auth.check_feature(user, "api_keys"):
        raise HTTPException(status_code=403, detail="API keys require a Pro or Institutional subscription.")
    return await DB.list_api_keys(user["sub"])


@app.post("/me/api-keys", response_model=ApiKeyResponse, tags=["API Keys"])
async def create_api_key(req: ApiKeyCreateRequest, user=Depends(Auth.get_current_user)):
    """Generate a new API key. The raw key is shown ONCE — save it securely."""
    if not Auth.check_feature(user, "api_keys"):
        raise HTTPException(status_code=403, detail="API keys require a Pro or Institutional subscription.")
    existing = await DB.list_api_keys(user["sub"])
    limit = 3 if user.get("tier") == "pro" else 20
    if len(existing) >= limit:
        raise HTTPException(status_code=400, detail=f"Maximum of {limit} API keys allowed.")
    raw, prefix, hashed = Auth.generate_api_key()
    stored = await DB.create_api_key(user["sub"], prefix, hashed, req.name)
    return ApiKeyResponse(**stored, raw_key=raw)


@app.delete("/me/api-keys/{key_id}", tags=["API Keys"])
async def revoke_api_key(key_id: str, user=Depends(Auth.get_current_user)):
    """Revoke (permanently disable) an API key."""
    revoked = await DB.revoke_api_key(key_id, user["sub"])
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found.")
    return {"message": "API key revoked."}


# ══════════════════════════════════════════════
#  VERIFY ROUTES
# ══════════════════════════════════════════════

def _call_verifier(claim: str, model: str) -> dict:
    """Call verifier.py or return a mock result if it's not installed."""
    if verify_claim is None:
        return {
            "verdict": "UNCORROBORATED", "score": 0,
            "explanation": "Verification engine not installed (verifier.py missing).",
            "sources": [], "model_used": model,
            "search_method": "mock", "processing_ms": 0,
        }
    return verify_claim(claim, model=model)


@app.post("/verify", response_model=VerifyResponse, tags=["Verification"])
async def verify(req: VerifyRequest, request: Request,
                 user=Depends(Auth.get_current_user_optional)):
    """
    Verify a claim. Works for:
      - Unauthenticated users (very limited, demo only)
      - Free users (5/day)
      - Pro users (unlimited)
      - Institutional users (unlimited)
      - API key holders (same limits as their tier)
    """
    tier    = user.get("tier", "free") if user else "free"
    user_id = user.get("sub") if user else None

    # Rate limit check
    if user_id:
        rl = await DB.check_rate_limit(user_id, tier)
        if not rl["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit of {rl['limit']} queries reached. "
                       f"Upgrade to Pro for unlimited access.",
                headers={"X-RateLimit-Limit": str(rl["limit"]),
                         "X-RateLimit-Remaining": "0"}
            )
    elif not user:
        # Unauthenticated — allow demo only, no logging
        pass

    # Model validation
    allowed_models = Auth.get_allowed_models(user) if user else ["gemini-2.0-flash-lite"]
    model = req.model or allowed_models[0]
    if model not in allowed_models:
        model = allowed_models[0]

    start = int(time.time() * 1000)
    result = _call_verifier(req.claim, model)
    ms = int(time.time() * 1000) - start

    # Log usage
    if user_id:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
        await DB.log_usage(
            user_id=user_id, endpoint="/verify",
            claim_text=req.claim,
            verdict=result.get("verdict"),
            score=result.get("score"),
            model_used=model, processing_ms=ms,
            ip_address=ip, user_agent=ua,
        )

    sources = [
        {"title": s.get("title","Untitled"),
         "url":   s.get("url_link", s.get("url","#")),
         "source":s.get("source_name", s.get("source","Unknown"))}
        for s in result.get("sources", [])
    ]

    # Current rate limit status to return in response
    rl_status = None
    if user_id:
        rl_status = await DB.check_rate_limit(user_id, tier)

    return VerifyResponse(
        verdict       = result.get("verdict", "UNCORROBORATED"),
        score         = int(result.get("score", 0)),
        explanation   = result.get("explanation", ""),
        sources       = sources,
        model_used    = result.get("model_used", model),
        search_method = result.get("search_method", "vector"),
        processing_ms = ms,
        rate_limit    = rl_status,
    )


@app.post("/verify/bulk", response_model=BulkVerifyResponse, tags=["Verification"])
async def verify_bulk(req: BulkVerifyRequest, request: Request,
                      user=Depends(Auth.get_current_user)):
    """Bulk verify up to 20 claims. Institutional tier only."""
    if not Auth.check_feature(user, "bulk_verify"):
        raise HTTPException(status_code=403,
                            detail="Bulk verification requires an Institutional subscription.")
    allowed_models = Auth.get_allowed_models(user)
    model = req.model or allowed_models[0]

    start_all = int(time.time() * 1000)
    results   = []
    for claim in req.claims:
        start = int(time.time() * 1000)
        res   = _call_verifier(claim, model)
        ms    = int(time.time() * 1000) - start
        sources = [
            {"title": s.get("title",""), "url": s.get("url_link","#"),
             "source": s.get("source_name","")}
            for s in res.get("sources",[])
        ]
        results.append(VerifyResponse(
            verdict=res.get("verdict","UNCORROBORATED"), score=int(res.get("score",0)),
            explanation=res.get("explanation",""), sources=sources,
            model_used=model, search_method=res.get("search_method","vector"),
            processing_ms=ms,
        ))
    total_ms = int(time.time() * 1000) - start_all
    return BulkVerifyResponse(results=results, total=len(results), processing_ms=total_ms)


# ══════════════════════════════════════════════
#  SUBSCRIPTION ROUTES  /subscription/*
# ══════════════════════════════════════════════

@app.post("/subscription/upgrade", tags=["Subscription"])
async def upgrade_subscription(req: UpgradeRequest, user=Depends(Auth.get_current_user)):
    """
    Upgrade to Pro or Institutional.
    In production, this should redirect to Stripe/Paystack for payment.
    For now, it directly activates the tier (demo/development mode).
    """
    from auth import TIER_PRICES
    current_tier = user.get("tier", "free")
    if req.tier == current_tier:
        raise HTTPException(status_code=400, detail=f"You are already on the {req.tier} plan.")

    base_price = TIER_PRICES[req.tier][req.billing_cycle]
    final_price = base_price
    promo = None
    discount_pct = 0
    trial_days = 0

    # Validate and apply promo code
    if req.promo_code:
        promo_result = await DB.validate_promo(req.promo_code, user["sub"], current_tier)
        if not promo_result["valid"]:
            raise HTTPException(status_code=400, detail=promo_result["error"])
        promo = promo_result["promo"]

        if promo["type"] == "discount":
            discount_pct = promo["discount_pct"]
            final_price  = base_price * (1 - discount_pct / 100)
        elif promo["type"] == "tier_unlock":
            trial_days  = promo["unlock_days"]
            final_price = 0
        elif promo["type"] == "trial_extension":
            trial_days  = promo["unlock_days"]

    sub = await DB.create_subscription(
        user_id       = user["sub"],
        tier          = req.tier,
        billing_cycle = req.billing_cycle,
        amount_usd    = round(final_price, 2),
        discount_pct  = discount_pct,
        promo_code_id = promo["id"] if promo else None,
        trial_days    = trial_days,
    )

    if promo:
        await DB.redeem_promo(promo["id"], user["sub"])

    return {
        "message":       f"Successfully upgraded to {req.tier}.",
        "tier":          req.tier,
        "billing_cycle": req.billing_cycle,
        "amount_charged": round(final_price, 2),
        "discount_pct":   discount_pct,
        "trial_days":     trial_days,
        "subscription_id": str(sub["id"]) if sub else None,
        "note": "⚠️ Payment processing not yet integrated. Add Stripe/Paystack before going live."
    }


@app.post("/subscription/cancel", tags=["Subscription"])
async def cancel_subscription(user=Depends(Auth.get_current_user)):
    """Cancel the current subscription. Reverts to free tier immediately."""
    if user.get("tier") == "free":
        raise HTTPException(status_code=400, detail="You are on the free plan already.")
    await DB.cancel_subscription(user["sub"])
    return {"message": "Subscription cancelled. You have been moved to the Free plan."}


@app.post("/subscription/promo/validate", response_model=PromoValidateResponse, tags=["Subscription"])
async def validate_promo(req: PromoValidateRequest, user=Depends(Auth.get_current_user)):
    """Check whether a promo code is valid for this user."""
    result = await DB.validate_promo(req.code, user["sub"], user.get("tier","free"))
    if not result["valid"]:
        return PromoValidateResponse(valid=False, code=req.code, error=result["error"],
                                      type=None, discount_pct=None, unlocks_tier=None,
                                      unlock_days=None, description=None)
    p = result["promo"]
    return PromoValidateResponse(
        valid=True, code=p["code"], error=None,
        type=p["type"], discount_pct=p.get("discount_pct"),
        unlocks_tier=p.get("unlocks_tier"), unlock_days=p.get("unlock_days"),
        description=p.get("description"),
    )


# ══════════════════════════════════════════════
#  STATS (public-ish — for homepage counters)
# ══════════════════════════════════════════════

@app.get("/stats", tags=["Public"])
async def public_stats():
    """Live database statistics for the homepage counters."""
    try:
        db = DB.get_db()
        articles = db.table("fact_entries").select("id", count="exact").execute()
        sources  = db.table("trusted_sources").select("id", count="exact").execute()
        claims   = db.table("vg_usage_logs").select("id", count="exact").execute()
        latest   = db.table("fact_entries").select("created_at").order("created_at", desc=True).limit(1).execute()
        last_upd = "—"
        if latest.data:
            dt = datetime.fromisoformat(latest.data[0]["created_at"].replace("Z",""))
            last_upd = dt.strftime("%d %b %Y")
        return {
            "total_articles":  articles.count or 0,
            "sources_indexed": sources.count or 0,
            "claims_checked":  claims.count or 0,
            "last_updated":    last_upd,
        }
    except Exception as e:
        return {"total_articles": 0, "sources_indexed": 0, "claims_checked": 0, "last_updated": "—"}


@app.get("/models", tags=["Public"])
async def list_models(user=Depends(Auth.get_current_user_optional)):
    """Return list of AI models available to the current user's tier."""
    allowed = Auth.get_allowed_models(user) if user else ["gemini-2.0-flash-lite"]
    return {"models": allowed, "default": allowed[0]}


# ══════════════════════════════════════════════
#  ADMIN ROUTES  /admin/*
# ══════════════════════════════════════════════

@app.get("/admin/stats", response_model=AdminStatsResponse, tags=["Admin"])
async def admin_stats(admin=Depends(Auth.require_admin)):
    """Platform-wide statistics for the admin dashboard."""
    return await DB.admin_get_stats()


@app.get("/admin/users", response_model=AdminUserListResponse, tags=["Admin"])
async def admin_list_users(
    limit: int = 50, offset: int = 0,
    tier: Optional[str] = None, role: Optional[str] = None,
    search: Optional[str] = None,
    admin=Depends(Auth.require_admin)
):
    """List all users with subscription details. Supports filtering and search."""
    return await DB.admin_list_users(limit, offset, tier, role, search)


@app.patch("/admin/users/{user_id}/tier", tags=["Admin"])
async def admin_change_tier(user_id: str, req: AdminTierChangeRequest,
                             admin=Depends(Auth.require_admin)):
    """Manually change a user's subscription tier (admin override)."""
    sub = await DB.admin_change_user_tier(user_id, req.tier, req.billing_cycle, admin["sub"])
    return {"message": f"User upgraded to {req.tier}.", "subscription": sub}


@app.patch("/admin/users/{user_id}/suspend", tags=["Admin"])
async def admin_suspend_user(user_id: str, admin=Depends(Auth.require_admin)):
    """Suspend a user account. All their tokens are revoked immediately."""
    if user_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account.")
    await DB.admin_toggle_user(user_id, False)
    return {"message": "User suspended."}


@app.patch("/admin/users/{user_id}/reactivate", tags=["Admin"])
async def admin_reactivate_user(user_id: str, admin=Depends(Auth.require_admin)):
    """Reactivate a suspended user account."""
    await DB.admin_toggle_user(user_id, True)
    return {"message": "User reactivated."}


@app.get("/admin/promos", tags=["Admin"])
async def admin_list_promos(admin=Depends(Auth.require_admin)):
    """List all promo codes with redemption stats."""
    return await DB.admin_list_promos()


@app.post("/admin/promos", tags=["Admin"])
async def admin_create_promo(req: PromoCreateRequest, admin=Depends(Auth.require_admin)):
    """Create a new promo code."""
    data = req.model_dump(exclude_none=True)
    if "valid_until" in data and data["valid_until"]:
        data["valid_until"] = data["valid_until"].isoformat()
    created = await DB.admin_create_promo(data, admin["sub"])
    if not created:
        raise HTTPException(status_code=500, detail="Could not create promo code.")
    return created


@app.patch("/admin/promos/{promo_id}/deactivate", tags=["Admin"])
async def admin_deactivate_promo(promo_id: str, admin=Depends(Auth.require_admin)):
    """Deactivate (disable) a promo code without deleting it."""
    db = DB.get_db()
    db.table("vg_promo_codes").update({"is_active": False}).eq("id", promo_id).execute()
    return {"message": "Promo code deactivated."}


# ══════════════════════════════════════════════
#  SEATS  /seats/*  (Institutional only)
# ══════════════════════════════════════════════

@app.get("/seats", tags=["Seats"])
async def list_seats(user=Depends(Auth.require_tier("institutional"))):
    """List all seat members in your organisation."""
    return await DB.list_seats(user["sub"])


@app.post("/seats/invite", tags=["Seats"])
async def invite_seat(req: SeatInviteRequest, user=Depends(Auth.require_tier("institutional"))):
    """Invite a new user to your organisation as a seat."""
    seats = await DB.list_seats(user["sub"])
    max_seats = Auth.TIER_FEATURES["institutional"]["max_seats"]
    if len(seats) >= max_seats:
        raise HTTPException(status_code=400,
                            detail=f"Maximum of {max_seats} seats allowed. Contact sales to expand.")
    result = await DB.invite_seat(user["sub"], req.email)
    return {
        "message": f"Invitation sent to {req.email}.",
        "invite_token": result.get("invite_token"),
        "note": "⚠️ Email delivery not yet integrated. Send the invite_token manually."
    }


@app.delete("/seats/{seat_id}", tags=["Seats"])
async def remove_seat(seat_id: str, user=Depends(Auth.require_tier("institutional"))):
    """Remove a seat member from your organisation."""
    await DB.remove_seat(user["sub"], seat_id)
    return {"message": "Seat removed."}


# ══════════════════════════════════════════════
#  ERROR HANDLERS
# ══════════════════════════════════════════════

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse(status_code=404,
                        content={"detail": f"Route not found: {request.url.path}"})

@app.exception_handler(500)
async def server_error(request: Request, exc):
    return JSONResponse(status_code=500,
                        content={"detail": "Internal server error. Check server logs."})