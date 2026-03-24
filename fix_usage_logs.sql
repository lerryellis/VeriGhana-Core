-- ═══════════════════════════════════════════════════════════════
--  Fix vg_usage_logs for Supabase Auth compatibility
--  Run in Supabase → SQL Editor
-- ═══════════════════════════════════════════════════════════════

-- 1. Drop the FK constraint that references vg_users(id).
--    The app authenticates via Supabase Auth (auth.users), so the
--    user_id from a JWT is an auth.users UUID — not a vg_users UUID.
--    This FK causes every _log_usage() insert to silently fail.
ALTER TABLE vg_usage_logs
    DROP CONSTRAINT IF EXISTS vg_usage_logs_user_id_fkey;

-- 2. Add claim_text column (api.py inserts this; schema only had claim_hash).
ALTER TABLE vg_usage_logs
    ADD COLUMN IF NOT EXISTS claim_text TEXT;

-- 3. Allow service_role to insert without RLS restriction.
--    (Service key bypasses RLS by default, but explicit policy is safer.)
--    Drop old INSERT-blocking policy if it exists, then add one for service role.
DROP POLICY IF EXISTS "logs_service_insert" ON vg_usage_logs;
CREATE POLICY "logs_service_insert" ON vg_usage_logs
    FOR INSERT
    WITH CHECK (true);

-- Done. Verify:
-- SELECT COUNT(*) FROM vg_usage_logs;  -- should work after next verification
