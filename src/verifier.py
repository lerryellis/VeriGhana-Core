"""
VeriGhana Verifier
==================
Core claim-verification engine with multi-provider AI cascade.

Provider priority order (auto-failover on quota / rate-limit):
  Tier 1  Gemini      gemini-2.0-flash → gemini-2.0-flash-lite
                      → gemini-1.5-flash → gemini-1.5-flash-8b
  Tier 2  Groq        llama-3.3-70b-versatile → llama-3.1-8b-instant
                      → gemma2-9b-it
  Tier 3  Cohere      command-r-plus → command-r
  Tier 4  OpenRouter  llama-3.3-70b:free → gemma-3-27b:free
                      → mistral-7b:free
  Tier 5  Heuristic   keyword-overlap score (never fails)

Required .env keys  (add whichever you have — the more the better):
  GOOGLE_API_KEY   or GEMINI_API_KEY   — aistudio.google.com  (free)
  GROQ_API_KEY                         — console.groq.com     (free)
  COHERE_API_KEY                       — dashboard.cohere.com (free tier)
  OPENROUTER_API_KEY                   — openrouter.ai        (free models)
"""

import os, re, time, json, logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  MODEL REGISTRY  (shown in the UI dropdown)
# ──────────────────────────────────────────────────────────────────────────────
FREE_MODELS: dict[str, str] = {
    "Gemini 2.0 Flash":        "gemini-2.0-flash",
    "Gemini 2.0 Flash Lite":   "gemini-2.0-flash-lite",
    "Gemini 1.5 Flash":        "gemini-1.5-flash",
    "Gemini 1.5 Flash 8B":     "gemini-1.5-flash-8b",
    "Groq Llama 3.3 70B":      "groq:llama-3.3-70b-versatile",
    "Groq Llama 3.1 8B Fast":  "groq:llama-3.1-8b-instant",
    "Cohere Command-R+":       "cohere:command-r-plus",
    "Cohere Command-R":        "cohere:command-r",
    "OpenRouter Llama 3.3 70B":"openrouter:llama-3.3-70b",
}

DEFAULT_MODEL = "gemini-2.0-flash"

_GEMINI_CASCADE     = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-flash-8b"]
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

