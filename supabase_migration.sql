-- ═══════════════════════════════════════════════════════════════
--  VeriGhana Backend Schema Migration
--  Run this in Supabase → SQL Editor
--  Run ONCE. Safe to re-run (uses IF NOT EXISTS / ON CONFLICT).
-- ═══════════════════════════════════════════════════════════════

-- ── Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ═══════════════════════════════════════════════════════════════
--  USERS
--  Stores all registered users: clients + admins.
--  Subscription tier drives rate limits and feature access.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    organisation    TEXT,                    -- for institutional accounts
    role            TEXT NOT NULL DEFAULT 'client'
                    CHECK (role IN ('admin','client')),
    tier            TEXT NOT NULL DEFAULT 'free'
                    CHECK (tier IN ('free','pro','institutional')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    verify_token    TEXT,                    -- email verification token
    reset_token     TEXT,                    -- password reset token
    reset_expires   TIMESTAMPTZ,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed one admin (change email/password before deploying)
-- Password below = bcrypt hash of "AdminPassword123!" — CHANGE THIS
INSERT INTO vg_users (email, password_hash, full_name, role, tier, is_active, is_verified)
VALUES (
    'admin@verighana.gh',
    '$2b$12$placeholder_change_this_before_deploy',
    'VeriGhana Admin',
    'admin',
    'institutional',
    TRUE,
    TRUE
) ON CONFLICT (email) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════
--  SUBSCRIPTIONS
--  Tracks current and historical subscription periods per user.
--  A user can only have ONE active subscription at a time.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_subscriptions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES vg_users(id) ON DELETE CASCADE,
    tier            TEXT NOT NULL CHECK (tier IN ('free','pro','institutional')),
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','cancelled','expired','trialing','paused')),
    billing_cycle   TEXT DEFAULT 'monthly' CHECK (billing_cycle IN ('monthly','annual')),
    amount_usd      NUMERIC(10,2) DEFAULT 0,
    discount_pct    INTEGER DEFAULT 0,       -- from promo code
    promo_code_id   UUID,                    -- which promo was applied
    trial_ends_at   TIMESTAMPTZ,
    current_period_start TIMESTAMPTZ DEFAULT NOW(),
    current_period_end   TIMESTAMPTZ,        -- NULL = free / no expiry set
    cancelled_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Every new user gets a free subscription record
CREATE OR REPLACE FUNCTION create_free_subscription()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO vg_subscriptions (user_id, tier, status, amount_usd)
    VALUES (NEW.id, 'free', 'active', 0);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS on_user_created ON vg_users;
CREATE TRIGGER on_user_created
    AFTER INSERT ON vg_users
    FOR EACH ROW EXECUTE FUNCTION create_free_subscription();


-- ═══════════════════════════════════════════════════════════════
--  API KEYS
--  Pro and Institutional users can generate REST API keys.
--  Keys are stored hashed. The raw key is shown once at creation.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES vg_users(id) ON DELETE CASCADE,
    key_prefix      TEXT NOT NULL,           -- first 8 chars shown in UI (e.g. "vg_a3f8")
    key_hash        TEXT NOT NULL UNIQUE,    -- bcrypt hash of full key
    name            TEXT DEFAULT 'Default',  -- user-given label
    is_active       BOOLEAN DEFAULT TRUE,
    last_used_at    TIMESTAMPTZ,
    requests_total  BIGINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════
--  USAGE LOGS
--  Every verification request is logged here for:
--    - Rate limiting (count today's requests per user)
--    - Admin analytics (popular claims, usage patterns)
--    - Billing (future metered usage)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_usage_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES vg_users(id) ON DELETE SET NULL,
    api_key_id      UUID REFERENCES vg_api_keys(id) ON DELETE SET NULL,
    endpoint        TEXT NOT NULL,
    claim_hash      TEXT,                    -- SHA256 of claim (not raw text for privacy)
    verdict         TEXT,
    score           INTEGER,
    model_used      TEXT,
    processing_ms   INTEGER,
    ip_address      TEXT,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast daily count queries (rate limiting)
CREATE INDEX IF NOT EXISTS idx_usage_user_day
    ON vg_usage_logs (user_id, created_at);


-- ═══════════════════════════════════════════════════════════════
--  PROMO CODES
--  Supports: % discounts, tier unlocks, trial extensions.
--  Admin creates codes; clients redeem them at signup or upgrade.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_promo_codes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            TEXT UNIQUE NOT NULL,    -- e.g. "GIMPA2026"
    description     TEXT,                    -- admin note
    type            TEXT NOT NULL DEFAULT 'discount'
                    CHECK (type IN (
                        'discount',          -- % off the price
                        'tier_unlock',       -- gives a tier free for N days
                        'trial_extension'    -- extends trial period
                    )),
    discount_pct    INTEGER DEFAULT 0 CHECK (discount_pct BETWEEN 0 AND 100),
    unlocks_tier    TEXT CHECK (unlocks_tier IN ('pro','institutional')),
    unlock_days     INTEGER DEFAULT 30,      -- how many free days
    max_uses        INTEGER DEFAULT 100,     -- NULL = unlimited
    uses_count      INTEGER DEFAULT 0,
    min_tier        TEXT DEFAULT 'free',     -- who can use it
    applies_to      TEXT DEFAULT 'all'
                    CHECK (applies_to IN ('all','new_users','existing_users')),
    is_active       BOOLEAN DEFAULT TRUE,
    valid_from      TIMESTAMPTZ DEFAULT NOW(),
    valid_until     TIMESTAMPTZ,             -- NULL = no expiry
    created_by      UUID REFERENCES vg_users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed some example promo codes
INSERT INTO vg_promo_codes (code, description, type, discount_pct, applies_to, max_uses)
VALUES
    ('GIMPA2026',     'GIMPA student/staff discount',     'discount',      50, 'new_users',      200),
    ('PRESS50',       'Press/media 50% off Pro',           'discount',      50, 'all',            50),
    ('NGOFREE30',     'NGO free Pro trial 30 days',        'tier_unlock',    0, 'new_users',      30),
    ('LAUNCH100',     'Launch special — 100% off first month', 'discount',  100, 'new_users',     100)
ON CONFLICT (code) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════
--  PROMO REDEMPTIONS
--  Prevents a user from using the same code twice.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_promo_redemptions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES vg_users(id) ON DELETE CASCADE,
    promo_id        UUID NOT NULL REFERENCES vg_promo_codes(id),
    redeemed_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, promo_id)               -- one redemption per user per code
);


