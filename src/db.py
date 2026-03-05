"""
db.py — VeriGhana Database Operations
========================================
All Supabase queries in one place.
Uses the service_role key so it bypasses Row Level Security.
Never expose the service_role key to the frontend.
"""

import os, hashlib
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client

_supabase: Optional[Client] = None

def get_db() -> Client:
    global _supabase
    if _supabase is None:
        url = os.environ["SUPABASE_URL"]
        # Use service_role key here — this backend runs server-side only
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
        _supabase = create_client(url, key)
    return _supabase


# ══════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════

async def create_user(email: str, password_hash: str, full_name: str = None,
                      organisation: str = None, role: str = "client") -> dict:
    db = get_db()
    result = db.table("vg_users").insert({
        "email":         email.lower().strip(),
        "password_hash": password_hash,
        "full_name":     full_name,
        "organisation":  organisation,
        "role":          role,
        "tier":          "free",
        "is_active":     True,
        "is_verified":   False,
    }).execute()
    return result.data[0] if result.data else None


async def get_user_by_email(email: str) -> Optional[dict]:
    db = get_db()
    result = db.table("vg_users") \
        .select("*") \
        .eq("email", email.lower().strip()) \
        .single() \
        .execute()
    return result.data


async def get_user_by_id(user_id: str) -> Optional[dict]:
    db = get_db()
    result = db.table("vg_users") \
        .select("*") \
        .eq("id", user_id) \
        .single() \
        .execute()
    return result.data


async def get_user_by_api_key(raw_key: str) -> Optional[dict]:
    """Find a user by their raw API key. Checks prefix first for efficiency."""
    from auth import verify_api_key_hash
    db = get_db()
    prefix = raw_key[:12]
    keys_result = db.table("vg_api_keys") \
        .select("*, vg_users(*)") \
        .eq("key_prefix", prefix) \
        .eq("is_active", True) \
        .execute()
    for row in (keys_result.data or []):
        if verify_api_key_hash(raw_key, row["key_hash"]):
            # Update last used
            db.table("vg_api_keys").update({
                "last_used_at":   datetime.now(timezone.utc).isoformat(),
                "requests_total": row["requests_total"] + 1,
            }).eq("id", row["id"]).execute()
            return row.get("vg_users")
    return None


async def update_user(user_id: str, **fields) -> dict:
    db = get_db()
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = db.table("vg_users") \
        .update(fields) \
        .eq("id", user_id) \
        .execute()
    return result.data[0] if result.data else None


async def update_last_login(user_id: str):
    db = get_db()
    db.table("vg_users").update({
        "last_login": datetime.now(timezone.utc).isoformat()
    }).eq("id", user_id).execute()


async def set_user_tier(user_id: str, tier: str):
    db = get_db()
    db.table("vg_users").update({"tier": tier, "updated_at": datetime.now(timezone.utc).isoformat()}) \
        .eq("id", user_id).execute()


# ══════════════════════════════════════════════
#  SUBSCRIPTIONS
# ══════════════════════════════════════════════

async def get_active_subscription(user_id: str) -> Optional[dict]:
    db = get_db()
    result = db.table("vg_subscriptions") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else None


async def create_subscription(user_id: str, tier: str, billing_cycle: str = "monthly",
                               amount_usd: float = 0, discount_pct: int = 0,
                               promo_code_id: str = None,
                               trial_days: int = 0) -> dict:
    from datetime import timedelta
    db = get_db()

    # Cancel any existing active subscription first
    db.table("vg_subscriptions").update({
        "status": "cancelled",
        "cancelled_at": datetime.now(timezone.utc).isoformat()
    }).eq("user_id", user_id).eq("status", "active").execute()

    now = datetime.now(timezone.utc)
    period_end = None
    trial_ends = None

    if tier != "free":
        days = 365 if billing_cycle == "annual" else 30
        period_end = (now + timedelta(days=days)).isoformat()
    if trial_days > 0:
        trial_ends = (now + timedelta(days=trial_days)).isoformat()

    result = db.table("vg_subscriptions").insert({
        "user_id":              user_id,
        "tier":                 tier,
        "status":               "trialing" if trial_days > 0 else "active",
        "billing_cycle":        billing_cycle,
        "amount_usd":           amount_usd,
        "discount_pct":         discount_pct,
        "promo_code_id":        promo_code_id,
        "trial_ends_at":        trial_ends,
        "current_period_start": now.isoformat(),
        "current_period_end":   period_end,
    }).execute()

    # Also update the user's tier
    await set_user_tier(user_id, tier)
    return result.data[0] if result.data else None


async def cancel_subscription(user_id: str) -> dict:
    db = get_db()
    result = db.table("vg_subscriptions").update({
        "status": "cancelled",
        "cancelled_at": datetime.now(timezone.utc).isoformat()
    }).eq("user_id", user_id).eq("status", "active").execute()
    await set_user_tier(user_id, "free")
    return result.data[0] if result.data else None


