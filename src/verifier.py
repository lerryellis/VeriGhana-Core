"""
VeriGhana Verifier — multi-provider AI cascade
================================================
Provider order: Gemini → Groq → Cohere → OpenRouter → Heuristic

HTTP backend: `requests` (fixes urllib latin-1 encoding bug).
Gemini: requires  pip install google-generativeai
Groq  : uses requests directly (no groq package needed).
"""

import os, re, time, json, logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Try importing requests (should always be available with Streamlit) ──
try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False
    logger.warning("requests not installed — HTTP providers will be skipped")


# ──────────────────────────────────────────────────────────────────────────────
#  MODEL REGISTRY
# ──────────────────────────────────────────────────────────────────────────────
FREE_MODELS: dict[str, str] = {
    "Gemini 2.0 Flash":         "gemini-2.0-flash",
    "Gemini 2.0 Flash Lite":    "gemini-2.0-flash-lite",
    "Gemini 1.5 Flash":         "gemini-1.5-flash",
    "Gemini 1.5 Flash 8B":      "gemini-1.5-flash-8b",
    "Groq Llama 3.3 70B":       "groq:llama-3.3-70b-versatile",
    "Groq Llama 3.1 8B Fast":   "groq:llama-3.1-8b-instant",
    "Cohere Command-R+":        "cohere:command-r-plus",
    "Cohere Command-R":         "cohere:command-r",
    "OpenRouter Llama 3.3 70B": "openrouter:llama-3.3-70b",
}

DEFAULT_MODEL = "gemini-2.0-flash"

_GEMINI_CASCADE     = ["gemini-2.0-flash", "gemini-2.0-flash-lite",
                        "gemini-1.5-flash", "gemini-1.5-flash-8b"]
_GROQ_CASCADE       = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
_COHERE_CASCADE     = ["command-r-plus", "command-r"]
_OPENROUTER_CASCADE = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-7b-instruct:free",
]


# ──────────────────────────────────────────────────────────────────────────────
#  SHARED UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def _is_quota(exc) -> bool:
    msg = str(exc).lower()
    return any(t in msg for t in (
        "429", "quota", "rate limit", "rate_limit", "resource_exhausted",
        "too many requests", "overloaded", "tokens per",
    ))

def _safe_key(raw: str) -> str:
    """Strip any non-ASCII characters that would break HTTP headers."""
    return raw.encode("ascii", errors="ignore").decode("ascii").strip()

def _parse_json(text: str) -> Optional[dict]:
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None

def _sources_text(sources: list, max_chars: int = 4000) -> str:
    parts = []
    for i, s in enumerate(sources[:10], 1):
        title    = s.get("title", "Untitled")
        src      = s.get("source_name", s.get("source", "Unknown"))
        category = s.get("category", "")
        content  = (s.get("content") or s.get("snippet") or "")[:400]
        date     = s.get("published_date", "")
        ds       = f" ({date[:10]})" if date else ""
        cat_tag  = f" [{category}]" if category else ""
        parts.append(f"[{i}] {src}{cat_tag}{ds} — {title}\n    {content}")
        if sum(len(p) for p in parts) > max_chars:
            break
    return "\n\n".join(parts) if parts else "(no matching sources found in database)"

_PROMPT = """You are VeriGhana, an AI fact-checker for Ghana. Analyse the claim against the provided source excerpts from multiple independent sources.

CLAIM:
{claim}

SOURCE EXCERPTS ({count} sources across {source_count} outlets):
{sources_text}

INSTRUCTIONS:
- Treat each source independently — do not assume they agree
- Note where sources corroborate each other AND where they differ or are silent
- A claim is VERIFIED only if multiple independent sources confirm it
- A claim is PARTIAL if some sources confirm part of it or sources conflict
- A claim is FALSE if sources directly contradict it
- A claim is UNCORROBORATED if no source addresses it (not necessarily false)

Return ONLY valid JSON - no markdown, no code fences, nothing else:
{{
  "verdict": "VERIFIED or PARTIAL or FALSE or UNCORROBORATED",
  "score": <integer 0-100>,
  "explanation": "<2-3 sentence plain-language verdict. Cite specific sources by name.>",
  "summary": "<3-4 sentence synthesis. Describe what each major source says, note agreements and disagreements between sources.>",
  "source_notes": [
    {{"source": "<source_name>", "category": "<Media|Government|Finance|Health|etc>", "stance": "<what this specific source says about the claim in 1 sentence>"}}
  ]
}}

Scoring: 85-100=confirmed by multiple independent sources, 65-84=mostly confirmed, 45-64=partially confirmed or conflicting sources, 20-44=weakly supported, 0-19=not supported or contradicted.
UNCORROBORATED means no relevant sources found, not necessarily false."""


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 1 — GEMINI
# ──────────────────────────────────────────────────────────────────────────────

