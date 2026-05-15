-- ============================================================================
-- Extend app_feedback with the qualitative research evaluation strand.
-- Adds an optional "research participation" mode: if a respondent opts in
-- (informed consent), they additionally answer the five DSR-aligned
-- open-ended questions, anchored in a real claim they verified on the live
-- system. Quantitative fields (NPS, stars, Likert) remain unchanged.
-- ============================================================================

ALTER TABLE app_feedback
  ADD COLUMN IF NOT EXISTS research_consent       BOOLEAN     NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS research_consent_at    TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS research_claim_text    TEXT,
  ADD COLUMN IF NOT EXISTS research_verdict       TEXT,
  ADD COLUMN IF NOT EXISTS research_q1_confidence TEXT,
  ADD COLUMN IF NOT EXISTS research_q2_citations  TEXT,
  ADD COLUMN IF NOT EXISTS research_q3_barriers   TEXT,
  ADD COLUMN IF NOT EXISTS research_q4_surprises  TEXT,
  ADD COLUMN IF NOT EXISTS research_q5_comparison TEXT;

-- Filtering index for thematic analysis: pull only consenting responses.
CREATE INDEX IF NOT EXISTS idx_app_feedback_research_consent
  ON app_feedback (research_consent)
  WHERE research_consent = TRUE;
