-- ── Admin Audit Log ──────────────────────────────────────────
-- Tracks admin actions: role changes, tier changes, user deletions
-- Run once in Supabase → SQL Editor
CREATE TABLE IF NOT EXISTS admin_audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_email TEXT NOT NULL,
  action      TEXT NOT NULL,
  target_id   TEXT,
  target_email TEXT,
  details     JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON admin_audit_log (created_at DESC);
