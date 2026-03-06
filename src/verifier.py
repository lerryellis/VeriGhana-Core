"""
VeriGhana Verifier
==================
Core claim-verification engine.

Fixes in this version:
  1. Gemini rate-limit (429) handling — exponential backoff + automatic
     cascade through ALL free models before giving up.
  2. Score always returned — keyword/similarity heuristic used when every
     model is exhausted so the Truth Meter never shows 0/blank.
  3. AI-generated fact summary — Gemini writes a 2-3 sentence brief that
     synthesises matching sources AND highlights nuances / differences
     between them (e.g. one source says X while another says Y).
  4. Sentiment analysis works independently of Gemini quota — we always
     compute a base score from database similarity even if AI is offline.
"""

import os
import re
import time
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
#  MODEL REGISTRY
#  Ordered from most-capable to lightest.  The retry loop walks through all
#  of them automatically when a 429 is hit.
# ──────────────────────────────────────────────────────────────────────────────
FREE_MODELS: dict[str, str] = {
    "Gemini 2.0 Flash":      "gemini-2.0-flash",
    "Gemini 2.0 Flash Lite": "gemini-2.0-flash-lite",
    "Gemini 1.5 Flash":      "gemini-1.5-flash",
    "Gemini 1.5 Flash 8B":   "gemini-1.5-flash-8b",
}

DEFAULT_MODEL = "gemini-2.0-flash"

# Ordered list used for fallback cascade
_MODEL_CASCADE = list(FREE_MODELS.values())


# ──────────────────────────────────────────────────────────────────────────────
#  GEMINI HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _get_genai():
    """Lazy import + configure google.generativeai."""
    try:
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        if api_key:
            genai.configure(api_key=api_key)
        return genai
    except ImportError:
        return None


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True when the exception looks like a Gemini 429 / quota error."""
    msg = str(exc).lower()
    return any(tok in msg for tok in ("429", "quota", "rate limit", "resource_exhausted", "rateerror"))


def _gemini_call(prompt: str, model_id: str, max_tokens: int = 800) -> str | None:
    """
    Call a single Gemini model with retry on transient errors.
    Returns the text response or None on quota / hard failure.
    Raises RuntimeError with code 'QUOTA' on rate-limit so the caller
    can try the next model.
    """
    genai = _get_genai()
    if genai is None:
        return None

    model = genai.GenerativeModel(model_id)
    generation_config = {"max_output_tokens": max_tokens, "temperature": 0.2}

    for attempt in range(3):                         # up to 3 retries per model
        try:
            resp = model.generate_content(prompt, generation_config=generation_config)
            return resp.text
        except Exception as exc:
            if _is_rate_limit_error(exc):
                if attempt < 2:
                    wait = 4 ** attempt             # 1 s, 4 s, 16 s
                    logger.warning("Gemini 429 on %s attempt %d — waiting %ds", model_id, attempt + 1, wait)
                    time.sleep(wait)
                else:
                    raise RuntimeError("QUOTA") from exc
            else:
                logger.warning("Gemini error on %s: %s", model_id, exc)
                return None

    return None


def _gemini_call_with_fallback(prompt: str, preferred_model: str, max_tokens: int = 800) -> tuple[str | None, str]:
    """
    Try preferred_model first, then cascade through all free models on quota errors.
    Returns (text_or_None, model_id_used).
    """
    cascade = [preferred_model] + [m for m in _MODEL_CASCADE if m != preferred_model]

    for model_id in cascade:
        try:
            text = _gemini_call(prompt, model_id, max_tokens)
            if text:
                return text, model_id
        except RuntimeError as exc:
            if "QUOTA" in str(exc):
                logger.info("Model %s quota hit — trying next model", model_id)
                continue
            break

    return None, preferred_model   # all models exhausted


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


def _keyword_search(claim: str, limit: int = 8) -> list[dict]:
    """
    Full-text / keyword search in fact_entries.
    Falls back to a simple ilike scan if FTS is unavailable.
    """
    supabase = _get_supabase()
    if supabase is None:
        return []

    # Extract meaningful words (>= 4 chars)
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", claim)]
    if not words:
        return []

    results: list[dict] = []

    # Strategy 1 — Postgres full-text search
    try:
        tsquery = " | ".join(words[:12])
        res = (
            supabase.table("fact_entries")
            .select("id, title, content, url_link, source_name, published_date")
            .text_search("title", tsquery)
            .limit(limit)
            .execute()
        )
        if res.data:
            results.extend(res.data)
    except Exception:
        pass

    # Strategy 2 — ilike on most distinctive word
    if not results and words:
        for word in words[:5]:
            try:
                res = (
                    supabase.table("fact_entries")
                    .select("id, title, content, url_link, source_name, published_date")
                    .ilike("title", f"%{word}%")
                    .limit(limit)
                    .execute()
                )
                if res.data:
                    results.extend(res.data)
                    break
            except Exception:
                pass

    # Strategy 3 — content ilike
    if not results and words:
        for word in words[:3]:
            try:
                res = (
                    supabase.table("fact_entries")
                    .select("id, title, content, url_link, source_name, published_date")
                    .ilike("content", f"%{word}%")
                    .limit(limit)
                    .execute()
                )
                if res.data:
                    results.extend(res.data)
                    break
            except Exception:
                pass

    # Deduplicate by id
    seen: set = set()
    unique: list[dict] = []
    for r in results:
        if r.get("id") not in seen:
            seen.add(r.get("id"))
            unique.append(r)

    return unique[:limit]


def _vector_search(claim: str, model_id: str, limit: int = 6) -> list[dict]:
    """
    Embed the claim with Gemini and run a pgvector similarity query.
    Returns an empty list if embeddings / pgvector are unavailable.
    """
    genai = _get_genai()
    supabase = _get_supabase()
    if genai is None or supabase is None:
        return []

    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=claim,
            task_type="retrieval_query",
        )
        embedding = result["embedding"]
    except Exception as exc:
        logger.warning("Embedding failed: %s", exc)
        return []

    try:
        res = supabase.rpc(
            "match_fact_entries",
            {"query_embedding": embedding, "match_count": limit, "match_threshold": 0.55},
        ).execute()
        return res.data or []
    except Exception:
        # Try the older function name too
        try:
            res = supabase.rpc(
                "search_facts",
                {"query_embedding": embedding, "limit_count": limit},
            ).execute()
            return res.data or []
        except Exception:
            pass

    return []


# ──────────────────────────────────────────────────────────────────────────────
#  SIMILARITY HEURISTIC  (used when Gemini is fully unavailable)
# ──────────────────────────────────────────────────────────────────────────────

def _keyword_overlap_score(claim: str, sources: list[dict]) -> int:
    """
    Fast heuristic truth score (0–100) based on keyword overlap between
    the claim and retrieved source titles/content.  Used as a fallback
    when every Gemini model is rate-limited.
    """
    if not sources:
        return 5

    claim_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", claim.lower()))
    best_overlap = 0.0

    for s in sources:
        text = f"{s.get('title', '')} {s.get('content', '')[:500]}".lower()
        src_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", text))
        if not src_words:
            continue
        overlap = len(claim_words & src_words) / max(len(claim_words), 1)
        if overlap > best_overlap:
            best_overlap = overlap

    # Map overlap ratio → score
    if best_overlap >= 0.65:
        return int(70 + best_overlap * 25)   # 70-95
    elif best_overlap >= 0.40:
        return int(45 + best_overlap * 50)   # 45-70
    elif best_overlap >= 0.20:
        return int(20 + best_overlap * 80)   # 20-36
    else:
        return max(5, int(best_overlap * 100))


def _heuristic_verdict(score: int) -> str:
    if score >= 70:
        return "VERIFIED"
    elif score >= 45:
        return "PARTIAL"
    elif score >= 15:
        return "UNCORROBORATED"
    else:
        return "UNCORROBORATED"


# ──────────────────────────────────────────────────────────────────────────────
#  AI ANALYSIS  (verdict + score + summary with source nuances)
# ──────────────────────────────────────────────────────────────────────────────

_ANALYSIS_PROMPT = """You are VeriGhana, an AI fact-checker for Ghana. Analyse the claim against the provided source excerpts.