# ══════════════════════════════════════════════
#  USAGE LOGS + RATE LIMITING
# ══════════════════════════════════════════════

async def log_usage(user_id: Optional[str], endpoint: str,
                    claim_text: Optional[str] = None,
                    verdict: Optional[str] = None, score: Optional[int] = None,
                    model_used: Optional[str] = None, processing_ms: Optional[int] = None,
                    ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                    api_key_id: Optional[str] = None):
    db = get_db()
    claim_hash = hashlib.sha256(claim_text.encode()).hexdigest() if claim_text else None
    try:
        db.table("vg_usage_logs").insert({
            "user_id":       user_id,
            "api_key_id":    api_key_id,
            "endpoint":      endpoint,
            "claim_hash":    claim_hash,
            "verdict":       verdict,
            "score":         score,
            "model_used":    model_used,
            "processing_ms": processing_ms,
            "ip_address":    ip_address,
            "user_agent":    user_agent,
        }).execute()
    except Exception as e:
        print(f"Usage log error (non-fatal): {e}")


async def get_daily_usage_count(user_id: str) -> int:
    """Count this user's requests in the last 24 hours."""
    db = get_db()
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    result = db.table("vg_usage_logs") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .gte("created_at", since) \
        .execute()
    return result.count or 0


async def check_rate_limit(user_id: str, tier: str) -> dict:
    """
    Returns {"allowed": bool, "used": int, "limit": int|None, "remaining": int|None}
    """
    from auth import get_daily_limit
    limit = get_daily_limit(tier)
    if limit is None:
        return {"allowed": True, "used": 0, "limit": None, "remaining": None}
    used = await get_daily_usage_count(user_id)
    return {
        "allowed":   used < limit,
        "used":      used,
        "limit":     limit,
        "remaining": max(0, limit - used),
    }


# ══════════════════════════════════════════════
#  API KEYS
# ══════════════════════════════════════════════

async def create_api_key(user_id: str, key_prefix: str, key_hash: str, name: str = "Default") -> dict:
    db = get_db()
    result = db.table("vg_api_keys").insert({
        "user_id":    user_id,
        "key_prefix": key_prefix,
        "key_hash":   key_hash,
        "name":       name,
        "is_active":  True,
    }).execute()
    return result.data[0] if result.data else None


