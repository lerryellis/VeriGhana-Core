# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python/FastAPI)
```bash
pip install -r requirements.txt
uvicorn src.api:app --reload --port 8000   # dev server
python src/scraper.py                       # run RSS scraper manually
python src/embedder.py                      # run embedder manually
python src/scrapers/html_scraper.py         # run HTML scraper manually
```

### Streamlit App
```bash
streamlit run src/app.py    # full-featured dashboard (localhost:8501)
```

### Frontend (Next.js — verighana_web/)
```bash
cd verighana_web && npm install
npm run dev     # localhost:3000
npm run build
npm run lint
```

### Playwright (for JS-rendered scraping)
```bash
playwright install chromium
```

## Architecture

VeriGhana-Core is a fact-checking platform for Ghana. It has three main layers:

**1. Ingestion Pipeline (GitHub Actions, every 6h)**
- `src/scraper.py` — parses 3 trusted RSS feeds into `fact_entries` table
- `src/scrapers/html_scraper.py` — scrapes 65+ Ghanaian news/gov sites using 6 strategy cascade (headline → container → list → document → anchor sweep → JS render via Playwright)
- `src/embedder.py` — generates Gemini embeddings for unprocessed articles, stores in `fact_entries.content_embedding` (pgvector)

**2. FastAPI Backend (`src/api.py`)**
- Auth: Supabase JWT verification; `SUPABASE_SERVICE_KEY` bypasses RLS for local dev
- `POST /verify` — main endpoint: rate-limit check → vector search `fact_entries` → multi-provider AI cascade → log to `vg_usage_logs`
- Admin routes protected by `X-Admin-Key` header
- Background tasks for scraper/embedder triggers

**3. Frontends**
- `index.html` — standalone static landing page (pure HTML/CSS/JS, no build step)
- `src/app.py` — full-featured Streamlit dashboard (239KB merged redesign); includes real Supabase auth, claim verification UI, site tester, admin stats, session persistence via cookies/localStorage
- `verighana_web/` — Next.js 16 + React 19 + Tailwind 4 (early stage)

### AI Verification (`src/verifier.py`)
Multi-provider cascade: **Gemini 2.0 Flash → Gemini 1.5 Flash → Groq (Llama) → Cohere → OpenRouter → heuristic fallback**

Returns `{ verdict, score (0-100), explanation, summary, source_notes }` where verdict is one of `VERIFIED | PARTIAL | FALSE | UNCORROBORATED`.

### Database (Supabase/PostgreSQL + pgvector)
Key tables: `fact_entries` (articles + embeddings), `vg_users`, `vg_subscriptions`, `vg_usage_logs`, `vg_api_keys`, `vg_seats` (institutional), `payments`, `support_tickets`.

Tiers: **Free** (5 verifications/day) → **Pro** ($9.99/mo) → **Institutional** ($79.99/mo, bulk verify up to 20 claims).

### Local Claude Code (`claude.json`)
Configured to use a local Ollama instance (`http://localhost:11434`) instead of Anthropic's API. Requires Ollama running locally with `ANTHROPIC_AUTH_TOKEN=ollama`.

### Deployment
- Production: Railway via `Procfile` (`uvicorn src.api:app --host 0.0.0.0 --port $PORT`)
- Config: `railway.toml` (nixpacks builder, restart on failure)

## Key Environment Variables
```
SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET
ADMIN_API_KEY, ADMIN_EMAIL
GEMINI_API_KEY
GROQ_API_KEY, COHERE_API_KEY, OPENROUTER_API_KEY   # optional fallbacks
RESEND_API_KEY                                       # email notifications
JWT_SECRET_KEY, JWT_REFRESH_SECRET
ALLOWED_ORIGINS                                      # CORS
```