CLAIM:
{claim}

SOURCE EXCERPTS ({count} sources):
{sources_text}

Return ONLY valid JSON — no markdown, no code fences:
{{
  "verdict": "VERIFIED" | "PARTIAL" | "FALSE" | "UNCORROBORATED",
  "score": <integer 0-100>,
  "explanation": "<1-2 sentence plain-language verdict explanation>",
  "summary": "<2-3 sentence synthesis: what the sources collectively say, AND note any notable differences or nuances between them (e.g. 'Citi Newsroom reports X while Joy Online adds Y...'). If only one source, note its key angle.>",
  "source_notes": [
    {{"source": "<source_name>", "stance": "<what this specific source says about the claim in 1 sentence>"}}
  ]
}}

Scoring guide: 85-100 = fully confirmed, 65-84 = mostly confirmed, 45-64 = partially supported, 20-44 = weakly supported, 0-19 = not supported / contradicted.
UNCORROBORATED means no relevant sources found, not that the claim is false."""

def _build_sources_text(sources: list[dict], max_chars: int = 2500) -> str:
    parts = []
    for i, s in enumerate(sources[:6], 1):
        title   = s.get("title", "Untitled")
        src     = s.get("source_name", s.get("source", "Unknown"))
        content = (s.get("content") or s.get("snippet") or "")[:300]
        date    = s.get("published_date", "")
        date_str = f" ({date[:10]})" if date else ""
        parts.append(f"[{i}] {src}{date_str} — {title}\n    {content}")
        if sum(len(p) for p in parts) > max_chars:
            break
    return "\n\n".join(parts) if parts else "(no matching sources found in database)"


def _parse_gemini_json(text: str) -> dict | None:
    """Extract and parse the JSON object from Gemini's response."""
    if not text:
        return None
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find the first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _run_ai_analysis(claim: str, sources: list[dict], model_id: str) -> tuple[dict | None, str]:
    """
    Ask Gemini to analyse the claim vs sources.
    Returns (parsed_dict_or_None, model_id_actually_used).
    """
    sources_text = _build_sources_text(sources)
    prompt = _ANALYSIS_PROMPT.format(
        claim=claim,
        count=len(sources),
        sources_text=sources_text,
    )
    text, used_model = _gemini_call_with_fallback(prompt, model_id, max_tokens=900)
    parsed = _parse_gemini_json(text)
    return parsed, used_model


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN PUBLIC FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def verify_claim(claim: str, model: str = DEFAULT_MODEL, model_id: str | None = None) -> dict:
    """
    Verify a claim against the VeriGhana database.

    Accepts both `model` (API-style model ID string) and `model_id`
    (legacy keyword used by the old app.py) for backwards compatibility.

    Returns:
      {
        verdict:       str,           # VERIFIED | PARTIAL | FALSE | UNCORROBORATED | ERROR
        score:         int,           # 0–100
        explanation:   str,           # 1-2 sentence verdict
        summary:       str,           # AI synthesis with source nuances
        sources:       list[dict],    # [{title, url_link, source_name, stance?}]
        source_notes:  list[dict],    # [{source, stance}]
        model_used:    str,
        search_method: str,
        processing_ms: int,
      }
    """
    start = time.time()

    # ── normalise model id ──────────────────────────────────────────────────
    effective_model = model_id or model or DEFAULT_MODEL
    # If a display name was passed (e.g. "Gemini 2.0 Flash"), resolve to ID
    if effective_model in FREE_MODELS:
        effective_model = FREE_MODELS[effective_model]

    # ── retrieve sources ────────────────────────────────────────────────────
    # Try vector search first; fall back to keyword search
    search_method = "vector"
    sources = _vector_search(claim, effective_model, limit=8)

    if not sources:
        search_method = "keyword"
        sources = _keyword_search(claim, limit=8)

    # ── AI analysis ─────────────────────────────────────────────────────────
    ai_result, used_model = _run_ai_analysis(claim, sources, effective_model)

    if ai_result and isinstance(ai_result.get("score"), (int, float)):
        # ── Happy path: Gemini responded ────────────────────────────────────
        score       = max(0, min(100, int(ai_result.get("score", 0))))
        verdict     = ai_result.get("verdict", "UNCORROBORATED").upper()
        explanation = ai_result.get("explanation", "No explanation returned.")
        summary     = ai_result.get("summary", explanation)
        source_notes = ai_result.get("source_notes", [])

        if verdict not in ("VERIFIED", "PARTIAL", "FALSE", "UNCORROBORATED"):
            verdict = "UNCORROBORATED"

        # Sanity: if no sources were found, cap score at 15
        if not sources and score > 15:
            score = max(5, score // 4)
            verdict = "UNCORROBORATED"

    else:
        # ── Fallback: all models exhausted or parsing failed ─────────────────
        score       = _keyword_overlap_score(claim, sources)
        verdict     = _heuristic_verdict(score)
        explanation = (
            "AI analysis unavailable (Gemini quota reached on all models). "
            "Score is based on keyword overlap with database records."
        )
        summary = (
            f"Found {len(sources)} potentially related source(s) in the database. "
            "AI summarisation is temporarily unavailable due to API quota limits. "
            "Please try again in a few minutes or switch to a different Gemini model."
        ) if sources else (
            "No matching records found in the VeriGhana database for this claim. "
            "AI summarisation is also temporarily unavailable."
        )
        source_notes = []
        used_model = "heuristic"
        search_method = search_method + "+heuristic"

    # ── Format source list ──────────────────────────────────────────────────
    formatted_sources = []
    for s in sources:
        # Find matching stance note if available
        src_name = s.get("source_name", s.get("source", "Unknown"))
        stance = ""
        for note in source_notes:
            if note.get("source", "").lower() in src_name.lower() or src_name.lower() in note.get("source", "").lower():
                stance = note.get("stance", "")
                break

        formatted_sources.append({
            "title":         s.get("title", "Untitled"),
            "url_link":      s.get("url_link", s.get("url", "#")),
            "url":           s.get("url_link", s.get("url", "#")),
            "source_name":   src_name,
            "source":        src_name,
            "published_date": s.get("published_date", ""),
            "stance":        stance,
        })

    processing_ms = int((time.time() - start) * 1000)

    return {
        "verdict":       verdict,
        "score":         score,
        "explanation":   explanation,
        "summary":       summary,
        "sources":       formatted_sources,
        "source_notes":  source_notes,
        "model_used":    used_model,
        "search_method": search_method,
        "processing_ms": processing_ms,
    }