async def list_api_keys(user_id: str) -> list[dict]:
    db = get_db()
    result = db.table("vg_api_keys") \
        .select("id, key_prefix, name, is_active, last_used_at, requests_total, created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()
    return result.data or []


async def revoke_api_key(key_id: str, user_id: str) -> bool:
    db = get_db()
    result = db.table("vg_api_keys").update({"is_active": False}) \
        .eq("id", key_id).eq("user_id", user_id).execute()
    return bool(result.data)


# ══════════════════════════════════════════════
#  PROMO CODES
# ══════════════════════════════════════════════

async def get_promo_by_code(code: str) -> Optional[dict]:
    db = get_db()
    result = db.table("vg_promo_codes") \
        .select("*") \
        .eq("code", code.upper().strip()) \
        .eq("is_active", True) \
        .single() \
        .execute()
    return result.data


async def validate_promo(code: str, user_id: str, tier: str) -> dict:
    """
    Returns {"valid": bool, "promo": dict|None, "error": str|None}
    """
    promo = await get_promo_by_code(code)
    if not promo:
        return {"valid": False, "promo": None, "error": "Invalid or expired promo code."}

    now = datetime.now(timezone.utc)

    # Check expiry
    if promo.get("valid_until"):
        expiry = datetime.fromisoformat(promo["valid_until"].replace("Z",""))
        if expiry.replace(tzinfo=timezone.utc) < now:
            return {"valid": False, "promo": None, "error": "This promo code has expired."}

    # Check usage limit
    if promo.get("max_uses") and promo["uses_count"] >= promo["max_uses"]:
        return {"valid": False, "promo": None, "error": "This promo code has reached its usage limit."}

    # Check applies_to
    db = get_db()
    user = await get_user_by_id(user_id)
    is_new = (datetime.now(timezone.utc) - datetime.fromisoformat(
        user["created_at"].replace("Z","")).replace(tzinfo=timezone.utc)).days < 1
    if promo["applies_to"] == "new_users" and not is_new:
        return {"valid": False, "promo": None, "error": "This code is only for new users."}
    if promo["applies_to"] == "existing_users" and is_new:
        return {"valid": False, "promo": None, "error": "This code is only for existing users."}

    # Check already used
    used = db.table("vg_promo_redemptions") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("promo_id", promo["id"]) \
        .execute()
    if used.data:
        return {"valid": False, "promo": None, "error": "You have already used this promo code."}

    return {"valid": True, "promo": promo, "error": None}


async def redeem_promo(promo_id: str, user_id: str):
    db = get_db()
    db.table("vg_promo_redemptions").insert({
        "user_id":  user_id,
        "promo_id": promo_id,
    }).execute()
    # Increment uses_count
    db.rpc("increment_promo_uses", {"promo_id_arg": promo_id}).execute()


# ══════════════════════════════════════════════
#  REFRESH TOKENS
# ══════════════════════════════════════════════

async def store_refresh_token(user_id: str, token_hash: str, expires_at: str):
    db = get_db()
    db.table("vg_refresh_tokens").insert({
        "user_id":    user_id,
        "token_hash": token_hash,
        "expires_at": expires_at,
    }).execute()


async def validate_refresh_token(token_hash: str) -> Optional[dict]:
    db = get_db()
    result = db.table("vg_refresh_tokens") \
        .select("*, vg_users(*)") \
        .eq("token_hash", token_hash) \
        .eq("is_revoked", False) \
        .gte("expires_at", datetime.now(timezone.utc).isoformat()) \
        .single() \
        .execute()
    return result.data


async def revoke_refresh_token(token_hash: str):
    db = get_db()
    db.table("vg_refresh_tokens").update({"is_revoked": True}) \
        .eq("token_hash", token_hash).execute()


async def revoke_all_refresh_tokens(user_id: str):
    """Called on password change or account suspension."""
    db = get_db()
    db.table("vg_refresh_tokens").update({"is_revoked": True}) \
        .eq("user_id", user_id).execute()


# ══════════════════════════════════════════════
#  ADMIN QUERIES
# ══════════════════════════════════════════════

async def admin_list_users(limit: int = 50, offset: int = 0,
                            tier: str = None, role: str = None,
                            search: str = None) -> dict:
    db = get_db()
    q = db.table("vg_admin_users_view").select("*")
    if tier:   q = q.eq("tier", tier)
    if role:   q = q.eq("role", role)
    if search: q = q.ilike("email", f"%{search}%")
    result = q.range(offset, offset + limit - 1).execute()
    count_result = db.table("vg_users").select("id", count="exact").execute()
    return {"users": result.data or [], "total": count_result.count or 0}


async def admin_get_stats() -> dict:
    db = get_db()
    users_res   = db.table("vg_users").select("id", count="exact").execute()
    pro_res     = db.table("vg_users").select("id", count="exact").eq("tier", "pro").execute()
    inst_res    = db.table("vg_users").select("id", count="exact").eq("tier", "institutional").execute()
    req_res     = db.table("vg_usage_logs").select("id", count="exact").execute()
    promos_res  = db.table("vg_promo_codes").select("id, code, uses_count, max_uses").eq("is_active", True).execute()
    daily_res   = db.table("vg_daily_stats").select("*").limit(7).execute()
    return {
        "total_users":        users_res.count or 0,
        "pro_users":          pro_res.count or 0,
        "institutional_users": inst_res.count or 0,
        "total_requests":     req_res.count or 0,
        "active_promos":      promos_res.data or [],
        "daily_stats":        daily_res.data or [],
    }


async def admin_list_promos() -> list[dict]:
    db = get_db()
    result = db.table("vg_promo_codes") \
        .select("*, vg_users(email)") \
        .order("created_at", desc=True) \
        .execute()
    return result.data or []


async def admin_create_promo(data: dict, created_by: str) -> dict:
    db = get_db()
    data["code"] = data["code"].upper().strip()
    data["created_by"] = created_by
    result = db.table("vg_promo_codes").insert(data).execute()
    return result.data[0] if result.data else None


async def admin_toggle_user(user_id: str, is_active: bool) -> dict:
    db = get_db()
    result = db.table("vg_users").update({
        "is_active":  is_active,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", user_id).execute()
    if not is_active:
        await revoke_all_refresh_tokens(user_id)
    return result.data[0] if result.data else None


async def admin_change_user_tier(user_id: str, tier: str,
                                  billing_cycle: str = "monthly",
                                  admin_id: str = None) -> dict:
    from auth import TIER_PRICES
    amount = TIER_PRICES.get(tier, {}).get(billing_cycle, 0)
    return await create_subscription(user_id, tier, billing_cycle, amount)


# ══════════════════════════════════════════════
#  INSTITUTIONAL SEATS
# ══════════════════════════════════════════════

async def list_seats(org_user_id: str) -> list[dict]:
    db = get_db()
    result = db.table("vg_seats") \
        .select("*, vg_users(email, full_name)") \
        .eq("org_user_id", org_user_id) \
        .neq("status", "removed") \
        .execute()
    return result.data or []


async def invite_seat(org_user_id: str, email: str) -> dict:
    import secrets as sec
    db = get_db()
    token = sec.token_urlsafe(32)
    result = db.table("vg_seats").insert({
        "org_user_id":   org_user_id,
        "invite_email":  email.lower().strip(),
        "invite_token":  token,
        "status":        "pending",
    }).execute()
    return {**(result.data[0] if result.data else {}), "invite_token": token}


async def remove_seat(org_user_id: str, seat_id: str):
    db = get_db()
    db.table("vg_seats").update({"status": "removed"}) \
        .eq("id", seat_id).eq("org_user_id", org_user_id).execute()
