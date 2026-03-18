-- Run this in Supabase SQL editor: Dashboard → SQL Editor → New Query

CREATE TABLE IF NOT EXISTS verification_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    input_claim     TEXT NOT NULL,
    score           INTEGER,
    verdict         TEXT,
    explanation     TEXT,
    matched_sources TEXT,   -- JSON.stringify'd array of source objects
    model_used      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_log_user
    ON verification_log (user_id, created_at DESC);

ALTER TABLE verification_log ENABLE ROW LEVEL SECURITY;

-- Users can only see and modify their own records
CREATE POLICY "users_own_history" ON verification_log
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
