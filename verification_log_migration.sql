-- Run this in Supabase SQL Editor: Dashboard → SQL Editor → New Query
-- If you previously ran this and got an error, the table may be partially
-- created. Run the DROP line first, then the rest.

-- DROP TABLE IF EXISTS verification_log;  -- uncomment if re-running

CREATE TABLE IF NOT EXISTS verification_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL,          -- no FK to auth.users (SQL Editor lacks that permission)
    input_claim     TEXT NOT NULL,
    score           INTEGER,
    verdict         TEXT,
    explanation     TEXT,
    matched_sources TEXT,
    model_used      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_log_user
    ON verification_log (user_id, created_at DESC);

ALTER TABLE verification_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_history" ON verification_log
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
