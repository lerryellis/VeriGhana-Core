-- ============================================================================
-- Extend verification_log with accuracy-evaluation columns for thesis §5.2.
--
-- Adds:
--   category           — admin-set ground-truth bucket (known_true | known_false | no_coverage)
--   expected_verdict   — admin-set ideal verdict (VERIFIED | PARTIAL | FALSE | UNCORROBORATED)
--   response_time_ms   — end-to-end latency, populated at log-write time
--   sources_retrieved  — count of sources returned by retrieval engine
--
-- The existing columns map to the §5.2 spec as follows:
--   input_claim   → claim_text
--   verdict       → returned_verdict
--   score         → score
--   model_used    → provider_used
--
-- 'correct' is computed by the application (see admin Reports → Verifications)
-- because the rule is category-driven (known-true matches VERIFIED or PARTIAL,
-- known-false matches FALSE or PARTIAL, no-coverage matches UNCORROBORATED).
-- ============================================================================

ALTER TABLE verification_log
  ADD COLUMN IF NOT EXISTS category           TEXT,
  ADD COLUMN IF NOT EXISTS expected_verdict   TEXT,
  ADD COLUMN IF NOT EXISTS response_time_ms   INTEGER,
  ADD COLUMN IF NOT EXISTS sources_retrieved  INTEGER;

-- Constraints (PostgreSQL doesn't have idempotent ADD CONSTRAINT, so wrap in DO block)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.check_constraints
    WHERE constraint_name = 'verification_log_category_check'
  ) THEN
    ALTER TABLE verification_log
      ADD CONSTRAINT verification_log_category_check
      CHECK (category IS NULL OR category IN ('known_true','known_false','no_coverage'));
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.check_constraints
    WHERE constraint_name = 'verification_log_expected_verdict_check'
  ) THEN
    ALTER TABLE verification_log
      ADD CONSTRAINT verification_log_expected_verdict_check
      CHECK (expected_verdict IS NULL OR expected_verdict IN ('VERIFIED','PARTIAL','FALSE','UNCORROBORATED'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_verification_log_created
  ON verification_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_verification_log_tagged
  ON verification_log (category)
  WHERE category IS NOT NULL;
