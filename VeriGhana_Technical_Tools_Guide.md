# VeriGhana — Technical Tools & Technologies Guide

**Version:** 1.0
**Date:** March 2026
**Project:** VeriGhana — Ghana's AI-Powered Fact-Checking Platform

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Backend Tools (Python)](#3-backend-tools-python)
4. [Frontend Tools (Next.js)](#4-frontend-tools-nextjs)
5. [Database & Authentication](#5-database--authentication)
6. [AI & Verification Engine](#6-ai--verification-engine)
7. [Scraping & Data Ingestion](#7-scraping--data-ingestion)
8. [Payments](#8-payments)
9. [Infrastructure & Deployment](#9-infrastructure--deployment)
10. [Automated Workflows](#10-automated-workflows)
11. [Summary Table](#11-summary-table)

---

## 1. Project Overview

VeriGhana is a fact-checking platform for Ghana. When a user submits a claim (e.g. "The government increased fuel taxes by 30%"), the platform:

1. Searches its database of articles scraped from trusted Ghanaian news and government sources.
2. Passes the claim and matching articles to multiple AI models.
3. Returns a verdict — **VERIFIED**, **PARTIAL**, **FALSE**, or **UNCORROBORATED** — with a confidence score and source citations.

The platform has three user tiers: **Free** (5 verifications/day), **Pro** ($9.99/month), and **Institutional** ($79.99/month, bulk verification of up to 20 claims at once).

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                         │
│              Next.js 16 Web App (verighana-web/)            │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS API calls
┌────────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend (src/api.py)               │
│        Authentication · Rate Limiting · AI Cascade           │
└──────────┬────────────────────────────────┬─────────────────┘
           │                                │
┌──────────▼──────────┐        ┌────────────▼────────────────┐
│  Supabase Database  │        │     AI Providers            │
│  PostgreSQL+pgvector│        │  Gemini · Groq · Cohere     │
│  Auth · RLS · Storage│       │  OpenRouter · Heuristic     │
└──────────▲──────────┘        └─────────────────────────────┘
           │
┌──────────┴──────────────────────────────────────────────────┐
│              Automated Scraper (GitHub Actions, every 6h)    │
│    RSS Scraper · HTML Scraper · Embedder (pgvector)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Tools (Python)

### FastAPI
**What it is:** A modern Python web framework for building APIs.
**What it does in VeriGhana:** FastAPI is the core of the backend (`src/api.py`). It handles every HTTP request — user authentication, claim verification, payment processing, admin operations, and triggering scrapers. It is chosen because it is fast, supports async operations (multiple AI calls at once), and auto-generates API documentation.
**Key endpoints:**
- `POST /verify` — accepts a claim from a logged-in user, runs the full AI verification pipeline, and returns a verdict
- `POST /payment/verify` — confirms a Paystack payment and upgrades the user's subscription tier
- `GET /admin/users` — returns a paginated list of all users for the admin dashboard

### Uvicorn
**What it is:** An ASGI (Asynchronous Server Gateway Interface) server that runs FastAPI.
**What it does in VeriGhana:** Uvicorn is the process that actually listens on a port and hands HTTP requests to FastAPI. In development: `uvicorn src.api:app --reload --port 8000`. In production on Railway: `uvicorn src.api:app --host 0.0.0.0 --port $PORT`.

### PyJWT
**What it is:** A Python library for creating and verifying JSON Web Tokens (JWTs).
**What it does in VeriGhana:** Every request to a protected endpoint includes a JWT issued by Supabase when the user logs in. PyJWT decodes and verifies that token to confirm who the user is and whether their session is still valid.

### python-dotenv
**What it is:** A utility that reads a `.env` file and loads its values as environment variables.
**What it does in VeriGhana:** Allows the backend to store sensitive credentials (Supabase keys, Gemini API key, Paystack secret) in a `.env` file locally without hardcoding them in source code. On GitHub Actions and Railway, these variables are injected directly — `python-dotenv` is harmless in those environments.

### Requests / urllib3
**What it is:** Python HTTP client libraries.
**What it does in VeriGhana:** Used to make outbound HTTP calls — calling the Paystack API to verify a payment reference, calling AI provider APIs, and fetching web pages during scraping.

---

## 4. Frontend Tools (Next.js)

### Next.js 16
**What it is:** A React framework that supports both server-side rendering and client-side interactivity.
**What it does in VeriGhana:** Powers the entire web application at `verighana-web/`. Next.js handles routing (each folder under `app/` is a URL route), renders pages on the server for fast load times and SEO, and provides server components that can securely fetch data from the backend without exposing API keys to the browser.

### React 19
**What it is:** The JavaScript library for building user interfaces.
**What it does in VeriGhana:** All interactive parts of the UI — forms, state changes, tabs, buttons — are built as React components. React manages what the user sees and updates the page when data changes without a full reload.

### TypeScript
**What it is:** A typed superset of JavaScript that catches errors at compile time.
**What it does in VeriGhana:** All `.tsx` files are TypeScript. Type definitions (e.g. `AdminUser`, `PaymentRecord`, `SupportTicket`) ensure that if a backend response changes shape, the compiler flags it immediately rather than failing silently at runtime.

### Tailwind CSS 4
**What it is:** A utility-first CSS framework where styles are applied directly as class names.
**What it does in VeriGhana:** All visual styling — colours, spacing, typography, responsive layout — is applied through Tailwind class names directly in JSX. This makes components self-contained and eliminates separate CSS files.

### Recharts
**What it is:** A charting library built on React and SVG.
**What it does in VeriGhana:** Powers the Admin Sales Reports dashboard — daily revenue line charts, revenue-by-plan bar charts, and revenue-by-payment-method bar charts. Data is passed in as arrays and Recharts handles rendering, tooltips, and axes.

### @supabase/ssr
**What it is:** Supabase's official library for server-side rendering frameworks like Next.js.
**What it does in VeriGhana:** Manages the user's authentication session on both server components (for page-level access control like redirecting to `/login`) and client components (for live sign-out). It reads the session cookie from the browser and communicates securely with Supabase.

### Lucide React
**What it is:** An icon library with clean, consistent SVG icons.
**What it does in VeriGhana:** Provides icons used throughout the UI (check marks, alerts, arrows, etc.) as importable React components.

### shadcn / class-variance-authority / clsx / tailwind-merge
**What they are:** A UI component toolkit and utility libraries for managing Tailwind class names.
**What they do in VeriGhana:** These work together to build reusable, styled components (buttons, badges, cards) where the styles can vary based on props (e.g. a `TierChip` that looks different for Free vs Pro vs Institutional).

---

## 5. Database & Authentication

### Supabase
**What it is:** A hosted PostgreSQL database with built-in authentication, storage, and a REST API.
**What it does in VeriGhana:** Supabase is the single source of data for the entire platform. It stores:

| Table | Purpose |
|---|---|
| `fact_entries` | All scraped articles with their text and vector embeddings |
| `user_profiles` | User details — name, tier, organisation, daily query count |
| `vg_subscriptions` | Active subscription records |
| `vg_usage_logs` | Every verification request with its verdict and metadata |
| `payments` | Full payment history including Paystack references |
| `support_tickets` | User support tickets, admin replies, and follow-ups |
| `trusted_sources` | Registry of all news and government sources |

**Row Level Security (RLS):** Supabase enforces policies at the database level so that users can only read and write their own data. Admin operations bypass RLS using a service role key stored securely as an environment variable.

### pgvector
**What it is:** A PostgreSQL extension that adds a vector data type and similarity search.
**What it does in VeriGhana:** Each article in `fact_entries` has a `content_embedding` column — a 768-dimension vector that captures the semantic meaning of the article text. When a user submits a claim for verification, the claim is also converted to a vector, and pgvector finds the most semantically similar articles using cosine similarity. This is how the platform retrieves relevant source material even when the exact words don't match.

---

## 6. AI & Verification Engine

### Verification Flow (`src/verifier.py`)

When a claim is submitted, VeriGhana does not rely on a single AI model. It runs a **cascade**: if the first model fails or is unavailable, the next one is tried automatically. This ensures the platform stays online even when individual providers have downtime.

```
Claim submitted
      │
      ▼
pgvector similarity search → retrieve top matching articles
      │
      ▼
Build prompt (claim + article excerpts)
      │
      ▼
1. Gemini 2.0 Flash  ──► Success → return verdict
      │ Fail
      ▼
2. Gemini 1.5 Flash  ──► Success → return verdict
      │ Fail
      ▼
3. Groq (Llama 3)    ──► Success → return verdict
      │ Fail
      ▼
4. Cohere            ──► Success → return verdict
      │ Fail
      ▼
5. OpenRouter        ──► Success → return verdict
      │ Fail
      ▼
6. Heuristic fallback (keyword matching) → return verdict
```

Each provider returns the same structure: `{ verdict, score, explanation, summary, source_notes }` where:
- **verdict** — one of `VERIFIED`, `PARTIAL`, `FALSE`, `UNCORROBORATED`
- **score** — confidence percentage (0–100)
- **explanation** — detailed reasoning
- **summary** — one-sentence summary for display
- **source_notes** — which source articles were used

### Google Gemini (`google-genai`, `google-generativeai`)
**What it is:** Google's family of large language models.
**What it does in VeriGhana:** The primary verification model (Gemini 2.0 Flash) and the embedding model (`gemini-embedding-001`) used to convert article text into vectors. Two packages are installed: `google-generativeai` (older SDK used in some modules) and `google-genai` (newer SDK used in `embedder.py`).

### Groq (`groq`)
**What it is:** An API that serves open-source models (Llama 3) at very high speed using custom hardware.
**What it does in VeriGhana:** Second-tier fallback model in the verification cascade. Used when Gemini is unavailable.

### Cohere (`cohere`)
**What it is:** An NLP API specialising in text understanding and classification.
**What it does in VeriGhana:** Third-tier fallback in the verification cascade.

### OpenRouter
**What it is:** A unified API gateway that provides access to dozens of AI models from a single endpoint.
**What it does in VeriGhana:** Fourth-tier fallback. Accessed via standard HTTP requests (no dedicated SDK required).

---

## 7. Scraping & Data Ingestion

The scraping pipeline runs automatically every 6 hours via GitHub Actions and populates the `fact_entries` table.

### feedparser
**What it is:** A Python library for parsing RSS and Atom feeds.
**What it does in VeriGhana:** `src/scraper.py` uses feedparser to read the RSS feeds of trusted Ghanaian news outlets (Citi Newsroom, Joy Online, Pulse Ghana). It extracts article titles, summaries, publication dates, and source URLs, then saves each as a row in `fact_entries`.

### BeautifulSoup4 (`beautifulsoup4`)
**What it is:** A Python library for parsing HTML and XML documents.
**What it does in VeriGhana:** `src/scrapers/html_scraper.py` fetches raw HTML from 65+ Ghanaian news and government websites and uses BeautifulSoup to extract the article headline and body text from within the HTML structure. It tries multiple extraction strategies (headline tags, article containers, list items, document text) before falling back to Playwright.

### Playwright
**What it is:** A browser automation library that can launch a real Chromium browser and interact with web pages.
**What it does in VeriGhana:** Some websites render their content using JavaScript — the article text only appears after the page's scripts have run. When BeautifulSoup's static extraction strategies fail, the HTML scraper launches a headless Chromium browser via Playwright, waits for the page to fully render, and then extracts the content. This is the most powerful (and slowest) scraping strategy, used only as a last resort.

### google-genai (Embedder)
**What it does in the scraper pipeline:** After articles are scraped and saved, `src/embedder.py` fetches all articles that don't yet have an embedding, sends their text to Gemini's `gemini-embedding-001` model, and stores the resulting 768-dimension vector back into the `content_embedding` column. This is what makes semantic search possible during verification.

---

## 8. Payments

### Paystack
**What it is:** An African payment gateway that supports card payments and mobile money (MTN MoMo, Vodafone Cash, AirtelTigo).
**What it does in VeriGhana:** Handles all subscription payments on the billing page. When a user selects a plan:

1. **Frontend (BillingClient.tsx):** Loads the Paystack inline JavaScript popup. The popup collects card or mobile money details, processes the charge in GHS (Ghana Cedis), and returns a transaction reference on success.
2. **Backend (`POST /payment/verify`):** Receives the reference, calls Paystack's API to confirm the charge was genuine and successful, then upgrades the user's tier in `user_profiles`, creates a subscription record, and saves the payment to the `payments` table.

Prices are stored in USD and converted to GHS at a fixed rate of 15 GHS/USD for Paystack's required currency.

---

## 9. Infrastructure & Deployment

### Railway
**What it is:** A cloud platform for deploying backend services directly from a GitHub repository.
**What it does in VeriGhana:** Hosts the FastAPI backend in production. Railway watches the GitHub repository; when code is pushed to `main`, it automatically rebuilds and redeploys the backend. The `Procfile` tells Railway what command to run: `uvicorn src.api:app --host 0.0.0.0 --port $PORT`.

### Procfile
**What it is:** A single-line configuration file that tells the hosting platform how to start the application.
**What it does in VeriGhana:** Contains `web: uvicorn src.api:app --host 0.0.0.0 --port $PORT`. Railway reads this on deploy.

### railway.toml
**What it is:** Railway's project configuration file.
**What it does in VeriGhana:** Specifies the builder (nixpacks — automatic dependency detection) and restart-on-failure behaviour.

---

## 10. Automated Workflows

### GitHub Actions (`.github/workflows/automated_scraper.yml`)
**What it is:** GitHub's built-in CI/CD system that can run scripts on a schedule or on code pushes.
**What it does in VeriGhana:** Runs the full data ingestion pipeline automatically every 6 hours (00:00, 06:00, 12:00, 18:00 UTC) without any manual intervention. The workflow:

1. Checks out the repository code
2. Installs Python 3.12
3. Installs all Python dependencies from `requirements.txt`
4. Installs the Chromium browser for Playwright
5. Runs `src/scraper.py` — ingests RSS feeds
6. Runs `src/embedder.py` — generates and stores vector embeddings
7. Runs `src/scrapers/html_scraper.py` — scrapes 65+ HTML-based sources

Sensitive credentials (Supabase URL, Supabase Key, Gemini API Key) are stored as encrypted GitHub Secrets and injected as environment variables at runtime — they are never written in the workflow file.

---

## 11. Summary Table

| Tool | Category | Language/Type | Role in VeriGhana |
|---|---|---|---|
| FastAPI | Backend Framework | Python | API server — all endpoints |
| Uvicorn | ASGI Server | Python | Runs FastAPI in production |
| PyJWT | Authentication | Python | Validates user session tokens |
| python-dotenv | Configuration | Python | Loads `.env` credentials locally |
| Supabase | Database + Auth | Hosted PostgreSQL | All data storage, user accounts, RLS |
| pgvector | Search Extension | PostgreSQL | Semantic similarity search on articles |
| Next.js 16 | Frontend Framework | TypeScript/React | Web application and routing |
| React 19 | UI Library | JavaScript | Interactive user interface |
| TypeScript | Language | Compiled JS | Type safety across the frontend |
| Tailwind CSS 4 | Styling | CSS utilities | All visual design |
| Recharts | Charts | React/SVG | Admin sales and usage charts |
| @supabase/ssr | Auth Client | TypeScript | Session management in Next.js |
| Gemini 2.0 Flash | AI Model | API | Primary fact-checking model |
| Gemini Embedding | AI Model | API | Article and claim vectorisation |
| Groq (Llama 3) | AI Model | API | Fallback verification model |
| Cohere | AI Model | API | Fallback verification model |
| OpenRouter | AI Gateway | API | Final AI fallback |
| feedparser | RSS Scraper | Python | Parses trusted RSS news feeds |
| BeautifulSoup4 | HTML Parser | Python | Extracts content from web pages |
| Playwright | Browser Automation | Python | Scrapes JavaScript-rendered pages |
| Paystack | Payments | API + JS SDK | Card and mobile money subscriptions |
| Railway | Cloud Hosting | PaaS | Hosts and auto-deploys the backend |
| GitHub Actions | CI/CD | YAML | Runs the scraper pipeline every 6 hours |

---

*VeriGhana Technical Tools Guide — prepared March 2026*