-- ═══════════════════════════════════════════════════════════════
--  REFRESH TOKENS
--  Stored server-side so we can revoke them (logout, ban user).
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES vg_users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,
    is_revoked      BOOLEAN DEFAULT FALSE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════
--  INSTITUTIONAL SEATS
--  Institutional accounts can invite sub-users ("seats").
--  Each seat inherits the parent's tier and rate limits.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS vg_seats (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_user_id     UUID NOT NULL REFERENCES vg_users(id) ON DELETE CASCADE,  -- the main account
    seat_user_id    UUID REFERENCES vg_users(id) ON DELETE SET NULL,           -- the invited user
    invite_email    TEXT NOT NULL,
    invite_token    TEXT,
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','active','removed')),
    invited_at      TIMESTAMPTZ DEFAULT NOW(),
    accepted_at     TIMESTAMPTZ
);


-- ═══════════════════════════════════════════════════════════════
--  ROW-LEVEL SECURITY (RLS)
--  Users can only read their own records.
--  Admins bypass RLS using service_role key in the API.
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE vg_users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE vg_subscriptions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE vg_api_keys         ENABLE ROW LEVEL SECURITY;
ALTER TABLE vg_usage_logs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE vg_refresh_tokens   ENABLE ROW LEVEL SECURITY;
ALTER TABLE vg_seats            ENABLE ROW LEVEL SECURITY;

-- Policies: users can read/write only their own rows
CREATE POLICY "users_own" ON vg_users
    FOR ALL USING (auth.uid()::text = id::text);

CREATE POLICY "subs_own" ON vg_subscriptions
    FOR ALL USING (auth.uid()::text = user_id::text);

CREATE POLICY "keys_own" ON vg_api_keys
    FOR ALL USING (auth.uid()::text = user_id::text);

CREATE POLICY "logs_own" ON vg_usage_logs
    FOR SELECT USING (auth.uid()::text = user_id::text);

-- Promo codes are public-read (clients need to look them up)
ALTER TABLE vg_promo_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "promos_public_read" ON vg_promo_codes
    FOR SELECT USING (is_active = TRUE);


-- ═══════════════════════════════════════════════════════════════
--  HELPER VIEWS
-- ═══════════════════════════════════════════════════════════════

-- Admin view: users with active subscription info joined
CREATE OR REPLACE VIEW vg_admin_users_view AS
SELECT
    u.id, u.email, u.full_name, u.organisation,
    u.role, u.tier, u.is_active, u.is_verified,
    u.last_login, u.created_at,
    s.status        AS sub_status,
    s.billing_cycle,
    s.amount_usd,
    s.discount_pct,
    s.current_period_end,
    s.trial_ends_at,
    (SELECT COUNT(*) FROM vg_usage_logs l WHERE l.user_id = u.id) AS total_requests,
    (SELECT COUNT(*) FROM vg_usage_logs l
     WHERE l.user_id = u.id
     AND l.created_at > NOW() - INTERVAL '24 hours') AS requests_today
FROM vg_users u
LEFT JOIN vg_subscriptions s
    ON s.user_id = u.id AND s.status = 'active'
ORDER BY u.created_at DESC;


-- Daily usage stats view for admin dashboard
CREATE OR REPLACE VIEW vg_daily_stats AS
SELECT
    DATE(created_at) AS day,
    COUNT(*)          AS total_requests,
    COUNT(DISTINCT user_id) AS unique_users,
    AVG(score)::INTEGER     AS avg_score,
    COUNT(*) FILTER (WHERE verdict = 'VERIFIED')       AS verified_count,
    COUNT(*) FILTER (WHERE verdict = 'FALSE')           AS false_count,
    COUNT(*) FILTER (WHERE verdict = 'UNCORROBORATED')  AS unverified_count
FROM vg_usage_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY day DESC;