def _get_genai():
    try:
        import google.generativeai as genai
        key = _safe_key(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", ""))
        if key:
            genai.configure(api_key=key)
            return genai
        logger.warning("Gemini: GOOGLE_API_KEY not set in .env")
    except ImportError:
        logger.warning(
            "Gemini: google-generativeai not installed. "
            "Run: pip install google-generativeai"
        )
    return None


def _call_gemini(prompt: str, preferred: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    key = _safe_key(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", ""))
    if not key:
        return None, preferred

    genai = _get_genai()
    if genai is None:
        return None, preferred

    cascade = [preferred] + [m for m in _GEMINI_CASCADE if m != preferred]
    cfg = {"max_output_tokens": max_tokens, "temperature": 0.2}

    for mid in cascade:
        mdl = genai.GenerativeModel(mid)
        for attempt in range(3):
            try:
                text = mdl.generate_content(prompt, generation_config=cfg).text
                if text:
                    return text, mid
                break
            except Exception as exc:
                if _is_quota(exc):
                    if attempt < 2:
                        time.sleep(4 ** attempt)
                    else:
                        logger.info("Gemini quota on %s - next", mid)
                        break
                else:
                    logger.warning("Gemini error on %s: %s", mid, exc)
                    break

    return None, preferred


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 2 — GROQ  (via requests — no groq package needed)
# ──────────────────────────────────────────────────────────────────────────────

def _call_groq(prompt: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    if not _REQUESTS_OK:
        return None, "groq-unavailable"

    key = _safe_key(os.getenv("GROQ_API_KEY", ""))
    if not key:
        return None, "groq-unavailable"

    url     = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }

    for mid in _GROQ_CASCADE:
        payload = {
            "model":   mid,
            "messages": [
                {
                    "role":    "system",
                    "content": (
                        "You are VeriGhana, a Ghana fact-checking AI. "
                        "Return ONLY valid JSON - no markdown, no extra text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens":     max_tokens,
            "temperature":    0.1,
            "response_format": {"type": "json_object"},
        }
        for attempt in range(2):
            try:
                resp = _requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 429 or "rate" in resp.text.lower():
                    if attempt == 0:
                        time.sleep(3)
                        continue
                    logger.info("Groq quota on %s - next", mid)
                    break
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
                if text:
                    return text, f"groq:{mid}"
                break
            except Exception as exc:
                if _is_quota(exc):
                    if attempt == 0:
                        time.sleep(3)
                        continue
                    break
                logger.warning("Groq error on %s: %s", mid, exc)
                break

    return None, "groq-exhausted"


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 3 — COHERE  (via requests)
# ──────────────────────────────────────────────────────────────────────────────

def _call_cohere(prompt: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    if not _REQUESTS_OK:
        return None, "cohere-unavailable"

    key = _safe_key(os.getenv("COHERE_API_KEY", ""))
    if not key:
        return None, "cohere-unavailable"

    url     = "https://api.cohere.com/v2/chat"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    for mid in _COHERE_CASCADE:
        payload = {
            "model":    mid,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
        try:
            resp = _requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                logger.info("Cohere quota on %s - next", mid)
                continue
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("message", {})
                        .get("content", [{}])[0]
                        .get("text", ""))
            if not text:
                text = data.get("text", "")
            if text:
                return text, f"cohere:{mid}"
        except Exception as exc:
            if _is_quota(exc):
                logger.info("Cohere quota on %s - next", mid)
                continue
            logger.warning("Cohere error on %s: %s", mid, exc)
            break

    return None, "cohere-exhausted"


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 4 — OPENROUTER  (via requests)
# ──────────────────────────────────────────────────────────────────────────────

def _call_openrouter(prompt: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    if not _REQUESTS_OK:
        return None, "openrouter-unavailable"

    key = _safe_key(os.getenv("OPENROUTER_API_KEY", ""))
    if not key:
        return None, "openrouter-unavailable"

    url     = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://verighana.gh",
        "X-Title":       "VeriGhana",
    }

    for mid in _OPENROUTER_CASCADE:
        payload = {
            "model":       mid,
            "messages":    [{"role": "user", "content": prompt}],
            "max_tokens":  max_tokens,
            "temperature": 0.1,
        }
        try:
            resp = _requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code in (429, 402):
                logger.info("OpenRouter quota on %s - next", mid)
                continue
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            if text:
                label = mid.split("/")[-1].split(":")[0]
                return text, f"openrouter:{label}"
        except Exception as exc:
            if _is_quota(exc):
                logger.info("OpenRouter quota on %s - next", mid)
                continue
            logger.warning("OpenRouter error on %s: %s", mid, exc)
            break

    return None, "openrouter-exhausted"


# ──────────────────────────────────────────────────────────────────────────────
#  MASTER CALLER
# ──────────────────────────────────────────────────────────────────────────────

def _run_ai_analysis(claim: str, sources: list, preferred_model: str) -> tuple[Optional[dict], str]:
    if preferred_model in FREE_MODELS:
        preferred_model = FREE_MODELS[preferred_model]

    gemini_pref = preferred_model if not any(
        preferred_model.startswith(p) for p in ("groq:", "cohere:", "openrouter:")
    ) else _GEMINI_CASCADE[0]

    distinct_outlets = len({s.get("source_name", s.get("source", "?")) for s in sources})
    prompt = _PROMPT.format(
        claim=claim,
        count=len(sources),
        source_count=distinct_outlets,
        sources_text=_sources_text(sources),
    )

    for caller in [
        lambda p: _call_gemini(p, gemini_pref),
        _call_groq,
        _call_cohere,
        _call_openrouter,
    ]:
        text, used = caller(prompt)
        if text:
            parsed = _parse_json(text)
            if parsed and isinstance(parsed.get("score"), (int, float)):
                return parsed, used

    return None, "all-providers-exhausted"


# ──────────────────────────────────────────────────────────────────────────────
#  DATABASE HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _get_supabase():
    try:
        from database_utils import get_supabase_client
        return get_supabase_client()
    except Exception:
        try:
            from supabase import create_client
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
            if url and key:
                return create_client(url, key)
        except Exception:
            pass
    return None


def _keyword_search(claim: str, limit: int = 8) -> list:
    """
    Multi-strategy keyword search.
    1. Detects actual column names in fact_entries (never assumes)
    2. ilike on every text column for each word in claim
    3. Falls back to most recent rows so AI always has something to work with
    """
    supabase = _get_supabase()
    if supabase is None:
        logger.error("_keyword_search: no supabase client")
        return []

    # --- Probe actual columns once ---
    actual_cols: list[str] = []
    try:
        probe = supabase.table("fact_entries").select("*").limit(1).execute()
        if probe.data:
            actual_cols = list(probe.data[0].keys())
            logger.debug("fact_entries columns: %s", actual_cols)
        else:
            logger.warning("fact_entries probe returned 0 rows")
    except Exception as e:
        logger.error("Column probe failed: %s", e)

    # Text columns we will search, in priority order
    text_cols = [c for c in ["title", "content", "headline", "body", "text", "description"]
                 if c in actual_cols] or ["title", "content"]   # fallback guess

    # Order column for recency fallback
    order_col = next((c for c in ["published_date", "created_at", "date", "id"]
                      if c in actual_cols), None)

    # --- Extract words (no heavy stopword filter — trust ilike to be fast enough) ---
    words = sorted(
        set(w.lower() for w in re.findall(r"[a-zA-Z]{3,}", claim)
            if w.lower() not in {"the", "and", "for", "are", "but", "not", "you",
                                  "all", "any", "can", "was", "one", "our", "out",
                                  "get", "has", "how", "its", "let", "may", "see",
                                  "who", "did", "into", "that", "this", "with",
                                  "from", "they", "been", "have", "more", "will",
                                  "were", "said", "each", "which", "their"}),
        key=len, reverse=True
    )

    if not words:
        # No usable words — skip straight to recency fallback
        logger.warning("_keyword_search: no usable words extracted from claim: %r", claim[:80])
        words = []

    # Collect a large candidate pool (3x limit) before diversity filtering
    candidate_pool: list[dict] = []
    seen_ids: set = set()
    pool_target = limit * 3

    def _add(rows):
        for row in (rows or []):
            rid = row.get("id")
            if rid not in seen_ids:
                seen_ids.add(rid)
                candidate_pool.append({
                    "id":             rid,
                    "title":          row.get("title") or row.get("headline") or row.get("body", "")[:80],
                    "content":        row.get("content") or row.get("body") or row.get("text", ""),
                    "url_link":       row.get("url_link") or row.get("url", "#"),
                    "source_name":    row.get("source_name") or row.get("source", "Unknown"),
                    "published_date": row.get("published_date") or row.get("created_at", ""),
                })

    # --- Strategy 1: search top keywords across all text columns, collect all hits ---
    for word in words[:8]:
        if len(candidate_pool) >= pool_target:
            break
        for col in text_cols[:2]:
            try:
                r = (supabase.table("fact_entries")
                             .select("*")
                             .ilike(col, f"%{word}%")
                             .limit(pool_target)
                             .execute())
                if r.data:
                    _add(r.data)
                    logger.debug("ilike %s LIKE %%%s%% -> %d hits", col, word, len(r.data))
            except Exception as e:
                logger.warning("ilike %s/%s failed: %s", col, word, e)

    # --- Strategy 2: recent rows as additional context if pool is thin ---
    if len(candidate_pool) < limit:
        try:
            q = supabase.table("fact_entries").select("*")
            if order_col:
                q = q.order(order_col, desc=True)
            r = q.limit(pool_target).execute()
            _add(r.data)
            logger.debug("recency fallback added %d rows", len(r.data or []))
        except Exception as e:
            logger.error("recency fallback failed: %s — order_col=%s actual_cols=%s",
                         e, order_col, actual_cols)

    if not candidate_pool:
        logger.error("_keyword_search returned 0 results for: %r  cols=%s  words=%s",
                     claim[:80], actual_cols, words)

    return candidate_pool


def _vector_search(claim: str, model_id: str, limit: int = 6) -> list:
    genai    = _get_genai()
    supabase = _get_supabase()
    if genai is None or supabase is None:
        return []
    try:
        emb = genai.embed_content(
            model="models/text-embedding-004",
            content=claim,
            task_type="retrieval_query",
        )["embedding"]
    except Exception as exc:
        logger.warning("Embedding failed: %s", exc)
        return []

    for fn, kwargs in [
        ("match_fact_entries", {"query_embedding": emb, "match_count": limit, "match_threshold": 0.50}),
        ("search_facts",       {"query_embedding": emb, "limit_count": limit}),
    ]:
        try:
            r = supabase.rpc(fn, kwargs).execute()
            if r.data:
                return r.data
        except Exception:
            continue
    return []


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 5 — HEURISTIC  (never fails)
# ──────────────────────────────────────────────────────────────────────────────

def _overlap_score(claim: str, sources: list) -> int:
    if not sources:
        return 5
    cw = set(re.findall(r"\b[a-zA-Z]{3,}\b", claim.lower()))
    best = 0.0
    for s in sources:
        txt = f"{s.get('title','')} {s.get('content','')[:500]}".lower()
        sw  = set(re.findall(r"\b[a-zA-Z]{3,}\b", txt))
        if sw:
            best = max(best, len(cw & sw) / max(len(cw), 1))
    if best >= 0.65: return int(70 + best * 25)
    if best >= 0.40: return int(45 + best * 50)
    if best >= 0.20: return int(20 + best * 80)
    return max(5, int(best * 100))

def _h_verdict(score: int) -> str:
    if score >= 70: return "VERIFIED"
    if score >= 45: return "PARTIAL"
    return "UNCORROBORATED"


# ──────────────────────────────────────────────────────────────────────────────
#  SOURCE DIVERSITY & CATEGORY ENRICHMENT
# ──────────────────────────────────────────────────────────────────────────────

def _diversify_sources(sources: list, max_per_source: int = 2, total: int = 10) -> list:
    """
    From a candidate pool, pick up to `max_per_source` articles per outlet,
    spreading results across as many different sources as possible.
    Returns at most `total` results.
    """
    from collections import defaultdict
    buckets: dict[str, list] = defaultdict(list)
    for s in sources:
        name = s.get("source_name", s.get("source", "Unknown"))
        buckets[name].append(s)

    diverse: list[dict] = []
    round_idx = 0
    while len(diverse) < total:
        added_this_round = 0
        for name, items in buckets.items():
            if round_idx < len(items) and round_idx < max_per_source:
                diverse.append(items[round_idx])
                added_this_round += 1
                if len(diverse) >= total:
                    break
        if added_this_round == 0:
            break
        round_idx += 1

    return diverse[:total]


def _enrich_with_categories(sources: list) -> list:
    """
    Look up the category for each source from the trusted_sources table
    and add it to the source dict.
    """
    supabase = _get_supabase()
    if not supabase or not sources:
        return sources

    names = list({s.get("source_name", s.get("source", "")) for s in sources if s.get("source_name") or s.get("source")})
    if not names:
        return sources

    try:
        rows = (supabase.table("trusted_sources")
                        .select("source_name,category")
                        .in_("source_name", names)
                        .execute()
                        .data or [])
        cat_map = {r["source_name"]: r.get("category", "") for r in rows}
    except Exception as e:
        logger.warning("Category enrichment failed: %s", e)
        return sources

    for s in sources:
        name = s.get("source_name", s.get("source", ""))
        if name in cat_map:
            s["category"] = cat_map[name]

    return sources


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def verify_claim(claim: str, model: str = DEFAULT_MODEL,
                 model_id: Optional[str] = None) -> dict:
    start = time.time()
    eff   = model_id or model or DEFAULT_MODEL

    # ── Hybrid retrieval: combine vector + keyword, then diversify ────────────
    vector_results  = _vector_search(claim, eff, limit=12)
    keyword_results = _keyword_search(claim, limit=24)

    # Merge — vector results first (higher precision), then keyword fills gaps
    seen_ids: set = set()
    combined: list[dict] = []
    for s in vector_results + keyword_results:
        rid = s.get("id")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            combined.append(s)

    if vector_results and keyword_results:
        search_method = "hybrid"
    elif vector_results:
        search_method = "vector"
    else:
        search_method = "keyword"

    # Enforce source diversity: max 2 articles per outlet, up to 10 total
    sources = _diversify_sources(combined, max_per_source=2, total=10)

    # Enrich with category from trusted_sources table
    sources = _enrich_with_categories(sources)

    # AI analysis
    ai, used = _run_ai_analysis(claim, sources, eff)

    if ai and isinstance(ai.get("score"), (int, float)):
        score        = max(0, min(100, int(ai["score"])))
        verdict      = ai.get("verdict", "UNCORROBORATED").upper()
        explanation  = ai.get("explanation", "No explanation returned.")
        summary      = ai.get("summary", explanation)
        source_notes = ai.get("source_notes", [])
        if verdict not in ("VERIFIED", "PARTIAL", "FALSE", "UNCORROBORATED"):
            verdict = "UNCORROBORATED"
        if not sources and score > 15:
            score = max(5, score // 4)
            verdict = "UNCORROBORATED"
        if   "groq:"        in used: provider = "Groq"
        elif "cohere:"      in used: provider = "Cohere"
        elif "openrouter:"  in used: provider = "OpenRouter"
        else:                        provider = "Gemini"
    else:
        score        = _overlap_score(claim, sources)
        verdict      = _h_verdict(score)
        explanation  = (
            "All AI providers unavailable right now. "
            "Score estimated from keyword overlap with database records."
        )
        summary = (
            f"Found {len(sources)} related source(s) in the database. "
            "AI summarisation temporarily unavailable — all providers quota-limited. "
            "Please try again shortly."
        ) if sources else (
            "No matching records found and all AI providers are currently unavailable."
        )
        source_notes = []
        used         = "heuristic"
        provider     = "Heuristic"
        search_method = search_method + "+heuristic"

    stance_map = {
        n.get("source", "").lower(): n.get("stance", "")
        for n in source_notes
    }
    fmt_sources = []
    for s in sources:
        nm = s.get("source_name", s.get("source", "Unknown"))
        fmt_sources.append({
            "title":          s.get("title", "Untitled"),
            "url_link":       s.get("url_link", s.get("url", "#")),
            "url":            s.get("url_link", s.get("url", "#")),
            "source_name":    nm,
            "source":         nm,
            "category":       s.get("category", ""),
            "published_date": s.get("published_date", ""),
            "stance":         s.get("stance", "") or stance_map.get(nm.lower(), ""),
        })

    # Group sources by category for structured display
    categories: dict[str, list] = {}
    for s in fmt_sources:
        cat = s.get("category") or "Other"
        categories.setdefault(cat, []).append(s.get("source_name", ""))

    return {
        "verdict":       verdict,
        "score":         score,
        "explanation":   explanation,
        "summary":       summary,
        "sources":       fmt_sources,
        "source_notes":  source_notes,
        "categories":    categories,
        "model_used":    used,
        "provider":      provider,
        "search_method": search_method,
        "processing_ms": int((time.time() - start) * 1000),
    }