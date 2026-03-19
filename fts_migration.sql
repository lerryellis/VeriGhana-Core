-- Full-Text Search migration for fact_entries
-- Run in Supabase SQL Editor: Dashboard → SQL Editor → New Query
--
-- Safe to re-run: uses IF NOT EXISTS / CREATE OR REPLACE throughout.

-- ── 1. Add generated tsvector column ────────────────────────────────────────
-- Uses a DO block so we can skip gracefully if the column already exists.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_name = 'fact_entries' AND column_name = 'search_vector'
  ) THEN
    ALTER TABLE fact_entries
      ADD COLUMN search_vector tsvector
      GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title,   '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content, '')), 'B')
      ) STORED;
  END IF;
END;
$$;

-- ── 2. GIN index for fast FTS queries ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_fact_entries_fts
  ON fact_entries USING gin(search_vector);

-- ── 3. RPC function callable from Supabase client ───────────────────────────
-- Returns rows ranked by ts_rank_cd (cover density — rewards phrase proximity).
-- websearch_to_tsquery handles quoted phrases, minus-exclusion, AND/OR natively.
CREATE OR REPLACE FUNCTION search_fact_entries_fts(
  query       text,
  match_count int DEFAULT 24
)
RETURNS TABLE (
  id            bigint,
  title         text,
  content       text,
  url_link      text,
  source_name   text,
  published_date text,
  rank          real
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  SELECT
    fe.id::bigint,
    fe.title,
    fe.content,
    fe.url_link,
    fe.source_name,
    (fe.published_date)::text,
    ts_rank_cd(
      fe.search_vector,
      websearch_to_tsquery('english', query)
    )::real AS rank
  FROM fact_entries fe
  WHERE
    fe.search_vector @@ websearch_to_tsquery('english', query)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

-- ── 4. Grant execute to authenticated users (needed for client-side RPC) ────
GRANT EXECUTE ON FUNCTION search_fact_entries_fts(text, int) TO authenticated;
GRANT EXECUTE ON FUNCTION search_fact_entries_fts(text, int) TO anon;
