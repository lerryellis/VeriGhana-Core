-- ── App Feedback ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_feedback (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at            TIMESTAMPTZ   DEFAULT NOW(),
  user_id               UUID          REFERENCES auth.users(id) ON DELETE SET NULL,
  user_email            TEXT,
  user_tier             TEXT,

  -- About the respondent
  respondent_role       TEXT,          -- 'researcher' | 'journalist' | 'student' | 'developer' | 'educator' | 'general'
  use_frequency         TEXT,          -- 'daily' | 'weekly' | 'monthly' | 'occasionally' | 'first_time'
  use_case              TEXT,

  -- NPS (0–10)
  nps_score             INTEGER        CHECK (nps_score BETWEEN 0 AND 10),

  -- Star ratings (1–5)
  rating_accuracy       INTEGER        CHECK (rating_accuracy BETWEEN 1 AND 5),
  rating_usability      INTEGER        CHECK (rating_usability BETWEEN 1 AND 5),
  rating_speed          INTEGER        CHECK (rating_speed BETWEEN 1 AND 5),
  rating_reliability    INTEGER        CHECK (rating_reliability BETWEEN 1 AND 5),
  rating_value          INTEGER        CHECK (rating_value BETWEEN 1 AND 5),

  -- Likert agreement (1=Strongly Disagree … 5=Strongly Agree)
  likert_easy_to_use    INTEGER        CHECK (likert_easy_to_use BETWEEN 1 AND 5),
  likert_trust_results  INTEGER        CHECK (likert_trust_results BETWEEN 1 AND 5),
  likert_improves_work  INTEGER        CHECK (likert_improves_work BETWEEN 1 AND 5),
  likert_recommend      INTEGER        CHECK (likert_recommend BETWEEN 1 AND 5),

  -- Open-ended qualitative
  most_useful           TEXT,
  biggest_challenge     TEXT,
  feature_request       TEXT,
  general_comments      TEXT
);

-- ── Staff ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS staff (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at            TIMESTAMPTZ   DEFAULT NOW(),
  updated_at            TIMESTAMPTZ   DEFAULT NOW(),
  full_name             TEXT          NOT NULL,
  email                 TEXT          UNIQUE NOT NULL,
  role                  TEXT          NOT NULL,   -- 'developer' | 'researcher' | 'support' | 'admin' | 'contractor'
  department            TEXT,
  employment_type       TEXT          DEFAULT 'full_time',  -- 'full_time' | 'part_time' | 'contract'
  start_date            DATE,
  end_date              DATE,
  gross_salary_ghs      NUMERIC(12,2) NOT NULL DEFAULT 0,
  status                TEXT          DEFAULT 'active',    -- 'active' | 'inactive' | 'terminated'
  notes                 TEXT
);

-- ── Payroll Runs ──────────────────────────────────────────────────────────────
-- One record per month processed
CREATE TABLE IF NOT EXISTS payroll_runs (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at            TIMESTAMPTZ   DEFAULT NOW(),
  period_year           INTEGER       NOT NULL,
  period_month          INTEGER       NOT NULL CHECK (period_month BETWEEN 1 AND 12),
  status                TEXT          DEFAULT 'draft',    -- 'draft' | 'approved' | 'paid'
  total_gross_ghs       NUMERIC(12,2) DEFAULT 0,
  total_paye_ghs        NUMERIC(12,2) DEFAULT 0,
  total_ssf_employee_ghs NUMERIC(12,2) DEFAULT 0,
  total_ssf_employer_ghs NUMERIC(12,2) DEFAULT 0,
  total_net_ghs         NUMERIC(12,2) DEFAULT 0,
  notes                 TEXT,
  UNIQUE (period_year, period_month)
);

-- ── Payroll Entries ───────────────────────────────────────────────────────────
-- One row per staff member per payroll run
CREATE TABLE IF NOT EXISTS payroll_entries (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  payroll_run_id        UUID          REFERENCES payroll_runs(id) ON DELETE CASCADE,
  staff_id              UUID          REFERENCES staff(id) ON DELETE CASCADE,
  gross_salary_ghs      NUMERIC(12,2) NOT NULL,
  paye_tax_ghs          NUMERIC(12,2) NOT NULL DEFAULT 0,
  ssf_employee_ghs      NUMERIC(12,2) NOT NULL DEFAULT 0,  -- 5.5% employee contribution
  ssf_employer_ghs      NUMERIC(12,2) NOT NULL DEFAULT 0,  -- 13%  employer contribution
  net_salary_ghs        NUMERIC(12,2) NOT NULL DEFAULT 0,
  UNIQUE (payroll_run_id, staff_id)
);
