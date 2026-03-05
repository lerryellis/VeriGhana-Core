"""
schemas.py — VeriGhana Request/Response Models
================================================
All Pydantic models used by the API.
"""

from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional, List, Any
from datetime import datetime


# ══════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════

class RegisterRequest(BaseModel):
    email:         EmailStr
    password:      str
    full_name:     Optional[str] = None
    organisation:  Optional[str] = None   # for institutional signups
    promo_code:    Optional[str] = None   # apply promo at registration

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v):
        if not v or len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password:     str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token:        str
    new_password: str


# ══════════════════════════════════════════════
#  USER
# ══════════════════════════════════════════════

class UserProfile(BaseModel):
    id:            str
    email:         str
    full_name:     Optional[str]
    organisation:  Optional[str]
    role:          str
    tier:          str
    is_active:     bool
    is_verified:   bool
    last_login:    Optional[datetime]
    created_at:    datetime


class UserUpdateRequest(BaseModel):
    full_name:    Optional[str] = None
    organisation: Optional[str] = None


class RateLimitStatus(BaseModel):
    allowed:   bool
    used:      int
    limit:     Optional[int]   # None = unlimited
    remaining: Optional[int]


# ══════════════════════════════════════════════
#  VERIFICATION
# ══════════════════════════════════════════════

class VerifyRequest(BaseModel):
    claim: str
    model: Optional[str] = None  # if None, uses tier default

    @field_validator("claim")
    @classmethod
    def claim_not_empty(cls, v):
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Claim is too short.")
        if len(v) > 2000:
            raise ValueError("Claim exceeds 2000 character limit.")
        return v


class BulkVerifyRequest(BaseModel):
    """Institutional-tier feature: verify up to 20 claims at once."""
    claims:  List[str]
    model:   Optional[str] = None

    @field_validator("claims")
    @classmethod
    def limit_claims(cls, v):
        if len(v) > 20:
            raise ValueError("Bulk verify is limited to 20 claims per request.")
        return v


class SourceCitation(BaseModel):
    title:  str
    url:    Optional[str]
    source: str


class VerifyResponse(BaseModel):
    verdict:       str          # VERIFIED | UNCORROBORATED | FALSE | PARTIAL | ERROR
    score:         int          # 0–100
    explanation:   str
    sources:       List[SourceCitation]
    model_used:    str
    search_method: str
    processing_ms: int
    rate_limit:    Optional[RateLimitStatus] = None


class BulkVerifyResponse(BaseModel):
    results:       List[VerifyResponse]
    total:         int
    processing_ms: int


# ══════════════════════════════════════════════
#  SUBSCRIPTIONS
# ══════════════════════════════════════════════

class SubscriptionInfo(BaseModel):
    tier:                 str
    status:               str
    billing_cycle:        Optional[str]
    amount_usd:           float
    discount_pct:         int
    current_period_end:   Optional[datetime]
    trial_ends_at:        Optional[datetime]
    features:             dict


class UpgradeRequest(BaseModel):
    tier:          str   # "pro" or "institutional"
    billing_cycle: str = "monthly"  # "monthly" or "annual"
    promo_code:    Optional[str] = None

    @field_validator("tier")
    @classmethod
    def valid_tier(cls, v):
        if v not in ("pro", "institutional"):
            raise ValueError("Tier must be 'pro' or 'institutional'.")
        return v

    @field_validator("billing_cycle")
    @classmethod
    def valid_cycle(cls, v):
        if v not in ("monthly", "annual"):
            raise ValueError("Billing cycle must be 'monthly' or 'annual'.")
        return v


# ══════════════════════════════════════════════
#  API KEYS
# ══════════════════════════════════════════════

class ApiKeyCreateRequest(BaseModel):
    name: str = "Default"


class ApiKeyResponse(BaseModel):
    id:              str
    key_prefix:      str
    name:            str
    is_active:       bool
    last_used_at:    Optional[datetime]
    requests_total:  int
    created_at:      datetime
    raw_key:         Optional[str] = None  # Only set on creation


# ══════════════════════════════════════════════
#  PROMO CODES
# ══════════════════════════════════════════════

class PromoValidateRequest(BaseModel):
    code: str


class PromoValidateResponse(BaseModel):
    valid:          bool
    code:           Optional[str]
    type:           Optional[str]          # discount | tier_unlock | trial_extension
    discount_pct:   Optional[int]
    unlocks_tier:   Optional[str]
    unlock_days:    Optional[int]
    description:    Optional[str]
    error:          Optional[str]


class PromoCreateRequest(BaseModel):
    """Admin-only: create a new promo code."""
    code:           str
    description:    Optional[str] = None
    type:           str = "discount"
    discount_pct:   int = 0
    unlocks_tier:   Optional[str] = None
    unlock_days:    int = 30
    max_uses:       Optional[int] = 100
    applies_to:     str = "all"
    valid_until:    Optional[datetime] = None

    @field_validator("type")
    @classmethod
    def valid_type(cls, v):
        if v not in ("discount", "tier_unlock", "trial_extension"):
            raise ValueError("Invalid promo type.")
        return v

    @field_validator("discount_pct")
    @classmethod
    def valid_discount(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Discount must be 0–100.")
        return v


# ══════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════

class AdminUserListResponse(BaseModel):
    users: List[Any]
    total: int


class AdminStatsResponse(BaseModel):
    total_users:         int
    pro_users:           int
    institutional_users: int
    total_requests:      int
    active_promos:       List[Any]
    daily_stats:         List[Any]


class AdminTierChangeRequest(BaseModel):
    tier:          str
    billing_cycle: str = "monthly"

    @field_validator("tier")
    @classmethod
    def valid_tier(cls, v):
        if v not in ("free","pro","institutional"):
            raise ValueError("Invalid tier.")
        return v


# ══════════════════════════════════════════════
#  SEATS (Institutional)
# ══════════════════════════════════════════════

class SeatInviteRequest(BaseModel):
    email: EmailStr


class SeatResponse(BaseModel):
    id:           str
    invite_email: str
    status:       str
    invited_at:   datetime
    accepted_at:  Optional[datetime]
    user:         Optional[dict]   # linked vg_users record if accepted
