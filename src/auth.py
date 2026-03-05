"""
auth.py — VeriGhana Authentication
====================================
Handles:
  - Password hashing (bcrypt)
  - JWT access + refresh tokens
  - API key generation and validation
  - Permission checking by role + tier
"""

import os, secrets, hashlib, string
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader

# ── Secrets (set in .env)
SECRET_KEY       = os.environ.get("JWT_SECRET_KEY",    "change-this-in-production-use-a-long-random-string")
REFRESH_SECRET   = os.environ.get("JWT_REFRESH_SECRET", "change-this-refresh-secret-too")
ALGORITHM        = "HS256"
ACCESS_TOKEN_TTL  = int(os.environ.get("ACCESS_TOKEN_TTL_MINUTES", 30))    # 30 minutes
REFRESH_TOKEN_TTL = int(os.environ.get("REFRESH_TOKEN_TTL_DAYS",   30))    # 30 days

# ── Rate limits by tier (requests per 24 hours; None = unlimited)
TIER_DAILY_LIMITS = {
    "free":          5,
    "pro":           None,
    "institutional": None,
}

# ── Feature flags by tier
TIER_FEATURES = {
    "free": {
        "api_keys":       False,
        "bulk_verify":    False,
        "export":         False,
        "alerts":         False,
        "seats":          False,
        "max_seats":      0,
        "models":         ["gemini-2.0-flash-lite"],  # cheapest only
    },
    "pro": {
        "api_keys":       True,
        "bulk_verify":    False,
        "export":         True,
        "alerts":         True,
        "seats":          False,
        "max_seats":      0,
        "models":         ["gemini-2.0-flash", "gemini-2.0-flash-lite",
                           "gemini-1.5-flash", "gemini-1.5-flash-8b"],
    },
    "institutional": {
        "api_keys":       True,
        "bulk_verify":    True,
        "export":         True,
        "alerts":         True,
        "seats":          True,
        "max_seats":      20,
        "models":         ["gemini-2.0-flash", "gemini-2.0-flash-lite",
                           "gemini-1.5-flash", "gemini-1.5-flash-8b"],
    },
}

# ── Pricing table (used by billing + promo logic)
TIER_PRICES = {
    "free":          {"monthly": 0,     "annual": 0},
    "pro":           {"monthly": 9.99,  "annual": 7.99},
    "institutional": {"monthly": 79.99, "annual": 63.99},
}

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ═══════════════════════════════════════════════
#  PASSWORD
# ═══════════════════════════════════════════════
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def validate_password_strength(password: str) -> list[str]:
    """Returns list of violations. Empty list = password is strong."""
    errors = []
    if len(password) < 8:
        errors.append("Must be at least 8 characters.")
    if not any(c.isupper() for c in password):
        errors.append("Must contain at least one uppercase letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Must contain at least one number.")
    return errors


# ═══════════════════════════════════════════════
#  JWT TOKENS
# ═══════════════════════════════════════════════
def create_access_token(user_id: str, email: str, role: str, tier: str) -> str:
    payload = {
        "sub":   user_id,
        "email": email,
        "role":  role,
        "tier":  tier,
        "type":  "access",
        "exp":   datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL),
        "iat":   datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (raw_token, hashed_token). Store the hash; send raw to client."""
    raw = secrets.token_urlsafe(64)
    payload = {
        "sub":  user_id,
        "type": "refresh",
        "jti":  secrets.token_hex(16),   # unique ID so we can revoke
        "exp":  datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL),
        "iat":  datetime.now(timezone.utc),
    }
    signed = jwt.encode(payload, REFRESH_SECRET, algorithm=ALGORITHM)
    token_hash = hashlib.sha256(signed.encode()).hexdigest()
    return signed, token_hash


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type.")
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalid or expired: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, REFRESH_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type.")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Refresh token invalid: {str(e)}")


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ═══════════════════════════════════════════════
#  API KEYS
# ═══════════════════════════════════════════════
def generate_api_key() -> tuple[str, str, str]:
    """
    Returns (raw_key, key_prefix, key_hash).
      raw_key   — shown once to user, never stored
      key_prefix — first 12 chars stored for display (e.g. "vg_a3f8d2c1")
      key_hash  — bcrypt hash stored in DB for validation
    """
    body    = secrets.token_urlsafe(32)
    raw_key = f"vg_{body}"
    prefix  = raw_key[:12]
    hashed  = pwd_context.hash(raw_key)
    return raw_key, prefix, hashed


def verify_api_key_hash(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


# ═══════════════════════════════════════════════
#  CURRENT USER DEPENDENCY
# ═══════════════════════════════════════════════
async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Security(api_key_header),
):
    """
    FastAPI dependency. Resolves identity from:
      1. Bearer JWT token (web app / Streamlit)
      2. X-API-Key header (Pro/Institutional API consumers)

    Returns the decoded token payload or raises 401.
    """
    # --- API Key path
    if api_key:
        from db import get_user_by_api_key  # lazy import avoids circular
        user = await get_user_by_api_key(api_key)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key.")
        if not user.get("is_active"):
            raise HTTPException(status_code=403, detail="Account is suspended.")
        return {
            "sub":    str(user["id"]),
            "email":  user["email"],
            "role":   user["role"],
            "tier":   user["tier"],
            "via":    "api_key",
        }

    # --- JWT path
    if token:
        payload = decode_access_token(token)
        return {**payload, "via": "jwt"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Security(api_key_header),
):
    """Like get_current_user but returns None instead of raising for unauthenticated."""
    try:
        return await get_current_user(token, api_key)
    except HTTPException:
        return None


def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def require_tier(*tiers: str):
    """Usage: Depends(require_tier('pro', 'institutional'))"""
    def checker(user: dict = Depends(get_current_user)):
        if user.get("role") == "admin":
            return user  # admins bypass tier checks
        if user.get("tier") not in tiers:
            raise HTTPException(
                status_code=403,
                detail=f"This feature requires a {' or '.join(tiers)} subscription."
            )
        return user
    return checker


def check_feature(user: dict, feature: str) -> bool:
    """Check if user's tier includes a named feature."""
    if user.get("role") == "admin":
        return True
    tier = user.get("tier", "free")
    return TIER_FEATURES.get(tier, {}).get(feature, False)


def get_allowed_models(user: dict) -> list[str]:
    if user.get("role") == "admin":
        return list(TIER_FEATURES["institutional"]["models"])
    tier = user.get("tier", "free")
    return TIER_FEATURES.get(tier, TIER_FEATURES["free"])["models"]


def get_daily_limit(tier: str) -> Optional[int]:
    return TIER_DAILY_LIMITS.get(tier, 5)
