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
        src      = _bucket_key(s)
        category = s.get("category", "")
        content  = (s.get("content") or s.get("snippet") or "")[:1000]
        date     = s.get("published_date", "")
        ds       = f" ({date[:10]})" if date else ""
        cat_tag  = f" [{category}]" if category else ""
        parts.append(f"[{i}] {src}{cat_tag}{ds} — {title}\n    {content}")
        if sum(len(p) for p in parts) > max_chars:
            break
    return "\n\n".join(parts) if parts else "(no matching sources found in database)"

_PROMPT = """You are VeriGhana, an AI fact-checker for Ghana using the Triangulation & Nuance Framework.

CLAIM:
{claim}

SOURCE EXCERPTS ({count} sources across {source_count} outlets):
{sources_text}

ANALYSIS STEPS — follow in order:
1. RELEVANCE FILTER: For each source, decide whether it directly addresses this specific claim
   (RELEVANT), covers a related topic without addressing the claim (TANGENTIAL), or is on
   a completely different topic (UNRELATED). Base your verdict and score ONLY on RELEVANT
   sources. Mention tangential sources in the explanation only if noteworthy.
2. CONVERGENCE: Identify facts that 2+ RELEVANT sources agree on — these carry the most weight.
3. VERDICT: Apply the rules below using only RELEVANT sources.

VERDICT RULES:
- VERIFIED: 2+ independent RELEVANT sources confirm the core claim
- PARTIAL: RELEVANT sources confirm only part of it, or RELEVANT sources conflict with each other
- FALSE: RELEVANT sources directly contradict the claim
- UNCORROBORATED: no RELEVANT source addresses the claim (not necessarily false)

TRIANGULATION RULES:
- Treat each source as an independent witness — never assume they agree
- convergence = facts at least 2 sources agree on (these are most reliable)
- narrative_delta = where sources describe the SAME event/fact but use different words,
  emphasis, framing, or omit details — this reveals editorial angle and potential bias
- bias_signals = specific indicators: loaded language, selective statistics, omission of
  key context, alarming vs dismissive tone, who/what the source centres or erases
- tone values: "neutral" | "positive" | "alarming" | "dismissive" | "critical" | "promotional"
- bias_type values: "word_choice" | "omission" | "emphasis" | "framing" | "selective_data" | "tone"
- triangulation_confidence: "high" = 3+ sources with clear convergence, "medium" = 2 sources
  or partial overlap, "low" = 1 source or no clear convergence

Return ONLY valid JSON - no markdown, no code fences, no trailing commas:
{{
  "verdict": "VERIFIED or PARTIAL or FALSE or UNCORROBORATED",
  "score": <integer 0-100>,
  "explanation": "<2-3 sentences citing specific source names for the verdict>",
  "summary": "<3-4 sentences: what each major source says, where they agree, where they differ>",
  "source_notes": [
    {{"source": "<name>", "category": "<Media|Government|Finance|Health|etc>", "stance": "<1 sentence on this source's position>"}}
  ],
  "convergence": [
    "<fact or detail confirmed by 2+ sources — be specific, quote or closely paraphrase>"
  ],
  "narrative_delta": [
    {{
      "aspect": "<the specific topic/sub-claim being compared>",
      "variations": [
        {{"source": "<name>", "framing": "<how this source describes it — quote key phrases>", "tone": "<tone value>"}}
      ],
      "delta_analysis": "<1-2 sentences: what the framing difference reveals about each source's angle, bias, or intent>"
    }}
  ],
  "bias_signals": [
    {{"source": "<name>", "signal": "<specific evidence — quote or describe the problematic phrase/omission>", "type": "<bias_type value>"}}
  ],
  "triangulation_confidence": "high or medium or low",
  "triangulation_note": "<1-2 sentences: overall reliability assessment given the source mix — consider category diversity (Media vs Government vs Finance) and whether sources have conflicting interests>"
}}

Scoring: 85-100=confirmed by 2+ independent sources, 65-84=mostly confirmed, 45-64=partial or conflicting, 20-44=weakly supported, 0-19=contradicted.
If only 1 source exists, narrative_delta and bias_signals should still reflect that single source's own internal framing choices."""


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

    max_tokens = 1800
    for caller in [
        lambda p: _call_gemini(p, gemini_pref, max_tokens),
        lambda p: _call_groq(p, max_tokens),
        lambda p: _call_cohere(p, max_tokens),
        lambda p: _call_openrouter(p, max_tokens),
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

    # Columns to search: title first, then content — both searched at every tier
    search_cols = text_cols[:2]

    # --- Strategy 0: PostgreSQL full-text search (highest accuracy, best ranking) ---
    # Falls back silently if the fts_migration.sql hasn't been run yet.
    if len(candidate_pool) < pool_target:
        try:
            r = supabase.rpc("search_fact_entries_fts", {
                "query": claim[:500],
                "match_count": pool_target,
            }).execute()
            if r.data:
                _add(r.data)
                logger.debug("FTS rpc -> %d hits", len(r.data))
        except Exception as e:
            logger.info("FTS rpc unavailable (run fts_migration.sql): %s", e)

    # --- Strategy 0b: entity-anchored AND search (proper nouns + acronyms) ---
    # Searches for the most distinctive named entities co-occurring in the same field.
    entities = _extract_entities(claim)
    if entities and len(candidate_pool) < pool_target:
        anchors = entities[:3]  # top 3 most specific entities
        for col in search_cols:
            if len(candidate_pool) >= pool_target:
                break
            try:
                q = supabase.table("fact_entries").select("*")
                for e in anchors[:2]:   # AND on top 2 to stay precise
                    q = q.ilike(col, f"%{e}%")
                r = q.limit(pool_target).execute()
                if r.data:
                    _add(r.data)
                    logger.debug("entity AND ilike %s %s -> %d hits", col, anchors[:2], len(r.data))
            except Exception as e:
                logger.warning("entity ilike %s failed: %s", col, e)

    # --- Strategy 1: exact phrase match on title + content (highest precision) ---
    phrase = claim[:150]
    for col in search_cols:
        if len(candidate_pool) >= pool_target:
            break
        try:
            r = (supabase.table("fact_entries")
                         .select("*")
                         .ilike(col, f"%{phrase}%")
                         .limit(pool_target)
                         .execute())
            if r.data:
                _add(r.data)
                logger.debug("phrase ilike %s -> %d hits", col, len(r.data))
        except Exception as e:
            logger.warning("phrase ilike %s failed: %s", col, e)

    # --- Strategy 2: multi-keyword AND search on title + content (strict context) ---
    # Require the top 3 most distinctive words to ALL appear in the same column.
    # Chaining multiple .ilike() calls on the same column applies AND logic in PostgREST.
    anchor_words = words[:3]
    if len(anchor_words) >= 2 and len(candidate_pool) < pool_target:
        for col in search_cols:
            if len(candidate_pool) >= pool_target:
                break
            try:
                q = supabase.table("fact_entries").select("*")
                for w in anchor_words:
                    q = q.ilike(col, f"%{w}%")
                r = q.limit(pool_target).execute()
                if r.data:
                    _add(r.data)
                    logger.debug("AND ilike %s %s -> %d hits", col, anchor_words, len(r.data))
            except Exception as e:
                logger.warning("AND ilike %s failed: %s", col, e)

    # --- Strategy 3: per-keyword search on title + content (broader fallback) ---
    for word in words[:6]:
        if len(candidate_pool) >= pool_target:
            break
        for col in search_cols:
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
        ("match_fact_entries", {"query_embedding": emb, "match_count": limit, "match_threshold": 0.65}),
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

def _bucket_key(s: dict) -> str:
    """Return a stable per-outlet key for diversity bucketing.
    Prefers source_name, falls back to URL domain so articles from
    different sites never all collapse into one 'Unknown' bucket."""
    name = s.get("source_name") or s.get("source") or ""
    if name and name != "Unknown":
        return name.lower()
    url = s.get("url_link") or s.get("url") or ""
    if url and url != "#":
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.removeprefix("www.")
            domain = host.split(".")[0]
            if domain:
                return domain.lower()
        except Exception:
            pass
    return f"unknown_{s.get('id', id(s))}"  # unique key per article as last resort


def _diversify_sources(sources: list, max_per_source: int = 2, total: int = 10) -> list:
    """
    From a candidate pool, pick up to `max_per_source` articles per outlet,
    spreading results across as many different sources as possible.
    Returns at most `total` results.
    """
    from collections import defaultdict
    buckets: dict[str, list] = defaultdict(list)
    for s in sources:
        buckets[_bucket_key(s)].append(s)

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
#  NAMED ENTITY EXTRACTION & NEAR-DUPLICATE DEDUPLICATION
# ──────────────────────────────────────────────────────────────────────────────

_GENERIC_CAPS = {
    'This', 'That', 'These', 'Those', 'The', 'There', 'Their',
    'What', 'When', 'Where', 'Which', 'Who', 'Whom', 'Whose', 'Why', 'How',
    'Some', 'Such', 'Each', 'Every', 'Both', 'Many', 'More', 'Most',
    'Also', 'Even', 'Just', 'Only', 'Very', 'Well', 'Still', 'Then',
    'Than', 'After', 'About', 'From', 'Into', 'Over', 'Under', 'Been',
    'Have', 'Were', 'Will', 'Would', 'Could', 'Should', 'Does', 'Said',
}

def _extract_entities(text: str) -> list[str]:
    """Extract named entities (proper nouns ≥4 chars, years) as high-precision search anchors.

    Returns lowercase strings, deduplicated, ordered by first appearance.
    """
    entities: list[str] = []
    # 4-digit years (19xx or 20xx)
    for year in re.findall(r'\b(19\d{2}|20\d{2})\b', text):
        entities.append(year)
    # Capitalized words ≥4 chars not in the generic list
    for w in re.findall(r'\b[A-Z][a-z]{3,}\b', text):
        if w not in _GENERIC_CAPS:
            entities.append(w.lower())
    # All-caps acronyms ≥2 chars (e.g. GES, NPP, NDC, ECG, COCOBOD)
    for w in re.findall(r'\b[A-Z]{2,}\b', text):
        entities.append(w.lower())

    seen: set[str] = set()
    result: list[str] = []
    for e in entities:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


def _deduplicate(sources: list, threshold: float = 0.70) -> list:
    """Remove near-duplicate articles (same wire story republished across outlets).

    Uses Jaccard similarity on title word sets. If two titles share ≥threshold
    fraction of their words, only the first-seen article is kept.
    Wire-story duplicates inflate AI confidence — deduplication ensures each
    independent outlet is counted as a distinct witness.
    """
    def _title_words(s: dict) -> frozenset[str]:
        t = (s.get("title") or "").lower()
        return frozenset(re.findall(r'[a-z]{3,}', t))

    deduped: list[dict] = []
    for s in sources:
        sw = _title_words(s)
        if not sw:
            deduped.append(s)
            continue
        is_dup = False
        for kept in deduped:
            kw = _title_words(kept)
            if not kw:
                continue
            jaccard = len(sw & kw) / max(len(sw | kw), 1)
            if jaccard >= threshold:
                is_dup = True
                break
        if not is_dup:
            deduped.append(s)
    return deduped


# ──────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def verify_claim(claim: str, model: str = DEFAULT_MODEL,
                 model_id: Optional[str] = None) -> dict:
    start = time.time()
    eff   = model_id or model or DEFAULT_MODEL

    # ── Hybrid retrieval: vector results protected, keyword fills remaining ────
    vector_results  = _vector_search(claim, eff, limit=12)
    keyword_results = _keyword_search(claim, limit=24)

    if vector_results and keyword_results:
        search_method = "hybrid"
    elif vector_results:
        search_method = "vector"
    else:
        search_method = "keyword"

    # Vector results are always included — cosine similarity already ranks
    # the exact/closest matches first and we never want diversity to drop them.
    seen_ids: set = set()
    priority: list[dict] = []
    for s in vector_results:
        rid = s.get("id")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            priority.append(s)

    # Keyword results fill remaining slots with source diversity applied
    keyword_pool: list[dict] = []
    for s in keyword_results:
        rid = s.get("id")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            keyword_pool.append(s)

    remaining = max(0, 10 - len(priority))
    sources = priority + _diversify_sources(keyword_pool, max_per_source=2, total=remaining)

    # Remove near-duplicate wire stories before sending to AI
    # (same story published by multiple outlets would inflate confidence)
    sources = _deduplicate(sources, threshold=0.70)

    # Enrich with category from trusted_sources table
    sources = _enrich_with_categories(sources)

    # AI analysis
    ai, used = _run_ai_analysis(claim, sources, eff)

    if ai and isinstance(ai.get("score"), (int, float)):
        score                   = max(0, min(100, int(ai["score"])))
        verdict                 = ai.get("verdict", "UNCORROBORATED").upper()
        explanation             = ai.get("explanation", "No explanation returned.")
        summary                 = ai.get("summary", explanation)
        source_notes            = ai.get("source_notes", [])
        convergence             = ai.get("convergence", [])
        narrative_delta         = ai.get("narrative_delta", [])
        bias_signals            = ai.get("bias_signals", [])
        triangulation_confidence = ai.get("triangulation_confidence", "low")
        triangulation_note      = ai.get("triangulation_note", "")
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
        score                   = _overlap_score(claim, sources)
        verdict                 = _h_verdict(score)
        explanation             = (
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
        source_notes            = []
        convergence             = []
        narrative_delta         = []
        bias_signals            = []
        triangulation_confidence = "low"
        triangulation_note      = ""
        used                    = "heuristic"
        provider                = "Heuristic"
        search_method           = search_method + "+heuristic"

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
        "verdict":                  verdict,
        "score":                    score,
        "explanation":              explanation,
        "summary":                  summary,
        "sources":                  fmt_sources,
        "source_notes":             source_notes,
        "categories":               categories,
        "convergence":              convergence,
        "narrative_delta":          narrative_delta,
        "bias_signals":             bias_signals,
        "triangulation_confidence": triangulation_confidence,
        "triangulation_note":       triangulation_note,
        "model_used":               used,
        "provider":                 provider,
        "search_method":            search_method,
        "processing_ms":            int((time.time() - start) * 1000),
    }