def _is_quota(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(t in msg for t in ("429","quota","rate limit","rate_limit",
               "resource_exhausted","too many requests","overloaded","tokens per"))


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


def _sources_text(sources: list[dict], max_chars: int = 2500) -> str:
    parts = []
    for i, s in enumerate(sources[:6], 1):
        title   = s.get("title", "Untitled")
        src     = s.get("source_name", s.get("source", "Unknown"))
        content = (s.get("content") or s.get("snippet") or "")[:300]
        date    = s.get("published_date", "")
        ds      = f" ({date[:10]})" if date else ""
        parts.append(f"[{i}] {src}{ds} — {title}\n    {content}")
        if sum(len(p) for p in parts) > max_chars:
            break
    return "\n\n".join(parts) if parts else "(no matching sources found in database)"


_PROMPT = """You are VeriGhana, an AI fact-checker for Ghana. Analyse the claim against the provided source excerpts.

CLAIM:
{claim}

SOURCE EXCERPTS ({count} sources):
{sources_text}

Return ONLY valid JSON — no markdown, no code fences, nothing else:
{{
  "verdict": "VERIFIED" | "PARTIAL" | "FALSE" | "UNCORROBORATED",
  "score": <integer 0-100>,
  "explanation": "<1-2 sentence plain-language verdict explanation>",
  "summary": "<2-3 sentence synthesis of what the sources collectively say, noting any differences or nuances between them, e.g. 'Citi Newsroom reports X while Joy Online adds Y...'. If sources agree, note that.>",
  "source_notes": [
    {{"source": "<source_name>", "stance": "<what this specific source says about the claim in 1 sentence>"}}
  ]
}}

Scoring: 85-100=fully confirmed, 65-84=mostly confirmed, 45-64=partially, 20-44=weakly, 0-19=not supported/contradicted.
UNCORROBORATED = no relevant sources found, not necessarily false."""


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 1 — GEMINI
# ──────────────────────────────────────────────────────────────────────────────

def _get_genai():
    try:
        import google.generativeai as genai
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        if key:
            genai.configure(api_key=key)
            return genai
    except ImportError:
        pass
    return None


def _call_gemini(prompt: str, preferred: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
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
                        logger.info("Gemini quota on %s — next", mid)
                        break
                else:
                    logger.warning("Gemini error on %s: %s", mid, exc)
                    break

    return None, preferred


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 2 — GROQ
# ──────────────────────────────────────────────────────────────────────────────

def _call_groq(prompt: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    # SAFEGUARD 1: load key securely from .env — never hardcode
    load_dotenv()
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None, "groq-unavailable"

    # SAFEGUARD 2: use official groq package when available, raw HTTP as fallback
    try:
        from groq import Groq as GroqClient
        client = GroqClient(api_key=key)
        use_package = True
    except ImportError:
        use_package = False

    import urllib.request as _urlreq

    # SAFEGUARD 3: split system instructions from user content (same as the example)
    messages = [
        {
            "role": "system",
            "content": (
                "You are VeriGhana, a Ghana fact-checking AI. "
                "Return ONLY valid JSON — no markdown, no code fences, no extra text."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    for mid in _GROQ_CASCADE:
        for attempt in range(2):
            try:
                if use_package:
                    resp = client.chat.completions.create(
                        model=mid,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=0.1,                          # SAFEGUARD 4: 0.1 = more deterministic JSON
                        response_format={"type": "json_object"}, # SAFEGUARD 5: forces valid JSON output
                    )
                    text = resp.choices[0].message.content
                else:
                    payload = json.dumps({
                        "model": mid,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": 0.1,                           # SAFEGUARD 4
                        "response_format": {"type": "json_object"},  # SAFEGUARD 5
                    }).encode()
                    req = _urlreq.Request(
                        "https://api.groq.com/openai/v1/chat/completions",
                        data=payload,
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        method="POST",
                    )
                    with _urlreq.urlopen(req, timeout=30) as r:
                        text = json.loads(r.read())["choices"][0]["message"]["content"]

                if text:
                    return text, f"groq:{mid}"
                break
            except Exception as exc:
                if _is_quota(exc):
                    if attempt == 0:
                        time.sleep(3)
                        continue
                    logger.info("Groq quota on %s — next", mid)
                    break
                logger.warning("Groq error on %s: %s", mid, exc)
                break

    return None, "groq-exhausted"


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 3 — COHERE
# ──────────────────────────────────────────────────────────────────────────────

def _call_cohere(prompt: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    key = os.getenv("COHERE_API_KEY", "")
    if not key:
        return None, "cohere-unavailable"

    import urllib.request as _urlreq

    for mid in _COHERE_CASCADE:
        payload = json.dumps({
            "model": mid, "message": prompt,
            "max_tokens": max_tokens, "temperature": 0.2,
        }).encode()
        req = _urlreq.Request(
            "https://api.cohere.com/v1/chat",
            data=payload,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Accept": "application/json"},
            method="POST",
        )
        try:
            with _urlreq.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                text = data.get("text") or (
                    data.get("message", {}).get("content", [{}])[0].get("text", "")
                )
                if text:
                    return text, f"cohere:{mid}"
        except Exception as exc:
            if _is_quota(exc):
                logger.info("Cohere quota on %s — next", mid)
                continue
            logger.warning("Cohere error on %s: %s", mid, exc)
            break

    return None, "cohere-exhausted"


# ──────────────────────────────────────────────────────────────────────────────
#  TIER 4 — OPENROUTER
# ──────────────────────────────────────────────────────────────────────────────

def _call_openrouter(prompt: str, max_tokens: int = 900) -> tuple[Optional[str], str]:
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        return None, "openrouter-unavailable"

    import urllib.request as _urlreq

    for mid in _OPENROUTER_CASCADE:
        payload = json.dumps({
            "model": mid,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": 0.2,
        }).encode()
        req = _urlreq.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "HTTP-Referer": "https://verighana.gh",
                     "X-Title": "VeriGhana"},
            method="POST",
        )
        try:
            with _urlreq.urlopen(req, timeout=30) as r:
                text = json.loads(r.read())["choices"][0]["message"]["content"]
                if text:
                    label = mid.split("/")[-1].split(":")[0]
                    return text, f"openrouter:{label}"
        except Exception as exc:
            if _is_quota(exc) or "402" in str(exc):
                logger.info("OpenRouter quota on %s — next", mid)
                continue
            logger.warning("OpenRouter error on %s: %s", mid, exc)
            break

    return None, "openrouter-exhausted"


# ──────────────────────────────────────────────────────────────────────────────
#  MASTER CALLER — walks all tiers
# ──────────────────────────────────────────────────────────────────────────────

def _run_ai_analysis(claim: str, sources: list[dict], preferred_model: str) -> tuple[Optional[dict], str]:
    # Resolve display name → model ID
    if preferred_model in FREE_MODELS:
        preferred_model = FREE_MODELS[preferred_model]

    # If user selected a non-Gemini model, still start Gemini first for speed
    gemini_pref = preferred_model if not any(
        preferred_model.startswith(p) for p in ("groq:", "cohere:", "openrouter:")
    ) else _GEMINI_CASCADE[0]

    prompt = _PROMPT.format(
        claim=claim,
        count=len(sources),
        sources_text=_sources_text(sources),
    )

    for caller, label in [
        (lambda p: _call_gemini(p, gemini_pref), "gemini"),
        (_call_groq,        "groq"),
        (_call_cohere,      "cohere"),
        (_call_openrouter,  "openrouter"),
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


def _keyword_search(claim: str, limit: int = 8) -> list[dict]:
    supabase = _get_supabase()
    if supabase is None:
        return []
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", claim)]
    if not words:
        return []
    results: list[dict] = []
    sel = "id,title,content,url_link,source_name,published_date"

    try:
        r = (supabase.table("fact_entries").select(sel)
             .text_search("title", " | ".join(words[:12])).limit(limit).execute())
        if r.data:
            results.extend(r.data)
    except Exception:
        pass

    if not results:
        for w in words[:5]:
            try:
                r = (supabase.table("fact_entries").select(sel)
                     .ilike("title", f"%{w}%").limit(limit).execute())
                if r.data:
                    results.extend(r.data)
                    break
            except Exception:
                pass

    if not results:
        for w in words[:3]:
            try:
                r = (supabase.table("fact_entries").select(sel)
                     .ilike("content", f"%{w}%").limit(limit).execute())
                if r.data:
                    results.extend(r.data)
                    break
            except Exception:
                pass

    seen: set = set()
    unique: list[dict] = []
    for r in results:
        if r.get("id") not in seen:
            seen.add(r.get("id"))
            unique.append(r)
    return unique[:limit]


def _vector_search(claim: str, model_id: str, limit: int = 6) -> list[dict]:
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
        ("match_fact_entries", {"query_embedding": emb, "match_count": limit, "match_threshold": 0.55}),
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
#  TIER 5 — HEURISTIC (never fails)
# ──────────────────────────────────────────────────────────────────────────────

def _overlap_score(claim: str, sources: list[dict]) -> int:
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
#  PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def verify_claim(claim: str, model: str = DEFAULT_MODEL, model_id: Optional[str] = None) -> dict:
    """
    Verify a claim. Cascades through Gemini → Groq → Cohere → OpenRouter
    → heuristic, so a result is always returned.
    """
    start = time.time()
    eff   = model_id or model or DEFAULT_MODEL

    # Retrieve sources
    search_method = "vector"
    sources = _vector_search(claim, eff, limit=8)
    if not sources:
        search_method = "keyword"
        sources = _keyword_search(claim, limit=8)

    # AI analysis
    ai, used = _run_ai_analysis(claim, sources, eff)

    if ai and isinstance(ai.get("score"), (int, float)):
        score        = max(0, min(100, int(ai["score"])))
        verdict      = ai.get("verdict", "UNCORROBORATED").upper()
        explanation  = ai.get("explanation", "No explanation returned.")
        summary      = ai.get("summary", explanation)
        source_notes = ai.get("source_notes", [])
        if verdict not in ("VERIFIED","PARTIAL","FALSE","UNCORROBORATED"):
            verdict = "UNCORROBORATED"
        if not sources and score > 15:
            score = max(5, score // 4)
            verdict = "UNCORROBORATED"
        if "groq:"        in used: provider = "Groq"
        elif "cohere:"    in used: provider = "Cohere"
        elif "openrouter:" in used: provider = "OpenRouter"
        else:                       provider = "Gemini"
    else:
        score        = _overlap_score(claim, sources)
        verdict      = _h_verdict(score)
        explanation  = ("All AI providers are currently rate-limited. "
                        "Score is estimated from keyword overlap.")
        summary      = (
            f"Found {len(sources)} related source(s). "
            "AI summarisation unavailable — Gemini, Groq, Cohere and OpenRouter "
            "are all quota-limited right now. Please try again shortly."
        ) if sources else "No matching records found and all AI providers are unavailable."
        source_notes = []
        used         = "heuristic"
        provider     = "Heuristic"
        search_method = search_method + "+heuristic"

    # Format sources
    stance_map = {n.get("source","").lower(): n.get("stance","") for n in source_notes}
    fmt_sources = []
    for s in sources:
        nm = s.get("source_name", s.get("source", "Unknown"))
        fmt_sources.append({
            "title":          s.get("title", "Untitled"),
            "url_link":       s.get("url_link", s.get("url", "#")),
            "url":            s.get("url_link", s.get("url", "#")),
            "source_name":    nm,
            "source":         nm,
            "published_date": s.get("published_date", ""),
            "stance":         s.get("stance","") or stance_map.get(nm.lower(),""),
        })

    return {
        "verdict":       verdict,
        "score":         score,
        "explanation":   explanation,
        "summary":       summary,
        "sources":       fmt_sources,
        "source_notes":  source_notes,
        "model_used":    used,
        "provider":      provider,
        "search_method": search_method,
        "processing_ms": int((time.time() - start) * 1000),
    }