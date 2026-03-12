"""
VeriGhana — Streamlit Application  (merged)
=============================================
Full redesign matching index.html aesthetic,
with all original logic from the working app.py preserved:
  • Real Supabase auth (sign_in_with_password / sign_up)
  • Real verify_claim() call with model_id parameter
  • Full SITES_TO_TEST list (65 sites)
  • Full HEADLINE_PATTERNS list
  • test_single_site() with complete scraping logic
  • auto_add_to_scraper()
  • Live progress + summary counters in Site Tester
  • Database stats sidebar with trusted-source list
  • Skip-existing checkbox, category filter, custom URL tester
  • Cookie + localStorage session persistence (survives refresh/reopen)
"""

import streamlit as st
import streamlit.components.v1
import sys, os, time, hashlib, hmac, json, base64
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

# ── Core imports
try:
    from verifier import verify_claim, FREE_MODELS, DEFAULT_MODEL
    VERIFIER_OK = True
except ImportError:
    VERIFIER_OK = False
    FREE_MODELS   = {
        "Gemini 2.0 Flash":      "gemini-2.0-flash",
        "Gemini 2.0 Flash Lite": "gemini-2.0-flash-lite",
        "Gemini 1.5 Flash":      "gemini-1.5-flash",
        "Gemini 1.5 Flash 8B":   "gemini-1.5-flash-8b",
    }
    DEFAULT_MODEL = "gemini-2.0-flash"

try:
    from database_utils import get_supabase_client
    DB_OK = True
except ImportError:
    DB_OK = False

try:
    import auth as Auth
    import db   as DB
    BACKEND_OK = True
except ImportError:
    BACKEND_OK = False

ADMIN_EMAIL  = os.getenv("ADMIN_EMAIL", "")
_COOKIE_NAME = "vg_session"
_COOKIE_DAYS = 30
_SECRET      = os.getenv("SESSION_SECRET", "vg-default-secret-change-me")

# ── Notification service keys
SENDGRID_API_KEY  = os.getenv("SENDGRID_API_KEY",  "")
AT_USERNAME       = os.getenv("AT_USERNAME",        "")   # Africa's Talking username
AT_API_KEY        = os.getenv("AT_API_KEY",         "")   # Africa's Talking API key
NOTIFY_FROM_EMAIL = os.getenv("NOTIFY_FROM_EMAIL",  "noreply@verighana.gh")
RESEND_API_KEY    = os.getenv("RESEND_API_KEY",     "")   # free 3k emails/month
NOTIFY_FROM_NAME  = os.getenv("NOTIFY_FROM_NAME",   "VeriGhana")

TIER_LIMITS = {"free": 5, "pro": None, "institutional": None}
TIER_MODELS = {
    "free":          [list(FREE_MODELS.keys())[-1]],
    "pro":           list(FREE_MODELS.keys()),
    "institutional": list(FREE_MODELS.keys()),
}


# ══════════════════════════════════════════════
#  SESSION PERSISTENCE  (v3 — query-param primary)
#  Token = base64(json_payload) + "." + HMAC-SHA256
#
#  PRIMARY path  (always works):
#    Login  →  Python writes st.query_params["_vg"] = token
#    Refresh →  ?_vg= is preserved in URL → Python reads & restores
#              → rolls to a fresh token so it never expires silently
#
#  BACKUP path  (fresh tab / shared link without ?_vg=):
#    JS writes token to localStorage on every authenticated render.
#    st.markdown script (main-page context, NOT iframe) reads
#    localStorage on the first unauthenticated load and redirects
#    window.location with ?_vg= so Python can pick it up.
# ══════════════════════════════════════════════

def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    sig = hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify_token(token: str) -> Optional[dict]:
    """Return payload if token is valid and not expired, else None."""
    try:
        body, sig = token.rsplit(".", 1)
        expected  = hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padding = 4 - len(body) % 4
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * padding))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def _make_session_token(email: str, name: str, role: str,
                        tier: str, user_id: str) -> str:
    return _sign({
        "email": email,
        "name":  name,
        "role":  role,
        "tier":  tier,
        "uid":   user_id,
        "exp":   int(time.time()) + _COOKIE_DAYS * 86400,
    })


def _cookie_js(token: str) -> str:
    """Write token to both cookie and localStorage."""
    token_json = json.dumps(token)
    return f"""
<script>
(function() {{
  var token  = {token_json};
  var days   = {_COOKIE_DAYS};
  var exp    = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = "vg_session=" + encodeURIComponent(token)
                  + "; expires=" + exp + "; path=/; SameSite=Lax";
  try {{ localStorage.setItem("vg_token", token); }} catch(e) {{}}
}})();
</script>"""


def _clear_cookie_js() -> str:
    """Delete cookie and localStorage on sign-out."""
    return """
<script>
(function() {
  document.cookie = "vg_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax";
  try { localStorage.removeItem("vg_token"); } catch(e) {}
  var url = new URL(window.location.href);
  url.searchParams.delete("_vg");
  window.history.replaceState({}, document.title, url.toString());
})();
</script>"""


def _read_session_js() -> str:
    """
    Fallback: injected via st.markdown (runs in the MAIN page window,
    not an iframe) when Python has no ?_vg= token in the URL.
    Reads localStorage → redirects window.location with ?_vg= token.
    Only fires when the browser has a stored token but the URL doesn't.
    """
    return """
<script>
(function() {
  try {
    var token = localStorage.getItem("vg_token");
    if (!token) return;
    var params = new URLSearchParams(window.location.search);
    if (params.get("_vg") === token) return;  // already present
    params.set("_vg", token);
    window.location.replace(window.location.pathname + "?" + params.toString());
  } catch(e) {}
})();
</script>"""


def _clear_redirect_flag_js() -> str:
    """Kept for backwards compatibility — sessionStorage guard removed."""
    return ""  # no-op


def _ls_write_js(token: str) -> str:
    """Write token to localStorage only (backup for fresh-tab recovery)."""
    token_json = __import__("json").dumps(token)
    return f"<script>try{{localStorage.setItem('vg_token',{token_json});}}catch(e){{}}</script>"


def restore_session_from_cookie():
    """
    Called once at the top of main().
    PRIMARY path: reads ?_vg= from URL (Python, no JS needed).
    After restoring, rolls the token (fresh expiry) so it stays alive.
    Never clears ?_vg= — keeping it in the URL is what makes refresh work.
    """
    if st.session_state.get("logged_in"):
        # Already logged in this server run — just roll the token
        save_session_cookie()
        return

    token = st.query_params.get("_vg", "")
    if not token:
        return  # no token in URL → fallback JS will handle it

    payload = _verify_token(token)
    if not payload:
        # Token invalid/expired — wipe it and force fresh login
        try:
            st.query_params.pop("_vg")
        except Exception:
            st.query_params.clear()
        return

    st.session_state.update(
        logged_in  = True,
        user_email = payload["email"],
        user_name  = payload.get("name", ""),
        user_role  = payload["role"],
        user_tier  = payload["tier"],
        user_id    = payload["uid"],
    )
    # Roll to a fresh 30-day token — writes new ?_vg= in same rerun
    save_session_cookie()


def save_session_cookie():
    """
    Persist session two ways:
      1. Python sets st.query_params["_vg"] = token  (primary — survives refresh)
      2. JS writes to localStorage via st.markdown    (backup — survives new tabs)
    """
    token = _make_session_token(
        email   = st.session_state.user_email or "",
        name    = st.session_state.user_name  or "",
        role    = st.session_state.user_role  or "client",
        tier    = st.session_state.user_tier  or "free",
        user_id = str(st.session_state.user_id or ""),
    )
    # PRIMARY: Python sets query param — guaranteed to be in URL on next load
    try:
        st.query_params["_vg"] = token
    except Exception:
        pass
    # BACKUP: also write to localStorage for fresh-tab recovery
    st.markdown(_ls_write_js(token), unsafe_allow_html=True)


def clear_session_cookie():
    """Delete query param, localStorage and wipe session_state keys."""
    # Clear the query param so ?_vg= doesn't auto-restore after sign-out
    try:
        st.query_params.pop("_vg")
    except Exception:
        try:
            st.query_params.clear()
        except Exception:
            pass
    # Clear localStorage via st.markdown (runs in main window)
    st.markdown(
        "<script>try{localStorage.removeItem('vg_token');}catch(e){}</script>",
        unsafe_allow_html=True,
    )
    for key in ("logged_in", "user_email", "user_name",
                "user_role", "user_tier", "user_id"):
        st.session_state.pop(key, None)


def inject_session_reader():
    """
    Fallback for fresh tabs that have no ?_vg= in the URL.
    Uses st.markdown so the script runs in the MAIN window (not an iframe).
    The JS reads localStorage and redirects with ?_vg= if a token exists.
    """
    if not st.session_state.get("logged_in"):
        st.markdown(_read_session_js(), unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="VeriGhana — National Fact Verification",
    page_icon="🇬🇭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════
#  SITE TESTER CONSTANTS
# ══════════════════════════════════════════════
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

HEADLINE_PATTERNS = [
    ("h1", None), ("h2", None), ("h3", None), ("h4", None),
    ("h2", "entry-title"), ("h3", "entry-title"), ("h2", "post-title"),
    ("h3", "post-title"), ("h3", "article-title"), ("h2", "article-title"),
    ("h2", "title"), ("h3", "title"), ("a", "story-title"),
    ("h3", "td-module-title"), ("h3", "jeg_post_title"), ("h2", "jeg_post_title"),
    ("div", "article-headline"), ("span", "headline"), ("h3", "cb-post-title"),
    ("h2", "cb-post-title"), ("li", "news-item"), ("div", "news-title"),
    ("p", "title"), ("h2", "views-field-title"), ("span", "views-field-title"),
    ("h3", "views-field-title"), ("div", "field-title"), ("h2", "node-title"),
    ("h3", "node-title"), ("a", "node-title"), ("h2", "field-content"),
    ("h3", "field-content"), ("div", "news-list"), ("h4", "entry-title"),
    ("h4", "post-title"),
]

SITES_TO_TEST = [
    {"name": "Citi Newsroom",                  "url": "https://citinewsroom.com/category/news/",                          "category": "Media"},
    {"name": "Joy Online",                     "url": "https://www.myjoyonline.com/news/",                                "category": "Media"},
    {"name": "Graphic Online",                 "url": "https://www.graphic.com.gh/news/general-news.html",                "category": "Media"},
    {"name": "Ghana News Agency",              "url": "https://www.ghananewsagency.org/",                                 "category": "Media"},
    {"name": "3News",                          "url": "https://3news.com/",                                               "category": "Media"},
    {"name": "Peacefm Online",                 "url": "https://www.peacefmonline.com/",                                   "category": "Media"},
    {"name": "GhanaWeb",                       "url": "https://www.ghanaweb.com/",                                       "category": "Media"},
    {"name": "Pulse Ghana",                    "url": "https://www.pulse.com.gh/",                                       "category": "Media"},
    {"name": "Office of the President",        "url": "https://presidency.gov.gh/",                                      "category": "Government - Executive"},
    {"name": "Ghana Government Portal",        "url": "https://www.ghana.gov.gh/",                                       "category": "Government - Executive"},
    {"name": "Ministry of Foreign Affairs",    "url": "https://mfa.gov.gh/",                                             "category": "Government - Ministry"},
    {"name": "Ministry of Finance",            "url": "https://mofep.gov.gh/",                                           "category": "Government - Ministry"},
    {"name": "Ministry of Education",          "url": "https://moe.gov.gh/",                                             "category": "Government - Ministry"},
    {"name": "Ministry of Energy",             "url": "https://www.energymin.gov.gh/",                                   "category": "Government - Ministry"},
    {"name": "Ministry of Health",             "url": "https://www.moh.gov.gh/",                                         "category": "Government - Ministry"},
    {"name": "Ministry of Roads and Highways", "url": "https://www.mrh.gov.gh/",                                         "category": "Government - Ministry"},
    {"name": "Ministry of Trade and Industry", "url": "http://www.moti.gov.gh/",                                         "category": "Government - Ministry"},
    {"name": "Ministry of Communication",      "url": "https://moc.gov.gh/",                                             "category": "Government - Ministry"},
    {"name": "Ministry of the Interior",       "url": "https://www.mint.gov.gh/",                                        "category": "Government - Ministry"},
    {"name": "Ministry of Tourism",            "url": "https://www.touringghana.com/",                                   "category": "Government - Ministry"},
    {"name": "Ministry of Local Government",   "url": "http://www.mlgrd.gov.gh/",                                        "category": "Government - Ministry"},
    {"name": "Ministry of Justice",            "url": "https://mojag.gov.gh/",                                           "category": "Government - Ministry"},
    {"name": "Ministry of Defence",            "url": "https://mod.gov.gh/",                                             "category": "Government - Ministry"},
    {"name": "Parliament of Ghana",            "url": "https://www.parliament.gh/news",                                  "category": "Government - Legislature"},
    {"name": "Judicial Service of Ghana",      "url": "https://www.judicial.gov.gh/",                                    "category": "Government - Judiciary"},
    {"name": "Bank of Ghana",                  "url": "https://www.bog.gov.gh/news-publications/press-releases/",        "category": "Government - Regulatory"},
    {"name": "Electoral Commission",           "url": "https://www.ec.gov.gh/",                                          "category": "Government - Regulatory"},
    {"name": "National Development Planning",  "url": "https://www.ndpc.gov.gh/",                                        "category": "Government - Regulatory"},
    {"name": "Public Procurement Authority",   "url": "https://www.ppbghana.org/",                                       "category": "Government - Regulatory"},
    {"name": "National Communications Auth",   "url": "https://www.nca.org.gh/",                                         "category": "Government - Regulatory"},
    {"name": "Public Utilities Regulatory",    "url": "http://www.purc.com.gh/",                                         "category": "Government - Regulatory"},
    {"name": "Ghana Standards Authority",      "url": "https://www.gsa.gov.gh/",                                         "category": "Government - Regulatory"},
    {"name": "Food and Drugs Authority",       "url": "https://www.fdaghana.gov.gh/",                                    "category": "Government - Regulatory"},
    {"name": "National Commission on Culture", "url": "http://www.ghanaculture.gov.gh/",                                 "category": "Government - Regulatory"},
    {"name": "Ghana Revenue Authority",        "url": "https://gra.gov.gh/",                                             "category": "Government - Revenue"},
    {"name": "SSNIT",                          "url": "https://www.ssnit.org.gh/",                                       "category": "Government - Social"},
    {"name": "National Health Insurance Auth", "url": "https://www.nhis.gov.gh/",                                        "category": "Government - Social"},
    {"name": "National Identification Auth",   "url": "https://nia.gov.gh/",                                             "category": "Government - Identification"},
    {"name": "DVLA",                           "url": "https://dvla.gov.gh/",                                            "category": "Government - Identification"},
    {"name": "Ghana Education Service",        "url": "https://ges.gov.gh/",                                             "category": "Government - Education"},
    {"name": "National Teaching Council",      "url": "https://ntc.gov.gh/",                                             "category": "Government - Education"},
    {"name": "National Accreditation Board",   "url": "https://nab.gov.gh/",                                             "category": "Government - Education"},
    {"name": "GIMPA",                          "url": "https://www.gimpa.edu.gh/",                                       "category": "Government - Education"},
    {"name": "CSIR",                           "url": "http://www.csir.org.gh/",                                         "category": "Government - Education"},
    {"name": "Ghana Statistical Service",      "url": "https://www.statsghana.gov.gh/",                                  "category": "Government - Statistics"},
    {"name": "Ghana Health Service",           "url": "https://ghs.gov.gh/",                                             "category": "Government - Health"},
    {"name": "Volta River Authority",          "url": "https://www.vra.com/",                                            "category": "Government - Energy"},
    {"name": "GRIDCo",                         "url": "https://www.gridcogh.com/",                                       "category": "Government - Energy"},
    {"name": "Energy Commission",              "url": "https://www.energycom.gov.gh/",                                   "category": "Government - Energy"},
    {"name": "Ghana Investment Promotion",     "url": "https://www.gipcghana.com/",                                      "category": "Government - Investment"},
    {"name": "Ghana Export Promotion Auth",    "url": "https://www.gepaghana.org/",                                      "category": "Government - Investment"},
    {"name": "Ghana Free Zones Board",         "url": "https://gfzb.gov.gh/",                                            "category": "Government - Investment"},
    {"name": "Ghana Tourism Authority",        "url": "https://www.ghana.travel/",                                       "category": "Government - Investment"},
    {"name": "Ghana Armed Forces",             "url": "https://gafonline.mil.gh/",                                       "category": "Government - Security"},
    {"name": "Ghana Police Service",           "url": "https://www.police.gov.gh/",                                      "category": "Government - Security"},
    {"name": "NITA",                           "url": "https://nita.gov.gh/",                                            "category": "Government - Technology"},
    {"name": "Cyber Security Authority",       "url": "https://www.csa.gov.gh/",                                        "category": "Government - Technology"},
    {"name": "Data Protection Commission",     "url": "https://dataprotection.gov.gh/",                                  "category": "Government - Technology"},
    {"name": "Securities and Exchange Comm",   "url": "https://sec.gov.gh/",                                             "category": "Government - Finance"},
    {"name": "National Insurance Commission",  "url": "https://nicghana.org/",                                           "category": "Government - Finance"},
    {"name": "NPRA",                           "url": "https://www.npra.gov.gh/",                                        "category": "Government - Finance"},
    {"name": "CAGD",                           "url": "https://cagd.gov.gh/",                                            "category": "Government - Finance"},
    {"name": "Association of Ghana Industries","url": "https://www.agighana.org/",                                       "category": "Government - Business"},
    {"name": "Private Enterprise Federation",  "url": "https://pef.org.gh/",                                            "category": "Government - Business"},
    {"name": "Local Government Service",       "url": "https://lgs.gov.gh/",                                            "category": "Government - Local"},
]

STATUS_ICON = {
    "scrapeable":   "✅",
    "no_headlines": "⚠️",
    "blocked":      "🚫",
    "unreachable":  "❌",
    "ssl_error":    "🔒",
    "timeout":      "⏱️",
    "not_found":    "🔍",
    "error":        "❌",
}
STATUS_LABEL = {
    "scrapeable":   "Scrapeable",
    "no_headlines": "No Headlines",
    "blocked":      "Blocked (403)",
    "unreachable":  "Unreachable",
    "ssl_error":    "SSL Error",
    "timeout":      "Timeout",
    "not_found":    "Not Found (404)",
    "error":        "Error",
}


# ══════════════════════════════════════════════
#  SITE TESTER CORE
# ══════════════════════════════════════════════
def test_single_site(site: dict) -> dict:
    name     = site["name"]
    url      = site["url"]
    category = site.get("category", "Uncategorized")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15, verify=True)
    except requests.exceptions.SSLError:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        except Exception:
            return {"name": name, "url": url, "category": category, "status": "ssl_error", "samples": []}
    except requests.exceptions.ConnectionError:
        return {"name": name, "url": url, "category": category, "status": "unreachable", "samples": []}
    except requests.exceptions.Timeout:
        return {"name": name, "url": url, "category": category, "status": "timeout", "samples": []}
    except Exception as e:
        return {"name": name, "url": url, "category": category, "status": "error", "error_msg": str(e), "samples": []}

    if response.status_code == 403:
        return {"name": name, "url": url, "category": category, "status": "blocked", "samples": []}
    if response.status_code == 404:
        return {"name": name, "url": url, "category": category, "status": "not_found", "samples": []}
    if response.status_code not in [200, 301, 302]:
        return {"name": name, "url": url, "category": category, "status": "error", "samples": [], "http_code": response.status_code}

    soup = BeautifulSoup(response.text, "html.parser")
    best_tag, best_class, best_count, best_samples = None, None, 0, []

    for tag, css_class in HEADLINE_PATTERNS:
        elements = soup.find_all(tag, class_=css_class) if css_class else soup.find_all(tag)
        found = []
        for el in elements:
            link = el.find("a")
            text = el.get_text(strip=True)
            if link and len(text) > 20:
                found.append({"text": text[:80], "href": link.get("href", "")})
        if len(found) > best_count:
            best_count, best_tag, best_class, best_samples = len(found), tag, css_class, found[:3]

    if best_count == 0:
        return {"name": name, "url": url, "category": category, "status": "no_headlines", "samples": []}

    parsed   = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    for s in best_samples:
        if s["href"] and not s["href"].startswith("http"):
            s["href"] = base_url + s["href"]

    return {
        "name":          name,
        "url":           url,
        "category":      category,
        "status":        "scrapeable",
        "article_tag":   best_tag,
        "article_class": best_class,
        "base_url":      base_url,
        "count":         best_count,
        "samples":       best_samples,
    }


def auto_add_to_scraper(result: dict) -> dict:
    try:
        from source_manager import add_source_to_scraper
        return add_source_to_scraper(result)
    except ImportError:
        return {"success": False, "skipped": False, "message": "source_manager.py not found."}


# ══════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════
def init_state():
    defaults = dict(
        logged_in=False, user_email="", user_name="",
        user_role="client", user_tier="free", user_id=None,
        page="verify", result=None, history=[],
        test_results=[], testing=False,
        billing_plan="pro", billing_step="form",
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ══════════════════════════════════════════════
#  GLOBAL CSS
# ══════════════════════════════════════════════
def inject_css():
    st.markdown(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800'
        '&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300'
        '&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    _CSS = """
/* ═══════════════════════════════════════════
   VERIGHANA — GLOBAL LIGHT THEME
   Background : #f8fafc (cool off-white)
   Surface    : #ffffff (cards, nav, tabs)
   Border     : #e2e8f0
   Text primary   : #0f172a
   Text secondary : #475569
   Text muted     : #94a3b8
   Accent blue    : #2563eb
   Accent green   : #16a34a
   Accent red     : #dc2626
   Accent amber   : #d97706
   ═══════════════════════════════════════════ */

/* ─── GLOBAL RESET ─── */
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif!important;}
#MainMenu,footer,header{visibility:hidden!important;height:0!important;overflow:hidden!important;}
.stApp{background:#f8fafc!important;min-height:100vh;}

/* ─── NUKE ALL STREAMLIT PADDING ─── */
.block-container{padding:0!important;padding-top:0!important;max-width:100%!important;margin:0!important;}
[data-testid="stAppViewBlockContainer"]{padding:0!important;padding-top:0!important;max-width:100%!important;}
[data-testid="stMainBlockContainer"]{padding:0!important;padding-top:0!important;max-width:100%!important;}
.stMainBlockContainer{padding:0!important;padding-top:0!important;}
section.main > div{padding:0!important;padding-top:0!important;}
section.main > div > div{padding:0!important;}
section[data-testid="stSidebar"]{display:none!important;}
[data-testid="stVerticalBlock"]{gap:0!important;}
.vg-wrap [data-testid="stVerticalBlock"]{gap:.5rem!important;}

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:#f1f5f9}
::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:#94a3b8}

/* ─── AUTH PAGE ─── */
.auth-mode .stApp{
  display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  min-height:100vh;
  background:#f8fafc !important;
}
.auth-mode .block-container,
.auth-mode [data-testid="stAppViewBlockContainer"],
.auth-mode [data-testid="stMainBlockContainer"]{
  width:100%!important;max-width:440px!important;
  margin:0 auto!important;padding:0 1rem!important;
}
.auth-bg-grid{display:none;}

/* ─── NAV BAR ─── */
.vg-nav{
  background:#ffffff;
  border-bottom:1px solid #e2e8f0;
  padding:0 2rem;
  display:flex;align-items:center;
  height:56px;gap:1rem;
  position:sticky;top:0;z-index:300;
  width:100%;
  box-shadow:0 1px 3px rgba(0,0,0,.05);
}
.vg-logo{font-family:'Syne',sans-serif;font-weight:800;font-size:1.2rem;
  color:#0f172a;letter-spacing:-.03em;text-decoration:none;white-space:nowrap;}
.vg-logo em{font-style:normal;color:#2563eb;}
.vg-sep{width:1px;height:18px;background:#e2e8f0;}
.vg-nav-sub{font-family:'DM Mono',monospace;font-size:.6rem;color:#94a3b8;
  letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;}
.vg-nav-right{margin-left:auto;display:flex;align-items:center;gap:.75rem;}
.vg-avatar{width:28px;height:28px;border-radius:50%;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  display:flex;align-items:center;justify-content:center;
  font-family:'Syne',sans-serif;font-weight:700;
  font-size:.65rem;color:#fff;flex-shrink:0;}

/* ─── TAB BAR — styled via JS in render_tabs() ─── */

/* ─── PAGE SHELL ─── */
.vg-shell{background:#f8fafc;width:100%;}
.vg-wrap{max-width:1080px;margin:0 auto;padding:1.5rem 2rem 3rem;}

/* ─── PAGE HEADER ─── */
.vg-page-head{border-bottom:1px solid #e2e8f0;
  padding:.75rem 0 1rem;margin-bottom:1.25rem;}

/* ─── CARDS ─── */
.vg-card{background:#ffffff;border:1px solid #e2e8f0;
  border-radius:12px;padding:1.25rem;margin-bottom:.75rem;
  box-shadow:0 1px 3px rgba(0,0,0,.05),0 2px 8px rgba(0,0,0,.03);}
.vg-card-flat{background:#f1f5f9;border:1px solid #e2e8f0;
  border-radius:8px;padding:.85rem 1rem;margin-bottom:.6rem;}

/* ─── TYPOGRAPHY ─── */
.vg-h1{font-family:'Syne',sans-serif;font-size:1.5rem;font-weight:800;
  color:#0f172a;letter-spacing:-.04em;margin:0 0 .2rem;line-height:1.2;display:inline;}
.vg-h1 em{font-style:normal;color:#2563eb;}
.vg-h2{font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:700;
  color:#1e293b;margin:0 0 .6rem;}
.vg-h3{font-family:'Syne',sans-serif;font-size:.9rem;font-weight:700;
  color:#334155;margin:0 0 .3rem;}
.vg-sub{color:#64748b;font-size:.82rem;font-weight:400;
  line-height:1.6;margin:.3rem 0 0;display:block;}
.vg-mono{font-family:'DM Mono',monospace;font-size:.63rem;color:#94a3b8;
  letter-spacing:.07em;text-transform:uppercase;}

/* ─── BADGE ─── */
.vg-badge{display:inline-flex;align-items:center;gap:.3rem;
  background:#eff6ff;border:1px solid #bfdbfe;
  color:#1d4ed8;font-size:.62rem;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;
  padding:.25rem .75rem;border-radius:999px;}

/* ─── VERDICT CHIPS ─── */
.v-VERIFIED      {background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;}
.v-FALSE         {background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}
.v-PARTIAL       {background:#fffbeb;color:#d97706;border:1px solid #fde68a;}
.v-UNCORROBORATED{background:#f8fafc;color:#475569;border:1px solid #e2e8f0;}
.v-UNAVAILABLE   {background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;}
.v-ERROR         {background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}
.vchip{display:inline-block;padding:.25rem .75rem;border-radius:6px;
  font-family:'Syne',sans-serif;font-weight:700;font-size:.75rem;}

/* ─── TIER CHIPS ─── */
.t-free {background:#f8fafc;color:#475569;border:1px solid #e2e8f0;}
.t-pro  {background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;}
.t-inst {background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;}
.t-admin{background:#fffbeb;color:#b45309;border:1px solid #fde68a;}
.tchip{display:inline-block;padding:.15rem .6rem;border-radius:999px;
  font-family:'DM Mono',monospace;font-size:.6rem;letter-spacing:.04em;text-transform:uppercase;}

/* ─── TRUTH BAR ─── */
.tbar-bg{height:8px;background:#e2e8f0;border-radius:99px;overflow:hidden;margin:.5rem 0;}
.tbar-fill{height:100%;border-radius:99px;}
.tbar-green {background:linear-gradient(90deg,#16a34a,#4ade80);}
.tbar-orange{background:linear-gradient(90deg,#d97706,#fbbf24);}
.tbar-red   {background:linear-gradient(90deg,#dc2626,#f87171);}
.tbar-gray  {background:linear-gradient(90deg,#94a3b8,#cbd5e1);}

/* ─── SCORE ─── */
.score-num{font-family:'Syne',sans-serif;font-size:2.75rem;font-weight:800;line-height:1;}
.sc-green {color:#16a34a;}
.sc-orange{color:#d97706;}
.sc-red   {color:#dc2626;}
.sc-gray  {color:#94a3b8;}

/* ─── STAT PILLS ─── */
.spill{background:#ffffff;border:1px solid #e2e8f0;
  border-radius:10px;padding:.85rem 1rem;text-align:center;
  box-shadow:0 1px 3px rgba(0,0,0,.04);}
.spill-n{font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;
  color:#0f172a;display:block;letter-spacing:-.02em;}
.spill-l{font-size:.6rem;color:#94a3b8;font-family:'DM Mono',monospace;
  letter-spacing:.06em;text-transform:uppercase;display:block;margin-top:.2rem;}

/* ─── SOURCE ROWS ─── */
.src-row{display:flex;align-items:flex-start;gap:.5rem;
  padding:.5rem 0;border-bottom:1px solid #f1f5f9;}
.src-row:last-child{border-bottom:none;}
.src-dot{width:6px;height:6px;border-radius:50%;background:#3b82f6;flex-shrink:0;margin-top:5px;}
.src-title a{color:#2563eb;font-size:.82rem;text-decoration:none;line-height:1.4;}
.src-title a:hover{text-decoration:underline;}
.src-by{color:#94a3b8;font-family:'DM Mono',monospace;font-size:.62rem;}

/* ─── INPUTS ─── */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea{
  background:#ffffff!important;border:1.5px solid #e2e8f0!important;
  border-radius:8px!important;color:#0f172a!important;
  font-family:'DM Sans',sans-serif!important;font-size:.9rem!important;}
.stTextInput>div>div>input::placeholder,
.stTextArea>div>div>textarea::placeholder{color:#94a3b8!important;}
.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus{
  border-color:#2563eb!important;background:#ffffff!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.1)!important;}
.stSelectbox>div>div{background:#ffffff!important;
  border:1.5px solid #e2e8f0!important;
  border-radius:8px!important;color:#0f172a!important;}
div[data-baseweb="select"] *{color:#0f172a!important;}
label{color:#64748b!important;font-size:.62rem!important;
  font-family:'DM Mono',monospace!important;
  letter-spacing:.06em!important;text-transform:uppercase!important;}

/* ─── RADIO + CHECKBOX ─── */
.stRadio label{color:#334155!important;font-size:.875rem!important;}
.stCheckbox label{color:#334155!important;font-size:.875rem!important;}

/* ─── BUTTONS ─── */
.stButton>button{
  background:#2563eb!important;color:#fff!important;border:none!important;
  border-radius:8px!important;font-family:'DM Sans',sans-serif!important;
  font-weight:600!important;font-size:.875rem!important;
  padding:.6rem 1.25rem!important;transition:all .15s!important;
  letter-spacing:.01em!important;width:100%;
  box-shadow:0 1px 2px rgba(37,99,235,.15)!important;}
.stButton>button:hover{background:#1d4ed8!important;
  box-shadow:0 2px 8px rgba(37,99,235,.25)!important;}
.btn-ghost .stButton>button{background:#ffffff!important;
  border:1.5px solid #e2e8f0!important;color:#475569!important;
  box-shadow:none!important;}
.btn-ghost .stButton>button:hover{background:#f8fafc!important;
  border-color:#cbd5e1!important;color:#1e293b!important;}
.btn-blue .stButton>button{background:#2563eb!important;}
.btn-blue .stButton>button:hover{background:#1d4ed8!important;}
.btn-green .stButton>button{background:#16a34a!important;}
.btn-green .stButton>button:hover{background:#15803d!important;}
.btn-red .stButton>button{background:#ffffff!important;
  border:1.5px solid #fecaca!important;color:#dc2626!important;
  box-shadow:none!important;}
.btn-red .stButton>button:hover{background:#fef2f2!important;border-color:#f87171!important;}

/* ─── ALERTS ─── */
div[data-testid="stAlert"]{border-radius:8px!important;}
.stSuccess{background:#f0fdf4!important;border:1px solid #bbf7d0!important;color:#15803d!important;}
.stError  {background:#fef2f2!important;border:1px solid #fecaca!important;color:#dc2626!important;}
.stWarning{background:#fffbeb!important;border:1px solid #fde68a!important;color:#b45309!important;}
.stInfo   {background:#eff6ff!important;border:1px solid #bfdbfe!important;color:#1d4ed8!important;}

/* ─── DIVIDER ─── */
hr{border:none!important;border-top:1px solid #e2e8f0!important;margin:1rem 0!important;}

/* ─── EXPANDER ─── */
.streamlit-expanderHeader{background:#f8fafc!important;
  border:1px solid #e2e8f0!important;border-radius:8px!important;
  color:#334155!important;font-family:'DM Sans',sans-serif!important;font-size:.875rem!important;}
.streamlit-expanderHeader:hover{background:#f1f5f9!important;}
[data-testid="stExpander"]{border:1px solid #e2e8f0!important;border-radius:8px!important;}

/* ─── SPINNER / PROGRESS ─── */
.stSpinner>div{border-top-color:#2563eb!important;}
.stProgress>div>div{background:#2563eb!important;}

/* ─── BILLING PAGE ─── */
.bill-shell{background:#f8fafc;width:100%;min-height:calc(100vh - 112px);}
.bill-wrap{max-width:960px;margin:0 auto;padding:1.5rem 2rem 3rem;}
.bill-card{
  background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:1.5rem;
  margin-bottom:1rem;box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 12px rgba(0,0,0,.03);}
.bill-card-accent{
  background:#fff;border:1.5px solid #2563eb;border-radius:12px;padding:1.5rem;
  margin-bottom:1rem;box-shadow:0 1px 3px rgba(37,99,235,.08),0 4px 16px rgba(37,99,235,.06);}
.bill-label{font-family:'DM Mono',monospace;font-size:.6rem;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;color:#94a3b8;margin-bottom:.75rem;display:block;}
.bill-back .stButton>button{background:#fff!important;border:1.5px solid #e2e8f0!important;
  color:#64748b!important;font-size:.8rem!important;padding:.35rem .9rem!important;
  width:auto!important;box-shadow:none!important;}
.bill-back .stButton>button:hover{background:#f8fafc!important;color:#334155!important;}
.bill-pay-btn .stButton>button{
  background:linear-gradient(135deg,#1d4ed8,#2563eb)!important;
  font-size:.95rem!important;padding:.8rem 1.5rem!important;
  border-radius:10px!important;box-shadow:0 4px 12px rgba(37,99,235,.3)!important;}
.bill-pay-btn .stButton>button:hover{
  background:linear-gradient(135deg,#1e40af,#1d4ed8)!important;
  box-shadow:0 6px 18px rgba(37,99,235,.4)!important;}

/* ─── INNER TABS (login) ─── */
.stTabs [data-baseweb="tab-list"]{background:#f1f5f9!important;
  border:1px solid #e2e8f0!important;border-radius:8px!important;
  padding:.2rem!important;gap:.15rem!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#64748b!important;
  border-radius:6px!important;font-family:'DM Sans',sans-serif!important;
  font-size:.85rem!important;border:none!important;padding:.45rem .9rem!important;}
.stTabs [aria-selected="true"]{background:#ffffff!important;color:#0f172a!important;
  box-shadow:0 1px 3px rgba(0,0,0,.08)!important;font-weight:600!important;}

/* ─── ADMIN TABLE ─── */
.admin-table{width:100%;border-collapse:collapse;}
.admin-table th{padding:.55rem .85rem;text-align:left;font-family:'DM Mono',monospace;
  font-size:.6rem;color:#94a3b8;letter-spacing:.07em;font-weight:600;
  border-bottom:2px solid #e2e8f0;background:#f8fafc;}
.admin-table td{padding:.65rem .85rem;font-size:.82rem;color:#1e293b;
  border-bottom:1px solid #f1f5f9;}
.admin-table tr:hover td{background:#f8fafc;}

/* ─── PLAN CARDS ─── */
.plan-card{border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;
  box-shadow:0 1px 3px rgba(0,0,0,.05);}
.plan-card.featured{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.15);}
.plan-header.pro {background:linear-gradient(135deg,#1e3a8a,#1d4ed8);}
.plan-header.inst{background:linear-gradient(135deg,#064e3b,#065f46);}
.plan-header.free{background:#f1f5f9;}
.plan-header{padding:1rem 1.25rem;border-bottom:1px solid rgba(0,0,0,.06);}
.plan-body{padding:1rem 1.25rem;background:#ffffff;}
"""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
def sc(score):
    if score >= 70: return "green"
    if score >= 40: return "orange"
    return "red" if score > 0 else "gray"

def tier_chip(tier, role=None):
    if role == "admin":
        return '<span class="tchip t-admin">Admin</span>'
    m = {"free": "t-free", "pro": "t-pro", "institutional": "t-inst"}
    l = {"free": "Free",   "pro": "Pro",   "institutional": "Institutional"}
    return f'<span class="tchip {m.get(tier,"t-free")}">{l.get(tier,tier)}</span>'

def queries_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for h in st.session_state.history if h.get("date","").startswith(today))

def daily_limit():
    return TIER_LIMITS.get(st.session_state.user_tier, 5)

def is_admin():
    return (
        ADMIN_EMAIL != "" and
        st.session_state.user_email.lower().strip() == ADMIN_EMAIL.lower().strip()
    ) or st.session_state.user_role == "admin"


# ══════════════════════════════════════════════
#  AUTH LOGIC
# ══════════════════════════════════════════════
def do_login(email, password):
    if not email or not password:
        return False, "Email and password are required."

    # ── Admin shortcut
    if ADMIN_EMAIL and email.lower().strip() == ADMIN_EMAIL.lower().strip():
        st.session_state.update(logged_in=True, user_email=email,
                                user_name="Admin", user_role="admin",
                                user_tier="institutional", user_id="admin-001")
        save_session_cookie()
        return True, ""

    # ── Real Supabase auth
    if DB_OK:
        try:
            supabase = get_supabase_client()
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.update(
                logged_in=True, user_email=email,
                user_name=email.split("@")[0].title(),
                user_role="client", user_tier="free",
                user_id=str(res.user.id) if res.user else None,
            )
            save_session_cookie()
            return True, ""
        except Exception as e:
            err = str(e)
            if "Invalid login" in err or "invalid" in err.lower():
                return False, "Incorrect email or password."
            return False, f"Login failed: {err}"

    # ── Backend auth (auth.py / db.py)
    if BACKEND_OK:
        import asyncio
        try:
            user = asyncio.run(DB.get_user_by_email(email))
            if not user:
                return False, "No account found with this email."
            if not Auth.verify_password(password, user["password_hash"]):
                return False, "Incorrect password."
            if not user["is_active"]:
                return False, "This account has been suspended."
            st.session_state.update(
                logged_in=True, user_email=user["email"],
                user_name=user.get("full_name") or email.split("@")[0].title(),
                user_role=user["role"], user_tier=user["tier"],
                user_id=str(user["id"]),
            )
            save_session_cookie()
            return True, ""
        except Exception as e:
            return False, f"Login error: {e}"

    return False, "Authentication service unavailable."


def do_register(email, password):
    if not email or not password:
        return False, "Email and password are required."

    if DB_OK:
        try:
            supabase = get_supabase_client()
            supabase.auth.sign_up({"email": email, "password": password})
            return True, "Account created! Check your email to confirm, then sign in."
        except Exception as e:
            return False, f"Registration failed: {e}"

    if BACKEND_OK:
        import asyncio
        errs = Auth.validate_password_strength(password)
        if errs:
            return False, errs[0]
        try:
            if asyncio.run(DB.get_user_by_email(email)):
                return False, "An account with this email already exists."
            user = asyncio.run(DB.create_user(
                email=email,
                password_hash=Auth.hash_password(password),
            ))
            return (True, "Account created! You can now sign in.") if user \
                   else (False, "Could not create account.")
        except Exception as e:
            return False, f"Registration error: {e}"

    return False, "Registration service unavailable."


# ══════════════════════════════════════════════
#  PAGE: AUTH
# ══════════════════════════════════════════════
def page_auth():
    st.markdown("""
    <div class="auth-bg-grid"></div>
    <style>
    [data-testid="stAppViewBlockContainer"],
    [data-testid="stMainBlockContainer"],
    .block-container {
        max-width: 420px !important;
        margin: 0 auto !important;
        padding: 0 1rem !important;
        padding-top: 0 !important;
    }
    [data-testid="stVerticalBlock"] > div:first-child { margin-top: 3rem !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;padding:2.5rem 0 1.5rem;">
      <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:2rem;
                  color:#fff;letter-spacing:-.02em;margin-bottom:.6rem;">
        Veri<em style="font-style:normal;color:#2563eb;">Ghana</em>
      </div>
      <span class="vg-badge">🇬🇭 National Fact Verification Platform</span>
      <div style="color:#334155;font-size:.78rem;margin-top:.5rem;">
        Powered by AI · Trusted Ghanaian sources
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="vg-card">', unsafe_allow_html=True)
    tab_in, tab_up = st.tabs(["Sign In", "Create Account"])

    with tab_in:
        st.markdown("<br>", unsafe_allow_html=True)
        li_email = st.text_input("Email", placeholder="you@example.com", key="li_em")
        li_pass  = st.text_input("Password", type="password", placeholder="••••••••", key="li_pw")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign In", key="li_btn", use_container_width=True):
            with st.spinner(""):
                ok, err = do_login(li_email, li_pass)
            if ok:
                st.success("Welcome back!")
                time.sleep(0.4); st.rerun()
            else:
                st.error(err)
        st.markdown("""
        <div style="text-align:center;margin-top:.75rem;">
          <span style="font-size:.72rem;color:#94a3b8;">
            Login: set <code style="color:#2563eb;font-size:.7rem;">Email and password are protected</code> VeriGhana
          </span>
        </div>""", unsafe_allow_html=True)

    with tab_up:
        st.markdown("<br>", unsafe_allow_html=True)
        r_email = st.text_input("Email", placeholder="you@example.com", key="r_em")
        r_pass  = st.text_input("Password", type="password", placeholder="Minimum 6 characters", key="r_pw")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create Account", key="r_btn", use_container_width=True):
            with st.spinner(""):
                ok, msg = do_register(r_email, r_pass)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        st.markdown("""
        <div style="text-align:center;margin-top:.75rem;">
          <span style="font-size:.72rem;color:#94a3b8;">
            GIMPA students — promo code
            <code style="color:#2563eb;background:rgba(37,99,235,.08);
              padding:.1rem .35rem;border-radius:3px;font-size:.7rem;">GIMPA2026</code>
            for 50% off Pro
          </span>
        </div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  SHARED: NAVBAR + TABBAR
# ══════════════════════════════════════════════
def render_nav():
    tier    = st.session_state.user_tier
    role    = st.session_state.user_role
    email   = st.session_state.user_email or ""
    name    = st.session_state.user_name or email.split("@")[0].title() or "User"
    initial = (name or "U")[0].upper()
    st.markdown(f"""
    <div class="vg-nav">
      <span class="vg-logo">Veri<em>Ghana</em></span>
      <span class="vg-sep"></span>
      <span class="vg-nav-sub">National Fact Verification</span>
      <div class="vg-nav-right">
        {tier_chip(tier, role)}
        <div class="vg-avatar">{initial}</div>
        <span style="color:#94a3b8;font-family:'DM Mono',monospace;font-size:.68rem;">{email}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_tabs():
    page  = st.session_state.page
    admin = is_admin()
    pages = [
        ("verify",  "Verify",  False),
        ("history", "History", False),
        ("account", "Account", False),
    ]
    if admin:
        pages += [("admin", "Admin", True), ("tickets", "Tickets", True), ("tester", "Site Tester", True)]

    # ── JS-based tab styling ───────────────────────────────────────────────
    # The global .stButton>button CSS uses !important everywhere, so :has()
    # selectors can't beat it reliably. Instead we inject a script that finds
    # each tab button by its known key (data-testid contains the key) and
    # stamps it with a unique class, which CSS can then target at high specificity.
    tab_keys   = [f"nav_{k}" for k, _, _ in pages]
    active_key = f"nav_{page}"
    admin_keys = [f"nav_{k}" for k, _, is_adm in pages if is_adm]

    st.markdown(f"""
<style>
/* ── Tab row wrapper ── */
.vg-tabrow-wrap {{
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  position: sticky;
  top: 52px;
  z-index: 200;
  padding: 0 2rem;
  display: flex;
  align-items: stretch;
  gap: 0;
  width: 100%;
  box-shadow: 0 1px 0 #e2e8f0;
}}
/* ── Every tab button reset ── */
button.vg-tab-btn {{
  background: transparent !important;
  border: none !important;
  border-top: none !important;
  border-left: none !important;
  border-right: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  color: #94a3b8 !important;
  font-family: 'DM Sans', sans-serif !important;
  font-size: .82rem !important;
  font-weight: 400 !important;
  padding: .65rem 1.25rem !important;
  width: auto !important;
  min-width: 0 !important;
  white-space: nowrap !important;
  cursor: pointer !important;
  transition: color .15s, border-color .15s !important;
  letter-spacing: .01em !important;
  line-height: 1.4 !important;
}}
button.vg-tab-btn:hover {{
  background: transparent !important;
  color: #475569 !important;
  border-bottom-color: #cbd5e1 !important;
}}
/* Active tab */
button.vg-tab-btn.vg-tab-active {{
  color: #0f172a !important;
  font-weight: 600 !important;
  border-bottom-color: #2563eb !important;
  background: transparent !important;
}}
/* Admin tabs */
button.vg-tab-btn.vg-tab-admin {{
  color: #b45309 !important;
}}
button.vg-tab-btn.vg-tab-admin.vg-tab-active {{
  color: #d97706 !important;
  border-bottom-color: #d97706 !important;
}}
</style>
<script>
(function applyTabStyles() {{
  var tabKeys    = {tab_keys};
  var activeKey  = "{active_key}";
  var adminKeys  = {admin_keys};

  function tag() {{
    var found = 0;
    tabKeys.forEach(function(key) {{
      // Streamlit puts the key into the button's data-testid via the key prop
      // It appears in the element's parent div as key="nav_xxx" or in aria
      // Most reliable: find by button text matching the label map
    }});

    // Strategy: walk ALL buttons, match by aria-label or inner text
    var buttons = document.querySelectorAll('button');
    var labelToKey = {{}};
    {chr(10).join(f'    labelToKey["{lbl}"] = "nav_{k}";' for k, lbl, _ in pages)}

    buttons.forEach(function(btn) {{
      var txt = btn.innerText ? btn.innerText.trim() : '';
      var key = labelToKey[txt];
      if (!key) return;

      btn.classList.add('vg-tab-btn');
      found++;

      if (key === activeKey) {{
        btn.classList.add('vg-tab-active');
      }}
      if (adminKeys.indexOf(key) !== -1) {{
        btn.classList.add('vg-tab-admin');
      }}

      // Style the parent column to be auto-width (not flex-1)
      var col = btn.closest('[data-testid="column"]');
      if (col) {{
        col.style.flex       = '0 0 auto';
        col.style.padding    = '0';
        col.style.minWidth   = '0';
        col.style.background = 'transparent';
      }}

      // Style the horizontal block = the tab bar container
      var bar = btn.closest('[data-testid="stHorizontalBlock"]');
      if (bar && !bar.classList.contains('vg-tab-bar-done')) {{
        bar.classList.add('vg-tab-bar-done');
        bar.style.background   = '#ffffff';
        bar.style.borderBottom = '1px solid #e2e8f0';
        bar.style.position     = 'sticky';
        bar.style.top          = '52px';
        bar.style.zIndex       = '200';
        bar.style.padding      = '0 2rem';
        bar.style.gap          = '0';
        bar.style.alignItems   = 'stretch';
        bar.style.boxShadow    = '0 1px 0 #e2e8f0';
      }}
    }});

    if (found < {len(pages)}) {{
      setTimeout(tag, 60);
    }}
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', tag);
  }} else {{
    tag();
  }}
  // Re-run after Streamlit re-renders
  setTimeout(tag, 200);
  setTimeout(tag, 600);
}})();
</script>
""", unsafe_allow_html=True)

    # Render the actual buttons — compact columns, spacer absorbs leftover width
    col_widths = [1] * len(pages) + [max(1, 8 - len(pages))]
    all_cols   = st.columns(col_widths, gap="small")
    for i, (k, lbl, _) in enumerate(pages):
        with all_cols[i]:
            is_active = (k == page)
            if st.button(lbl, key=f"nav_{k}",
                         type="primary" if is_active else "secondary",
                         use_container_width=False):
                st.session_state.page = k
                st.rerun()
    with all_cols[-1]:
        st.markdown("&nbsp;", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: VERIFY
# ══════════════════════════════════════════════
def page_verify():
    tier  = st.session_state.user_tier
    role  = st.session_state.user_role
    lim   = daily_limit()
    used  = queries_today()

    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)

    st.markdown("""
    <div class="vg-page-head">
      <div class="vg-h1">Verify a <em>Claim</em></div>
      <div class="vg-sub">Paste a post, WhatsApp message or headline — AI searches 60+ trusted Ghanaian sources and scores the verdict.</div>
    </div>
    """, unsafe_allow_html=True)

    if lim is not None:
        rem   = max(0, lim - used)
        pct   = min(100, int(used / lim * 100))
        bar_c = "green" if rem > 2 else "orange" if rem > 0 else "red"
        c_hex = "#4ade80" if rem > 2 else "#fbbf24" if rem > 0 else "#f87171"
        st.markdown(f"""
        <div class="vg-card-flat" style="display:flex;align-items:center;
             justify-content:space-between;padding:1rem 1.5rem;margin-bottom:1.5rem;">
          <div>
            <span class="vg-mono">Daily Usage</span><br>
            <span style="font-family:'Syne',sans-serif;font-weight:700;
                         font-size:1.15rem;color:{c_hex};">{used}/{lim}</span>
            <span style="color:#475569;font-size:.78rem;margin-left:.4rem;">queries used today</span>
          </div>
          <div style="width:220px;">
            <div class="tbar-bg">
              <div class="tbar-fill tbar-{bar_c}" style="width:{pct}%;"></div>
            </div>
            <div class="vg-mono" style="margin-top:.3rem;color:#334155;">
              {rem} remaining · upgrade for unlimited
            </div>
          </div>
          <div>{tier_chip(tier, role)}</div>
        </div>
        """, unsafe_allow_html=True)

    in1, in2 = st.columns([3, 1])

    with in1:
        user_input = st.text_area(
            "",
            height=140,
            key="claim_in",
            placeholder="e.g. Government announces 30% tax on Mobile Money starting Monday…",
            label_visibility="collapsed",
        )

    with in2:
        st.markdown("**Select AI Model**", unsafe_allow_html=False)
        model_names = list(FREE_MODELS.keys())
        default_idx = 0
        for i, n in enumerate(model_names):
            if "Lite" in n or "lite" in n:
                default_idx = i
                break
        selected_model_name = st.selectbox(
            "AI Model", options=model_names, index=default_idx,
            help="If one model hits its daily quota, switch to another.",
            label_visibility="collapsed",
        )
        selected_model_id = FREE_MODELS[selected_model_name]
        st.markdown(
            f'<div class="vg-mono" style="margin-top:-.5rem;margin-bottom:.75rem;">'
            f'Using: {selected_model_id}</div>',
            unsafe_allow_html=True,
        )

        can = (lim is None) or (used < lim)
        if not can:
            st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
        run_btn = st.button(
            "Check This Claim" if can else "Daily Limit Reached",
            key="run_btn", use_container_width=True, disabled=not can,
        )
        if not can:
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:.72rem;color:#475569;line-height:1.5;margin-top:.5rem;">'
            'Switch models if you see a quota error. All models are free tier.</div>',
            unsafe_allow_html=True,
        )

    if run_btn:
        if not user_input or not user_input.strip():
            st.warning("Please enter a claim to verify.")
        elif not VERIFIER_OK:
            st.error("verifier.py not found — check your src/ directory.")
        else:
            with st.spinner(f"Searching trusted sources using {selected_model_name}…"):
                t0 = time.time()
                try:
                    result = verify_claim(user_input.strip(), model_id=selected_model_id)
                    result.update(
                        claim         = user_input.strip(),
                        date          = datetime.now().strftime("%Y-%m-%d %H:%M"),
                        model         = selected_model_id,
                        model_name    = selected_model_name,
                        processing_ms = int((time.time() - t0) * 1000),
                    )
                    st.session_state.result = result
                    st.session_state.history.insert(0, result)
                except Exception as e:
                    st.error(f"Verification error: {e}")

    res = st.session_state.result
    if res:
        st.markdown("<hr>", unsafe_allow_html=True)
        verdict      = res.get("verdict", "UNCORROBORATED").upper()
        score        = max(0, min(100, int(res.get("score", 0))))
        explanation  = res.get("explanation", "")
        summary      = res.get("summary", explanation)
        sources      = res.get("sources", [])
        source_notes = res.get("source_notes", [])
        model_used   = res.get("model_used", res.get("model", selected_model_id))
        provider     = res.get("provider", "")
        color        = sc(score)

        if verdict not in ("VERIFIED", "PARTIAL", "FALSE", "UNCORROBORATED", "ERROR"):
            verdict = "UNCORROBORATED"

        r1, r2, r3 = st.columns([1, 2.2, 1.8])

        with r1:
            st.markdown(f"""
            <div class="vg-card" style="text-align:center;padding:2rem 1rem;">
              <div class="vg-mono" style="margin-bottom:.75rem;">TRUTH SCORE</div>
              <div class="score-num sc-{color}">{score}%</div>
              <div style="margin-top:1rem;">
                <span class="vchip v-{verdict}">{verdict}</span>
              </div>
              <div class="vg-mono" style="margin-top:.75rem;color:#334155;">
                {res.get("processing_ms",0)}ms
              </div>
              <div class="vg-mono" style="margin-top:.25rem;color:#475569;font-size:.65rem;">
                via {provider} · {model_used.split(":")[-1][:28]}
              </div>
            </div>
            """, unsafe_allow_html=True)

        with r2:
            st.markdown(f"""
            <div class="vg-card">
              <div class="vg-mono" style="margin-bottom:.75rem;">TRUTH METER</div>
              <div class="tbar-bg">
                <div class="tbar-fill tbar-{color}" style="width:{score}%;transition:width 1.4s ease;"></div>
              </div>
              <div style="font-size:.875rem;color:#64748b;line-height:1.65;
                           font-style:italic;margin-top:.75rem;">
                {explanation}
              </div>
            </div>
            """, unsafe_allow_html=True)

            if summary and summary != explanation:
                st.markdown(f"""
                <div class="vg-card" style="margin-top:.75rem;border-left:3px solid #2563eb;">
                  <div class="vg-mono" style="margin-bottom:.5rem;color:#2563eb;">AI ANALYSIS SUMMARY</div>
                  <div style="font-size:.875rem;color:#334155;line-height:1.7;">{summary}</div>
                </div>
                """, unsafe_allow_html=True)

        with r3:
            from html import escape as _esc
            stance_map = {}
            for note in source_notes:
                k = note.get("source", "").lower()
                if k:
                    stance_map[k] = note.get("stance", "")

            src_rows = ""
            for s in sources[:5]:
                if isinstance(s, dict):
                    raw_title  = s.get("title", "Untitled") or "Untitled"
                    url        = s.get("url_link", s.get("url", "#")) or "#"
                    raw_name   = s.get("source_name", s.get("source", "")) or ""
                    raw_stance = s.get("stance", "") or stance_map.get(raw_name.lower(), "")
                else:
                    raw_title, url, raw_name, raw_stance = str(s), "#", "", ""

                title    = _esc(raw_title[:70])
                src_name = _esc(raw_name[:60])
                stance   = _esc(raw_stance[:130]) if raw_stance else ""

                if not url.startswith(("http://", "https://")):
                    url = "#"

                stance_row = (
                    f'<div style="font-size:.71rem;color:#64748b;font-style:italic;'
                    f'margin-top:.2rem;line-height:1.4;">{stance}</div>'
                ) if stance else ""

                src_rows += (
                    '<div class="src-row">'
                      '<div class="src-dot"></div>'
                      '<div style="flex:1;min-width:0;">'
                        f'<div class="src-title">'
                          f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
                        '</div>'
                        f'<div class="src-by">{src_name}</div>'
                        f'{stance_row}'
                      '</div>'
                    '</div>'
                )

            if not src_rows:
                src_rows = (
                    '<div style="color:#475569;font-size:.875rem;padding:.5rem 0;">'
                    'No source matches found in the indexed database.</div>'
                )

            st.markdown(
                f'<div class="vg-card">'
                f'<div class="vg-mono" style="margin-bottom:.75rem;">SOURCES</div>'
                f'{src_rows}</div>',
                unsafe_allow_html=True,
            )

        st.markdown(f"""
        <div class="vg-card-flat" style="padding:1rem 1.5rem;">
          <span class="vg-mono">Claim checked</span><br>
          <span style="color:#64748b;font-size:.875rem;font-style:italic;">
            "{res.get('claim','')[:300]}{"..." if len(res.get('claim',''))>300 else ""}"
          </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="btn-ghost" style="display:inline-block;margin-top:.5rem;">',
                    unsafe_allow_html=True)
        if st.button("Clear Result", key="clear_btn"):
            st.session_state.result = None; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="vg-h3" style="margin-bottom:1rem;">Database Stats</div>',
                unsafe_allow_html=True)
    db1, db2 = st.columns(2)
    if DB_OK:
        try:
            supabase   = get_supabase_client()
            count_resp = supabase.table("fact_entries").select("id", count="exact").execute()
            total      = count_resp.count or 0
            src_resp   = supabase.table("trusted_sources").select("source_name,category").execute()
            with db1:
                st.markdown(f'<div class="spill"><span class="spill-n">{total:,}</span>'
                            f'<span class="spill-l">Facts Indexed</span></div>',
                            unsafe_allow_html=True)
            with db2:
                st.markdown(f'<div class="spill"><span class="spill-n">{len(src_resp.data or [])}</span>'
                            f'<span class="spill-l">Trusted Sources</span></div>',
                            unsafe_allow_html=True)
            if src_resp.data:
                with st.expander("View trusted sources"):
                    for s in src_resp.data:
                        st.markdown(
                            f'<div style="color:#1e293b;font-size:.82rem;padding:.25rem 0;">'
                            f'<span style="color:#2563eb;">•</span> '
                            f'{s["source_name"]} '
                            f'<span style="color:#475569;font-family:\'DM Mono\',monospace;'
                            f'font-size:.68rem;">({s["category"]})</span></div>',
                            unsafe_allow_html=True,
                        )
        except Exception as e:
            with db1:
                st.error(f"DB error: {e}")
    else:
        st.markdown('<div style="color:#475569;font-size:.82rem;">Database not connected.</div>',
                    unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: HISTORY
# ══════════════════════════════════════════════
def page_history():
    hist = st.session_state.history
    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)
    st.markdown("""
    <div class="vg-page-head">
      <div class="vg-h1">Verification <em>History</em></div>
      <div class="vg-sub">All claims verified this session.</div>
    </div>
    """, unsafe_allow_html=True)

    if not hist:
        st.markdown("""
        <div class="vg-card" style="text-align:center;padding:3.5rem;">
          <div style="font-size:2.5rem;margin-bottom:1rem;">📋</div>
          <div class="vg-h3">No verifications yet</div>
          <div class="vg-sub">Head to Verify to check your first claim.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        verified = sum(1 for h in hist if h.get("verdict") == "Verified")
        false_ct = sum(1 for h in hist if h.get("verdict") == "False")
        uncorr   = sum(1 for h in hist if h.get("verdict") not in ("Verified","False"))

        s1, s2, s3, s4 = st.columns(4)
        for col, (val, lbl) in zip([s1,s2,s3,s4], [
            (len(hist),"Total"), (verified,"Verified"), (false_ct,"False"), (uncorr,"Other")
        ]):
            with col:
                st.markdown(f'<div class="spill"><span class="spill-n">{val}</span>'
                            f'<span class="spill-l">{lbl}</span></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        for h in hist:
            verdict = h.get("verdict","UNCORROBORATED")
            score   = int(h.get("score",0))
            color   = sc(score)
            claim   = h.get("claim","")
            label   = claim[:80] + "…" if len(claim) > 80 else claim
            with st.expander(f"{STATUS_ICON.get(verdict,'?')} {label}"):
                c1, c2 = st.columns([1,3])
                with c1:
                    st.markdown(f"""
                    <div style="text-align:center;padding:1rem 0;">
                      <div class="score-num sc-{color}" style="font-size:2.5rem;">{score}%</div>
                      <div style="margin-top:.5rem;">
                        <span class="vchip v-{verdict.replace(' ','-')}">{verdict}</span>
                      </div>
                      <div class="vg-mono" style="margin-top:.6rem;">{h.get("date","—")}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                    <div style="padding:.75rem 0;">
                      <div class="tbar-bg">
                        <div class="tbar-fill tbar-{color}" style="width:{score}%;"></div>
                      </div>
                      <div style="color:#64748b;font-size:.875rem;line-height:1.6;font-style:italic;margin-top:.75rem;">
                        {h.get("explanation","—")}
                      </div>
                      <div class="vg-mono" style="margin-top:.75rem;color:#334155;">
                        Model: {h.get("model","—")}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="btn-ghost" style="display:inline-block;">', unsafe_allow_html=True)
        if st.button("Clear All History", key="clear_hist"):
            st.session_state.history = []; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: ACCOUNT
# ══════════════════════════════════════════════
def page_account():
    tier  = st.session_state.user_tier
    role  = st.session_state.user_role
    email = st.session_state.user_email
    name  = st.session_state.user_name or email or "User"
    lim   = daily_limit()
    used  = queries_today()

    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)
    st.markdown("""
    <div class="vg-page-head"><div class="vg-h1">Your <em>Account</em></div></div>
    """, unsafe_allow_html=True)

    a1, a2 = st.columns([1.3, 1])
    with a1:
        st.markdown(f"""
        <div class="vg-card">
          <div class="vg-mono" style="margin-bottom:1rem;">PROFILE</div>
          <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.25rem;">
            <div style="width:52px;height:52px;border-radius:50%;flex-shrink:0;
                        background:linear-gradient(135deg,#2563eb,#60a5fa);
                        display:flex;align-items:center;justify-content:center;
                        font-family:'Syne',sans-serif;font-weight:800;
                        font-size:1.2rem;color:#fff;">
              {(name or "U")[0].upper()}
            </div>
            <div>
              <div class="vg-h3" style="font-size:1rem;">{name}</div>
              <div style="color:#64748b;font-size:.82rem;">{email}</div>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:.75rem;">
            {tier_chip(tier, role)}
            <span style="color:#475569;font-size:.78rem;">
              {"Unlimited verifications" if lim is None else f"{lim} verifications / day"}
            </span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with a2:
        pct   = 0 if lim is None else min(100, int(used / lim * 100))
        bar_c = "green" if pct < 60 else "orange" if pct < 90 else "red"
        st.markdown(f"""
        <div class="vg-card">
          <div class="vg-mono" style="margin-bottom:1rem;">TODAY'S USAGE</div>
          {"<div style='color:#16a34a;font-family:Syne,sans-serif;font-size:1.5rem;font-weight:800;'>Unlimited</div>"
            if lim is None else
           f"<div style='font-family:Syne,sans-serif;font-size:1.75rem;font-weight:800;color:#fff;'>{used}"
           f"<span style='color:#475569;font-size:1rem;font-weight:400;'>/{lim}</span></div>"
           f"<div class='tbar-bg' style='margin:.5rem 0;'><div class='tbar-fill tbar-{bar_c}' style='width:{pct}%;'></div></div>"
          }
          <div class="vg-mono" style="color:#334155;">
            {f"{max(0,lim-used)} remaining today" if lim else "No daily limits on your plan"}
          </div>
        </div>
        """, unsafe_allow_html=True)

    if tier == "free":
        st.markdown('<hr>', unsafe_allow_html=True)

        # ── Pricing section header
        st.markdown("""
        <div style="margin-bottom:1.5rem;">
          <div class="vg-h2" style="font-size:1.2rem;margin-bottom:.35rem;">Upgrade Your Plan</div>
          <div class="vg-sub">Choose the plan that fits your verification needs.
            All plans include access to our full database of Ghanaian sources.</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Render both plan cards as pure HTML so they match in height
        pro_features = [
            ("∞", "Unlimited daily verifications"),
            ("4",  "All AI models — Gemini, Groq, Cohere, OpenRouter"),
            ("3",  "REST API keys for integrations"),
            ("✓",  "Export full verification history as CSV"),
            ("✓",  "Real-time alert webhooks"),
            ("✓",  "Priority model queue — no rate-limit delays"),
            ("✓",  "Advanced truth-score breakdown per source"),
            ("✓",  "Email digest of daily fact-checks"),
        ]
        inst_features = [
            ("∞",  "Everything in Pro, for your whole team"),
            ("20", "Team seats with individual logins"),
            ("20", "API keys for newsroom integrations"),
            ("20", "Bulk verify up to 20 claims at once"),
            ("✓",  "White-label PDF & HTML reports"),
            ("✓",  "Custom source watchlist & alerts"),
            ("✓",  "Dedicated onboarding & support"),
            ("✓",  "SLA-backed uptime guarantee"),
        ]

        def _feature_row(stat, text):
            return (
                '<div style="display:flex;align-items:flex-start;gap:.75rem;'
                'padding:.55rem 0;border-bottom:1px solid #f1f5f9;">'
                '<span style="font-family:DM Mono,monospace;font-size:.72rem;'
                'font-weight:700;color:#2563eb;min-width:20px;text-align:center;'
                f'margin-top:.05rem;">{stat}</span>'
                f'<span style="color:#334155;font-size:.85rem;line-height:1.5;">{text}</span>'
                '</div>'
            )

        pro_rows  = "".join(_feature_row(s, t) for s, t in pro_features)
        inst_rows = "".join(_feature_row(s, t) for s, t in inst_features)

        st.markdown(f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;align-items:stretch;">

          <!-- PRO CARD -->
          <div style="display:flex;flex-direction:column;
                      background:#f8fafc;
                      border:1px solid #bfdbfe;
                      border-radius:12px;overflow:hidden;position:relative;">
            <!-- Popular badge -->
            <div style="position:absolute;top:1rem;right:1rem;
                        background:#2563eb;color:#fff;
                        font-family:'DM Mono',monospace;font-size:.58rem;
                        font-weight:700;letter-spacing:.08em;text-transform:uppercase;
                        padding:.2rem .6rem;border-radius:999px;">MOST POPULAR</div>
            <!-- Header -->
            <div style="padding:1.5rem 1.5rem 1.25rem;
                        background:linear-gradient(135deg,#1e3a8a 0%,#1d4ed8 100%);
                        border-bottom:1px solid #e2e8f0;">
              <div style="font-family:'DM Mono',monospace;font-size:.62rem;
                           color:#94a3b8;letter-spacing:.1em;
                           text-transform:uppercase;margin-bottom:.5rem;">PRO PLAN</div>
              <div style="font-family:'Syne',sans-serif;font-weight:800;
                           font-size:1.75rem;color:#fff;letter-spacing:-.02em;
                           line-height:1.1;margin-bottom:.35rem;">$9.99
                <span style="font-size:.9rem;font-weight:400;color:#94a3b8;">/month</span>
              </div>
              <div style="color:#64748b;font-size:.82rem;">
                For journalists, researchers &amp; fact-checkers
              </div>
            </div>
            <!-- Features -->
            <div style="padding:1.25rem 1.5rem;flex:1;">
              {pro_rows}
            </div>
          </div>

          <!-- INSTITUTIONAL CARD -->
          <div style="display:flex;flex-direction:column;
                      background:#f8fafc;
                      border:1px solid #bbf7d0;
                      border-radius:12px;overflow:hidden;">
            <!-- Header -->
            <div style="padding:1.5rem 1.5rem 1.25rem;
                        background:linear-gradient(135deg,#064e3b 0%,#065f46 100%);
                        border-bottom:1px solid #e2e8f0;">
              <div style="font-family:'DM Mono',monospace;font-size:.62rem;
                           color:#94a3b8;letter-spacing:.1em;
                           text-transform:uppercase;margin-bottom:.5rem;">INSTITUTIONAL PLAN</div>
              <div style="font-family:'Syne',sans-serif;font-weight:800;
                           font-size:1.75rem;color:#fff;letter-spacing:-.02em;
                           line-height:1.1;margin-bottom:.35rem;">$79.99
                <span style="font-size:.9rem;font-weight:400;color:#94a3b8;">/month</span>
              </div>
              <div style="color:#64748b;font-size:.82rem;">
                For newsrooms, NGOs &amp; government agencies
              </div>
            </div>
            <!-- Features -->
            <div style="padding:1.25rem 1.5rem;flex:1;">
              {inst_rows}
            </div>
          </div>

        </div>
        """, unsafe_allow_html=True)

        # ── CTA buttons below the cards
        st.markdown("<div style='margin-top:1rem;'>", unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        with b1:
            st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
            if st.button("Upgrade to Pro →", key="up_pro", use_container_width=True):
                st.session_state.billing_plan = "pro"
                st.session_state.billing_step = "form"
                st.session_state.page = "billing"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with b2:
            st.markdown('<div class="btn-green">', unsafe_allow_html=True)
            if st.button("Upgrade to Institutional →", key="up_inst", use_container_width=True):
                st.session_state.billing_plan = "institutional"
                st.session_state.billing_step = "form"
                st.session_state.page = "billing"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════
    # SUBSCRIPTION MANAGEMENT (paid tiers only)
    # ══════════════════════════════════════════════
    if tier in ("pro", "institutional"):
        st.markdown("<br>", unsafe_allow_html=True)

        uid   = st.session_state.get("user_id", "")
        uemail = st.session_state.get("user_email", "")
        sub_info = get_subscription_info(uid)

        # Auto-expire if billing period has ended
        if _expire_if_due(uid, uemail, sub_info):
            st.rerun()

        # If DB offline / row not yet written, treat paid users as active
        raw_status  = sub_info.get("subscription_status", "free")
        sub_status  = raw_status if raw_status in ("active","cancelled","expired") else "active"
        expires_raw   = sub_info.get("subscription_expires_at")
        cancelled_raw = sub_info.get("cancelled_at")

        def _fmt_date(iso_str):
            if not iso_str:
                return "—"
            try:
                dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                return dt.strftime("%B %d, %Y")
            except Exception:
                return iso_str[:10]

        expires_fmt   = _fmt_date(expires_raw)
        cancelled_fmt = _fmt_date(cancelled_raw)
        plan_label    = "Pro Plan" if tier == "pro" else "Institutional Plan"
        plan_color    = "#2563eb" if tier == "pro" else "#16a34a"
        plan_amount   = "$9.99"   if tier == "pro" else "$79.99"

        # ── Left col: subscription card | Right col: upsell (Pro only)
        sub_col, upsell_col = st.columns([1.4, 1], gap="large")

        with sub_col:

            # ── STATUS CARD ────────────────────────────────────────────
            st.markdown(
                f'<div class="vg-card" style="border-left:4px solid {plan_color};">',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div style="font-family:DM Mono,monospace;font-size:.6rem;font-weight:700;'                'letter-spacing:.1em;text-transform:uppercase;color:#94a3b8;'                'margin-bottom:.85rem;">SUBSCRIPTION</div>',
                unsafe_allow_html=True,
            )

            # Status badge
            if sub_status == "active":
                badge = ('<span style="background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;'                         'font-size:.72rem;font-weight:700;font-family:DM Mono,monospace;'                         'padding:.2rem .65rem;border-radius:999px;letter-spacing:.05em;">'                         '&#9679; ACTIVE</span>')
            elif sub_status == "cancelled":
                badge = ('<span style="background:#fffbeb;color:#d97706;border:1px solid #fde68a;'                         'font-size:.72rem;font-weight:700;font-family:DM Mono,monospace;'                         'padding:.2rem .65rem;border-radius:999px;letter-spacing:.05em;">'                         '&#9679; CANCELLED</span>')
            else:
                badge = ('<span style="background:#f8fafc;color:#64748b;border:1px solid #e2e8f0;'                         'font-size:.72rem;font-weight:700;font-family:DM Mono,monospace;'                         'padding:.2rem .65rem;border-radius:999px;letter-spacing:.05em;">'                         '&#9679; EXPIRED</span>')

            rows = [("Plan", f'<strong>{plan_label}</strong>', "#0f172a")]
            rows.append(("Status", badge, ""))
            if sub_status == "active":
                rows.append(("Next billing", f'{expires_fmt} &nbsp;·&nbsp; {plan_amount}/mo', "#0f172a"))
            elif sub_status == "cancelled":
                rows.append(("Access until", f'<strong style="color:#d97706;">{expires_fmt}</strong>', ""))
                rows.append(("Cancelled on", cancelled_fmt, "#64748b"))

            rows_html = '<table style="width:100%;border-collapse:collapse;">'
            for label, val, color in rows:
                color_style = f'color:{color};' if color else ""
                rows_html += (
                    f'<tr><td style="border:none;padding:.4rem 0;color:#64748b;'                    f'font-size:.82rem;width:40%;">{label}</td>'                    f'<td style="border:none;padding:.4rem 0;{color_style}'                    f'font-size:.85rem;text-align:right;">{val}</td></tr>'
                )
            rows_html += "</table>"
            st.markdown(rows_html, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # ── ACTIVE: cancel button ───────────────────────────────────
            if sub_status == "active":
                st.markdown("<div style='margin-top:.5rem;'>", unsafe_allow_html=True)
                if not st.session_state.get("_confirm_cancel"):
                    st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
                    if st.button("Cancel subscription", key="btn_cancel_init",
                                 use_container_width=False):
                        st.session_state["_confirm_cancel"] = True
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div class="vg-card" style="border:1.5px solid #fde68a;'                        'background:#fffbeb;">'                        '<div style="font-weight:700;color:#92400e;margin-bottom:.4rem;">'                        'Stop your subscription?</div>'                        '<div style="color:#78350f;font-size:.85rem;line-height:1.65;'                        'margin-bottom:.85rem;">Your plan stays active until '                        f'<strong>{expires_fmt}</strong>. After that your account returns '                        'to the Free tier automatically. Your verification history '                        'is never deleted.</div></div>',
                        unsafe_allow_html=True,
                    )
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        st.markdown('<div class="btn-red">', unsafe_allow_html=True)
                        if st.button("Yes, cancel renewal", key="btn_cancel_confirm",
                                     use_container_width=True):
                            with st.spinner("Cancelling…"):
                                ok, msg = cancel_subscription(uid, uemail, immediate=False)
                            st.session_state.pop("_confirm_cancel", None)
                            if ok:
                                st.success("Cancelled — access continues until " + expires_fmt)
                                st.rerun()
                            else:
                                st.error(f"Error: {msg}")
                        st.markdown("</div>", unsafe_allow_html=True)
                    with cc2:
                        st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
                        if st.button("Keep my subscription", key="btn_cancel_abort",
                                     use_container_width=True):
                            st.session_state.pop("_confirm_cancel", None)
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # ── CANCELLED: reactivate + end now ────────────────────────
            elif sub_status == "cancelled":
                st.markdown(
                    f'<div style="background:#fffbeb;border:1px solid #fde68a;'
                    f'border-radius:8px;padding:.75rem 1rem;margin:.6rem 0;'
                    f'font-size:.82rem;color:#78350f;line-height:1.6;">'
                    f'Your {plan_label} features stay active until '
                    f'<strong>{expires_fmt}</strong>. After that you\'ll be '
                    f'moved to the Free tier automatically.</div>',
                    unsafe_allow_html=True,
                )
                rc1, rc2 = st.columns([1.1, 1])
                with rc1:
                    st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
                    if st.button("Reactivate subscription", key="btn_reactivate",
                                 use_container_width=True):
                        if DB_OK:
                            try:
                                sb      = get_supabase_client()
                                now_iso = datetime.utcnow().isoformat() + "Z"
                                sb.table("user_profiles").upsert({
                                    "user_id":             uid,
                                    "email":               uemail,
                                    "subscription_status": "active",
                                    "cancelled_at":        None,
                                    "updated_at":          now_iso,
                                }, on_conflict="user_id").execute()
                                st.success("Reactivated — renewal will continue as normal.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not reactivate: {e}")
                        else:
                            st.warning("DB not connected.")
                    st.markdown("</div>", unsafe_allow_html=True)
                with rc2:
                    if not st.session_state.get("_confirm_immediate"):
                        st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
                        if st.button("End access now", key="btn_end_now_init",
                                     use_container_width=True):
                            st.session_state["_confirm_immediate"] = True
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(
                            '<div class="vg-card" style="border:1.5px solid #fecaca;'                            'background:#fef2f2;margin-top:.25rem;">'                            '<div style="font-weight:700;color:#991b1b;margin-bottom:.3rem;'                            'font-size:.85rem;">End access immediately?</div>'                            '<div style="color:#7f1d1d;font-size:.8rem;line-height:1.6;'                            'margin-bottom:.65rem;">You will be moved to the Free tier '                            'right now. No refund for remaining days.</div></div>',
                            unsafe_allow_html=True,
                        )
                        ia1, ia2 = st.columns(2)
                        with ia1:
                            st.markdown('<div class="btn-red">', unsafe_allow_html=True)
                            if st.button("Yes, end now", key="btn_end_now_confirm",
                                         use_container_width=True):
                                with st.spinner("Downgrading…"):
                                    ok, msg = cancel_subscription(uid, uemail, immediate=True)
                                st.session_state.pop("_confirm_immediate", None)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(f"Error: {msg}")
                            st.markdown("</div>", unsafe_allow_html=True)
                        with ia2:
                            st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
                            if st.button("Go back", key="btn_end_now_abort",
                                         use_container_width=True):
                                st.session_state.pop("_confirm_immediate", None)
                                st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)

        # ── RIGHT COL: Institutional upsell (Pro only) ─────────────────
        with upsell_col:
            if tier == "pro":
                inst_perks = [
                    ("20", "Team seats with individual logins"),
                    ("20", "API keys for newsroom integrations"),
                    ("20", "Bulk verify up to 20 claims at once"),
                    ("✓",  "White-label PDF & HTML reports"),
                    ("✓",  "Custom source watchlists & alerts"),
                    ("✓",  "Dedicated onboarding & SLA uptime"),
                ]
                st.markdown(
                    '<div class="vg-card" style="border:1.5px solid #bbf7d0;'                    'background:linear-gradient(160deg,#f0fdf4,#ffffff);">',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div style="font-family:DM Mono,monospace;font-size:.6rem;'                    'font-weight:700;letter-spacing:.1em;text-transform:uppercase;'                    'color:#15803d;margin-bottom:.5rem;">UPGRADE AVAILABLE</div>'                    '<div style="font-family:Syne,sans-serif;font-size:1.1rem;'                    'font-weight:800;color:#0f172a;letter-spacing:-.02em;'                    'margin-bottom:.2rem;">Institutional Plan</div>'                    '<div style="font-family:Syne,sans-serif;font-size:1.5rem;'                    'font-weight:800;color:#065f46;margin-bottom:.15rem;">$79.99'                    '<span style="font-size:.82rem;font-weight:400;color:#64748b;">/mo</span></div>'                    '<div style="color:#64748b;font-size:.78rem;margin-bottom:1rem;">'                    'For newsrooms, NGOs &amp; government agencies</div>',
                    unsafe_allow_html=True,
                )
                for stat, text in inst_perks:
                    st.markdown(
                        f'<div style="display:flex;align-items:flex-start;gap:.6rem;'                        f'padding:.4rem 0;border-bottom:1px solid #dcfce7;">'                        f'<span style="font-family:DM Mono,monospace;font-size:.72rem;'                        f'font-weight:700;color:#15803d;min-width:18px;'                        f'text-align:center;margin-top:.05rem;">{stat}</span>'                        f'<span style="color:#334155;font-size:.82rem;'                        f'line-height:1.5;">{text}</span></div>',
                        unsafe_allow_html=True,
                    )
                st.markdown("<div style='margin-top:1rem;'>", unsafe_allow_html=True)
                st.markdown('<div class="btn-green">', unsafe_allow_html=True)
                if st.button("Upgrade to Institutional →", key="upsell_inst",
                             use_container_width=True):
                    st.session_state.billing_plan = "institutional"
                    st.session_state.billing_step = "form"
                    st.session_state.page         = "billing"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                st.markdown(
                    '<div style="color:#64748b;font-size:.72rem;margin-top:.5rem;'                    'text-align:center;">Upgrade takes effect immediately</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("</div></div>", unsafe_allow_html=True)
    # ══════════════════════════════════════════════
    # PROMO CODE
    # ══════════════════════════════════════════════
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="vg-h3" style="margin-bottom:1rem;">Redeem Promo Code</div>',
                unsafe_allow_html=True)
    pc1, pc2 = st.columns([2.5, 1])
    with pc1:
        promo_val = st.text_input("", placeholder="GIMPA2026 · PRESS50 · NGOFREE30 · LAUNCH100",
                                   key="promo_val_in", label_visibility="collapsed")
    with pc2:
        st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
        if st.button("Apply Code", key="apply_promo", use_container_width=True):
            known = {
                "GIMPA2026": "50% off Pro — GIMPA students & staff",
                "PRESS50":   "50% off Pro — press & media",
                "NGOFREE30": "Free Pro for 30 days — NGOs",
                "LAUNCH100": "100% off first month",
            }
            match = known.get((promo_val or "").upper())
            if match: st.success(f"Valid: {match}")
            else:      st.error("Invalid or expired promo code.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Sign Out
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="btn-red" style="display:inline-block;">', unsafe_allow_html=True)
    if st.button("Sign Out", key="signout"):
        try:
            if DB_OK:
                get_supabase_client().auth.sign_out()
        except Exception:
            pass
        clear_session_cookie()   # deletes cookie, localStorage, and session keys
        init_state()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: ADMIN DASHBOARD
# ══════════════════════════════════════════════
def page_admin():
    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)
    st.markdown(
        '<div class="vg-page-head">'
        '<div class="vg-h1">Admin <em>Dashboard</em></div>'
        '<div class="vg-sub">Platform overview, support queue, payments, '
        'promo management and system controls.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Pre-load all data up front ────────────────────────────────────────
    articles = sources_count = 0
    payments_count = pro_count = inst_count = 0
    revenue_total = 0.0
    _tickets_all = []
    t_open = t_inprog = t_closed = 0
    _recent_pays = []

    if DB_OK:
        sb = get_supabase_client()
        try:
            articles      = sb.table("fact_entries").select("id", count="exact").execute().count or 0
            sources_count = sb.table("trusted_sources").select("id", count="exact").execute().count or 0
        except Exception: pass
        try:
            _pay_rows      = sb.table("payments").select("amount,plan_key").eq("status", "succeeded").execute().data or []
            payments_count = len(_pay_rows)
            revenue_total  = sum(float(r.get("amount", 0)) for r in _pay_rows)
            pro_count      = sum(1 for r in _pay_rows if r.get("plan_key") == "pro")
            inst_count     = sum(1 for r in _pay_rows if r.get("plan_key") == "institutional")
        except Exception: pass
        try:
            _recent_pays = (
                sb.table("payments")
                .select("order_ref,created_at,user_email,full_name,plan_label,"
                        "amount,currency,payment_method,status,email_sent,sms_sent,promo_code,country")
                .order("created_at", desc=True)
                .limit(50)
                .execute().data or []
            )
        except Exception: pass
        try:
            _tickets_all = (
                sb.table("support_tickets")
                .select("id,created_at,name,email,category,subject,message,status")
                .order("created_at", desc=True)
                .limit(100)
                .execute().data or []
            )
            t_open   = sum(1 for t in _tickets_all if t.get("status") == "open")
            t_inprog = sum(1 for t in _tickets_all if t.get("status") == "in_progress")
            t_closed = sum(1 for t in _tickets_all if t.get("status") in ("closed", "resolved"))
        except Exception: pass

    # ════════════════════════════════════════════════════════════════════
    # SECTION 1 — PLATFORM OVERVIEW  (two rows of KPI pills)
    # ════════════════════════════════════════════════════════════════════
    st.markdown(
        '<div class="vg-mono" style="margin-bottom:.75rem;">PLATFORM OVERVIEW</div>',
        unsafe_allow_html=True,
    )
    ov1, ov2, ov3, ov4 = st.columns(4)
    for _col, (_val, _lbl, _clr) in zip([ov1, ov2, ov3, ov4], [
        (f"{articles:,}",         "Articles Indexed",        "#2563eb"),
        (f"{sources_count:,}",    "Trusted Sources",          "#2563eb"),
        (f"${revenue_total:,.2f}","Total Revenue",            "#16a34a"),
        (f"{payments_count:,}",   "Successful Payments",      "#16a34a"),
    ]):
        with _col:
            st.markdown(
                f'<div class="spill">'
                f'<span class="spill-n" style="color:{_clr};">{_val}</span>'
                f'<span class="spill-l">{_lbl}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-top:.6rem;'>", unsafe_allow_html=True)
    ov5, ov6, ov7 = st.columns(3)
    for _col, (_val, _lbl, _clr) in zip([ov5, ov6, ov7], [
        (f"{pro_count:,}",            "Pro Subscribers",          "#7c3aed"),
        (f"{inst_count:,}",           "Institutional Subscribers","#7c3aed"),
        (f"{len(st.session_state.history)}", "Session Verifications","#64748b"),
    ]):
        with _col:
            st.markdown(
                f'<div class="spill">'
                f'<span class="spill-n" style="color:{_clr};">{_val}</span>'
                f'<span class="spill-l">{_lbl}</span></div>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════

    # SECTION 3 — PAYMENT RECORDS
    # ════════════════════════════════════════════════════════════════════
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown(
        '<div class="vg-h2" style="margin-bottom:.25rem;">Payment Records</div>'
        '<div class="vg-sub" style="margin-bottom:1.25rem;">'
        'All completed transactions. Most recent 50 shown.</div>',
        unsafe_allow_html=True,
    )

    rv1, rv2, rv3, rv4 = st.columns(4)
    for _col, (_val, _lbl, _clr) in zip([rv1, rv2, rv3, rv4], [
        (f"${revenue_total:,.2f}", "Total Revenue",            "#16a34a"),
        (f"{payments_count:,}",   "Successful Payments",       "#2563eb"),
        (f"{pro_count:,}",        "Pro Subscribers",           "#7c3aed"),
        (f"{inst_count:,}",       "Institutional Subscribers", "#d97706"),
    ]):
        with _col:
            st.markdown(
                f'<div class="spill">'
                f'<span class="spill-n" style="color:{_clr};">{_val}</span>'
                f'<span class="spill-l">{_lbl}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    if _recent_pays:
        _pay_html = ""
        for _p in _recent_pays:
            _dt     = (_p.get("created_at", "")[:16] or "—").replace("T", " ")
            _status = _p.get("status", "—")
            _sc     = "#16a34a" if _status == "succeeded" else "#dc2626"
            _ec     = "#16a34a" if _p.get("email_sent") else "#dc2626"
            _smc    = "#16a34a" if _p.get("sms_sent")   else "#dc2626"
            _pay_html += (
                f"<tr>"
                f"<td style='font-family:DM Mono,monospace;color:#2563eb;font-size:.76rem;"
                f"white-space:nowrap;'>{_p.get('order_ref','—')}</td>"
                f"<td style='color:#64748b;font-size:.76rem;white-space:nowrap;'>{_dt}</td>"
                f"<td style='font-size:.82rem;'>{_p.get('user_email','—')}</td>"
                f"<td style='font-size:.82rem;'>{_p.get('full_name','—')}</td>"
                f"<td style='font-size:.82rem;font-weight:600;'>{_p.get('plan_label','—')}</td>"
                f"<td style='color:#16a34a;font-weight:600;'>"
                f"${float(_p.get('amount',0)):.2f} {_p.get('currency','')}</td>"
                f"<td style='color:#64748b;font-size:.76rem;'>{_p.get('payment_method','—')}</td>"
                f"<td style='font-size:.76rem;'>"
                f"<span style='color:{_sc};font-weight:600;'>● {_status}</span></td>"
                f"<td style='color:#64748b;font-size:.76rem;'>{_p.get('promo_code') or '—'}</td>"
                f"<td style='color:{_ec};text-align:center;font-size:.85rem;'>"
                f"{'✓' if _p.get('email_sent') else '✗'}</td>"
                f"<td style='color:{_smc};text-align:center;font-size:.85rem;'>"
                f"{'✓' if _p.get('sms_sent') else '✗'}</td>"
                f"<td style='color:#64748b;font-size:.76rem;'>{_p.get('country','—')}</td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="vg-card" style="padding:0;overflow-x:auto;">'
            f'<table class="admin-table" style="min-width:1100px;">'
            f'<thead><tr>'
            f'<th>ORDER REF</th><th>DATE</th><th>EMAIL</th><th>NAME</th>'
            f'<th>PLAN</th><th>AMOUNT</th><th>METHOD</th><th>STATUS</th>'
            f'<th>PROMO</th><th>📧</th><th>📱</th><th>COUNTRY</th>'
            f'</tr></thead>'
            f'<tbody>{_pay_html}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="vg-card" style="text-align:center;padding:2rem;color:#64748b;">'
            'No payment records yet — they will appear here after the first upgrade.</div>',
            unsafe_allow_html=True,
        )

    # ════════════════════════════════════════════════════════════════════
    # SECTION 4 — PROMO CODES
    # ════════════════════════════════════════════════════════════════════
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown(
        '<div class="vg-h2" style="margin-bottom:.25rem;">Promo Codes</div>'
        '<div class="vg-sub" style="margin-bottom:1.25rem;">'
        'Active discount and unlock codes for campaigns.</div>',
        unsafe_allow_html=True,
    )

    promo_left, promo_right = st.columns([1.6, 1], gap="large")

    with promo_left:
        promos = [
            ("GIMPA2026", "Discount",    "50% off",  "200", "Active", "#16a34a"),
            ("PRESS50",   "Discount",    "50% off",   "50", "Active", "#16a34a"),
            ("NGOFREE30", "Tier Unlock", "Pro 30d",   "30", "Active", "#16a34a"),
            ("LAUNCH100", "Discount",    "100% off", "100", "Active", "#16a34a"),
        ]
        rows = ""
        for code, typ, disc, mx, status, sc in promos:
            rows += (
                f"<tr>"
                f"<td style='font-family:DM Mono,monospace;color:#2563eb;font-weight:700;'>{code}</td>"
                f"<td style='color:#334155;'>{typ}</td>"
                f"<td style='color:#334155;'>{disc}</td>"
                f"<td style='color:#64748b;'>0 / {mx}</td>"
                f"<td><span style='color:{sc};font-weight:600;'>● {status}</span></td>"
                f"</tr>"
            )
        st.markdown(
            f'<div class="vg-card" style="padding:0;overflow:hidden;">'
            f'<table class="admin-table">'
            f'<thead><tr><th>CODE</th><th>TYPE</th><th>DISCOUNT</th>'
            f'<th>USES</th><th>STATUS</th></tr></thead>'
            f'<tbody>{rows}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )

    with promo_right:
        st.markdown(
            '<div class="vg-mono" style="margin-bottom:.75rem;">CREATE PROMO CODE</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="vg-card">', unsafe_allow_html=True)
        np_code = st.text_input("Code", placeholder="NEWCODE2026", key="np_code")
        np_type = st.selectbox("Type", ["discount", "tier_unlock"], key="np_type")
        np_disc = st.slider("Discount %", 0, 100, 50, key="np_disc")
        np_max  = st.number_input("Max uses", 1, 10000, 100, key="np_max")
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Create Code", key="create_promo", use_container_width=True):
            if np_code:
                st.success(f"Code {np_code.upper()} created.")
            else:
                st.error("Enter a code name.")
        st.markdown('</div></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════

    st.markdown('</div></div>', unsafe_allow_html=True)



def page_tester():
    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)
    st.markdown("""
    <div class="vg-page-head">
      <div class="vg-h1">Site <em>Tester</em></div>
      <div class="vg-sub">
        Test Ghanaian sources for scrapability. Sites that pass are
        <strong style="color:#fff;">automatically added</strong> to
        <code style="color:#2563eb;background:rgba(37,99,235,.1);
        padding:.1rem .4rem;border-radius:4px;">html_scraper.py</code>.
      </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        from source_manager import get_scraper_source_count, get_existing_urls
        current_count = get_scraper_source_count()
        existing_urls = get_existing_urls()
    except ImportError:
        current_count = 0
        existing_urls = set()

    already_added = sum(1 for s in SITES_TO_TEST if s["url"] in existing_urls)
    m1,m2,m3,m4 = st.columns(4)
    for col,(val,lbl) in zip([m1,m2,m3,m4],[
        (len(SITES_TO_TEST),"Sites in Test List"),
        (already_added,"Already in Scraper"),
        (len(SITES_TO_TEST)-already_added,"Remaining to Test"),
        (current_count,"HTML_SOURCES Total"),
    ]):
        with col:
            st.markdown(f'<div class="spill"><span class="spill-n">{val}</span>'
                        f'<span class="spill-l">{lbl}</span></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
    with ctrl1:
        all_categories = sorted(set(s["category"] for s in SITES_TO_TEST))
        selected_cats  = st.multiselect(
            "Filter by Category", options=["All"] + all_categories,
            default=["All"], key="tst_cats",
        )
    with ctrl2:
        skip_existing = st.checkbox(
            "Skip sites already in html_scraper.py", value=True, key="tst_skip"
        )
        delay = st.slider("Delay between requests (s)", 0.5, 3.0, 1.0, 0.5, key="tst_delay")
    with ctrl3:
        st.write("")
        st.write("")
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        run_button = st.button("Run Tests", key="run_tst", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("Test a Custom URL"):
        c1, c2, c3 = st.columns([2, 2, 1])
        custom_name = c1.text_input("Site Name", placeholder="My News Site", key="c_name")
        custom_url  = c2.text_input("URL",       placeholder="https://example.com/news/", key="c_url")
        custom_cat  = c3.text_input("Category",  placeholder="Media", key="c_cat")
        if st.button("Test Custom URL", key="test_cu"):
            if custom_url.strip():
                with st.spinner(f"Testing {custom_url}..."):
                    result = test_single_site({
                        "name":     custom_name or custom_url,
                        "url":      custom_url.strip(),
                        "category": custom_cat or "Custom",
                    })
                if result["status"] == "scrapeable":
                    st.success(
                        f"Scrapeable — {result['count']} headlines via "
                        f"`{result['article_tag']}` / `{result['article_class']}`"
                    )
                    add_res = auto_add_to_scraper(result)
                    if add_res["skipped"]:   st.info(add_res["message"])
                    elif add_res["success"]: st.success(add_res["message"])
                    else:                    st.error(add_res["message"])
                    for s in result["samples"]:
                        st.write(f"  - [{s['text']}]({s['href']})")
                else:
                    icon = STATUS_ICON.get(result["status"],"?")
                    st.warning(f"{icon} {STATUS_LABEL.get(result['status'], result['status'])}")
            else:
                st.warning("Please enter a URL.")

    st.markdown("<hr>", unsafe_allow_html=True)

    if run_button:
        sites_to_run = []
        for site in SITES_TO_TEST:
            cat = site.get("category","")
            if "All" not in selected_cats and cat not in selected_cats:
                continue
            if skip_existing and site["url"] in existing_urls:
                continue
            sites_to_run.append(site)

        if not sites_to_run:
            st.info("No sites to test with current filters.")
        else:
            st.markdown(f"""
            <div class="vg-card-flat">
              <span class="vg-mono">Testing
                <span style="color:#fff;font-size:.9rem;font-weight:700;">{len(sites_to_run)}</span>
                sites — results appear live as each completes
              </span>
            </div>
            """, unsafe_allow_html=True)

            progress_bar  = st.progress(0)
            status_text   = st.empty()
            results_store = []

            sm1, sm2, sm3, sm4 = st.columns(4)
            cnt_s = sm1.empty(); cnt_n = sm2.empty()
            cnt_b = sm3.empty(); cnt_u = sm4.empty()

            def refresh_counters(results):
                s_c = sum(1 for r in results if r["status"]=="scrapeable")
                n_c = sum(1 for r in results if r["status"]=="no_headlines")
                b_c = sum(1 for r in results if r["status"]=="blocked")
                u_c = sum(1 for r in results if r["status"] not in
                          ["scrapeable","no_headlines","blocked"])
                cnt_s.markdown(f'<div class="spill"><span class="spill-n">{s_c}</span>'
                               f'<span class="spill-l">Scrapeable</span></div>',
                               unsafe_allow_html=True)
                cnt_n.markdown(f'<div class="spill"><span class="spill-n">{n_c}</span>'
                               f'<span class="spill-l">No Headlines</span></div>',
                               unsafe_allow_html=True)
                cnt_b.markdown(f'<div class="spill"><span class="spill-n">{b_c}</span>'
                               f'<span class="spill-l">Blocked</span></div>',
                               unsafe_allow_html=True)
                cnt_u.markdown(f'<div class="spill"><span class="spill-n">{u_c}</span>'
                               f'<span class="spill-l">Unreachable</span></div>',
                               unsafe_allow_html=True)

            refresh_counters([])
            results_container = st.container()

            for i, site in enumerate(sites_to_run):
                status_text.markdown(
                    f'<div class="vg-mono" style="color:#64748b;">'
                    f'Testing ({i+1}/{len(sites_to_run)}): {site["name"]} — '
                    f'<span style="color:#2563eb;">{site["url"]}</span></div>',
                    unsafe_allow_html=True,
                )
                result = test_single_site(site)
                results_store.append(result)

                add_msg = ""
                if result["status"] == "scrapeable":
                    add_res = auto_add_to_scraper(result)
                    if add_res["skipped"]:   add_msg = "_(already in html_scraper.py)_"
                    elif add_res["success"]: add_msg = "**Auto-added**"
                    else:                    add_msg = f"Could not add: {add_res['message']}"

                with results_container:
                    icon  = STATUS_ICON.get(result["status"],"?")
                    label = STATUS_LABEL.get(result["status"], result["status"])
                    if result["status"] == "scrapeable":
                        with st.expander(
                            f"{icon} {result['name']} — {result['count']} headlines  |  "
                            f"`{result['article_tag']}` / `{result['article_class']}`  {add_msg}",
                            expanded=False,
                        ):
                            st.markdown(f"""
                            <div style="color:#1e293b;font-size:.875rem;line-height:1.8;">
                              <strong>URL:</strong> {result['url']}<br>
                              <strong>Base URL:</strong> {result['base_url']}<br>
                              <strong>Category:</strong> {result['category']}
                            </div>
                            """, unsafe_allow_html=True)
                            st.write("**Sample Headlines:**")
                            for s in result["samples"]:
                                st.write(f"  - [{s['text']}]({s['href']})")
                            st.code(
                                f'{{\n'
                                f'    "name":          "{result["name"]}",\n'
                                f'    "url":           "{result["url"]}",\n'
                                f'    "article_tag":   "{result["article_tag"]}",\n'
                                f'    "article_class": "{result["article_class"]}",\n'
                                f'    "base_url":      "{result["base_url"]}"\n'
                                f'}},',
                                language="python",
                            )
                    else:
                        st.markdown(
                            f'<div style="padding:.5rem 0;color:#64748b;font-size:.875rem;">'
                            f'{icon} <strong style="color:#1e293b;">{result["name"]}</strong>'
                            f' — {label}</div>',
                            unsafe_allow_html=True,
                        )

                refresh_counters(results_store)
                progress_bar.progress((i + 1) / len(sites_to_run))
                time.sleep(delay)

            status_text.markdown(
                '<div class="vg-mono" style="color:#16a34a;">All tests complete.</div>',
                unsafe_allow_html=True,
            )
            st.session_state.test_results = results_store

    elif st.session_state.test_results:
        results = st.session_state.test_results
        sc_l = [r for r in results if r["status"]=="scrapeable"]
        nh_l = [r for r in results if r["status"]=="no_headlines"]
        bl_l = [r for r in results if r["status"]=="blocked"]
        un_l = [r for r in results if r["status"] not in ["scrapeable","no_headlines","blocked"]]

        st.markdown('<div class="vg-h3" style="margin-bottom:1rem;">Last Test Run</div>',
                    unsafe_allow_html=True)
        pm1,pm2,pm3,pm4 = st.columns(4)
        for col,(val,lbl) in zip([pm1,pm2,pm3,pm4],[
            (len(sc_l),"Scrapeable"),(len(nh_l),"No Headlines"),
            (len(bl_l),"Blocked"),  (len(un_l),"Unreachable"),
        ]):
            with col:
                st.markdown(f'<div class="spill"><span class="spill-n">{val}</span>'
                            f'<span class="spill-l">{lbl}</span></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        for result in results:
            icon  = STATUS_ICON.get(result["status"],"?")
            label = STATUS_LABEL.get(result["status"], result["status"])
            if result["status"] == "scrapeable":
                with st.expander(
                    f"{icon} {result['name']} — {result['count']} headlines  |  "
                    f"`{result['article_tag']}` / `{result['article_class']}`"
                ):
                    for s in result["samples"]:
                        st.write(f"  - [{s['text']}]({s['href']})")
            else:
                st.markdown(
                    f'<div style="padding:.4rem 0;color:#64748b;font-size:.875rem;">'
                    f'{icon} <strong style="color:#1e293b;">{result["name"]}</strong>'
                    f' — {label}</div>',
                    unsafe_allow_html=True,
                )

    # SECTION 5 — SYSTEM CONTROLS  (scraper + diagnostics at the bottom)
    # ════════════════════════════════════════════════════════════════════
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown(
        '<div class="vg-h2" style="margin-bottom:.25rem;">System Controls</div>'
        '<div class="vg-sub" style="margin-bottom:1.25rem;">'
        'Scraper pipeline triggers and AI provider diagnostics. '
        'Run these during off-peak hours.</div>',
        unsafe_allow_html=True,
    )

    # ── 5a. Scraper Controls
    st.markdown(
        '<div class="vg-mono" style="margin-bottom:.6rem;">SCRAPER PIPELINE</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="vg-card">', unsafe_allow_html=True)
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(
            '<div style="font-size:.82rem;font-weight:600;color:#0f172a;margin-bottom:.3rem;">'
            'RSS Scraper</div>'
            '<div style="color:#64748b;font-size:.75rem;margin-bottom:.65rem;">'
            'Fetches latest articles from RSS feeds of all indexed sources.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Run RSS Scraper", key="run_rss", use_container_width=True):
            with st.spinner("Running…"):
                try:
                    from scraper import run_scraper; run_scraper()
                    st.success("RSS scraper done.")
                except Exception as e: st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
    with sc2:
        st.markdown(
            '<div style="font-size:.82rem;font-weight:600;color:#0f172a;margin-bottom:.3rem;">'
            'HTML Scraper</div>'
            '<div style="color:#64748b;font-size:.75rem;margin-bottom:.65rem;">'
            'Crawls full article pages for sources without RSS support.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Run HTML Scraper", key="run_html", use_container_width=True):
            with st.spinner("Running…"):
                try:
                    from scrapers.html_scraper import run_html_ingestion
                    run_html_ingestion(); st.success("HTML scraper done.")
                except Exception as e: st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
    with sc3:
        st.markdown(
            '<div style="font-size:.82rem;font-weight:600;color:#0f172a;margin-bottom:.3rem;">'
            'Embedder</div>'
            '<div style="color:#64748b;font-size:.75rem;margin-bottom:.65rem;">'
            'Generates vector embeddings for new articles and indexes them.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Run Embedder", key="run_embed", use_container_width=True):
            with st.spinner("Running…"):
                try:
                    from embedder import run_embedder
                    run_embedder(); st.success("Embedder done.")
                except Exception as e: st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # vg-card

    # ── 5b. LLM Diagnostics
    st.markdown("<div style='margin-top:1.5rem;'>", unsafe_allow_html=True)
    st.markdown(
        '<div class="vg-mono" style="margin-bottom:.6rem;">LLM DIAGNOSTICS</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:#64748b;font-size:.82rem;margin-bottom:1rem;">'
        'Run live checks against each AI provider and Supabase. '
        'Tests: API reachability &nbsp;·&nbsp; DB index readable &nbsp;·&nbsp; '
        'Narrative from facts.</div>',
        unsafe_allow_html=True,
    )

    diag_col, btn_col = st.columns([3, 1])
    with diag_col:
        diag_claim = st.text_input(
            "Test claim",
            value="The government of Ghana has increased fuel prices",
            key="diag_claim",
            label_visibility="collapsed",
            help="Use a real claim you know exists in your database.",
        )
    with btn_col:
        run_diag = st.button("▶ Run Diagnostics", key="run_diag",
                             type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    def _badge(status, msg=""):
        cfg = {
            "PASS": ("#f0fdf4", "#15803d", "#bbf7d0", "PASS"),
            "FAIL": ("#fef2f2", "#dc2626", "#fecaca", "FAIL"),
            "SKIP": ("#f8fafc", "#64748b", "#e2e8f0", "SKIP"),
        }
        bg, fg, bd, lbl = cfg.get(status, cfg["SKIP"])
        detail = (f' <span style="color:#64748b;font-size:.74rem;">{msg}</span>'
                  if msg else "")
        return (f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
                f'padding:.2rem .65rem;border-radius:4px;font-size:.72rem;'
                f'font-family:DM Mono,monospace;font-weight:700;">{lbl}</span>{detail}')

    def _row(prov, check, status, detail=""):
        return (f"<tr><td style='color:#0f172a;font-weight:600;padding:.55rem .85rem;'>{prov}</td>"
                f"<td style='color:#64748b;padding:.55rem .85rem;'>{check}</td>"
                f"<td style='padding:.55rem .85rem;'>{_badge(status, detail)}</td></tr>")

    if run_diag:
        import re as _re, json as _json
        import requests as _req
        rows_html = ""
        full_log  = []

        def _safe_key(k):
            return (k or "").encode("ascii", errors="ignore").decode("ascii").strip()

        providers = [
            ("Gemini",     _safe_key(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")), "gemini"),
            ("Groq",       _safe_key(os.getenv("GROQ_API_KEY", "")),       "groq"),
            ("Cohere",     _safe_key(os.getenv("COHERE_API_KEY", "")),     "cohere"),
            ("OpenRouter", _safe_key(os.getenv("OPENROUTER_API_KEY", "")), "openrouter"),
        ]

        total_steps = len(providers) * 3 + 2
        step_n = [0]
        bar = st.progress(0, text="Starting diagnostics…")

        def _tick(msg=""):
            step_n[0] = min(step_n[0] + 1, total_steps)
            bar.progress(step_n[0] / total_steps, text=msg)

        _tick("Checking Supabase connection…")
        try:
            sb_d = get_supabase_client()
            cnt  = sb_d.table("fact_entries").select("id", count="exact").execute().count or 0
            rows_html += _row("Supabase", "1. Connection + row count", "PASS", f"{cnt:,} rows in fact_entries")
            full_log.append(f"[DB-CONNECT] PASS - {cnt:,} rows")
        except Exception as e:
            cnt = 0
            rows_html += _row("Supabase", "1. Connection + row count", "FAIL", str(e)[:80])
            full_log.append(f"[DB-CONNECT] FAIL - {e}")

        _tick("Testing keyword search…")
        db_results = []
        try:
            sb2   = get_supabase_client()
            probe = sb2.table("fact_entries").select("*").limit(1).execute()
            actual_cols = list(probe.data[0].keys()) if probe.data else []
            full_log.append(f"[DB-COLS] {actual_cols}")

            import re as _re2
            raw_words = [w.lower() for w in _re2.findall(r"[a-zA-Z]{3,}", diag_claim)]
            text_cols = [c for c in ["title", "content", "headline", "body", "text", "description"]
                         if c in actual_cols]

            for word in raw_words[:4]:
                for col in text_cols[:2]:
                    try:
                        hits = (sb2.table("fact_entries")
                                .select("*").ilike(col, f"%{word}%").limit(3).execute().data or [])
                        db_results.extend(hits)
                        if db_results:
                            break
                    except Exception:
                        pass
                if db_results:
                    break

            rows_html += _row("Supabase", "2. Keyword search", "PASS" if db_results else "FAIL",
                              f"{len(db_results)} matching articles found")
            full_log.append(f"[DB-SEARCH] {'PASS' if db_results else 'FAIL'} - {len(db_results)} results")
        except Exception as e:
            rows_html += _row("Supabase", "2. Keyword search", "FAIL", str(e)[:80])
            full_log.append(f"[DB-SEARCH] FAIL - {e}")

        narr_prompt = (
            f"You are a fact-checking engine for Ghana. Based on these articles: "
            f"{str(db_results[:3])[:600] if db_results else 'No articles found.'} "
            f"Evaluate: '{diag_claim}'. "
            f"Reply ONLY with valid JSON: "
            f'{{\"verdict\":\"VERIFIED|FALSE|PARTIAL|UNCORROBORATED\",'
            f'\"score\":0-100,\"summary\":\"one sentence\"}}'
        )

        for pname, akey, pkey in providers:
            _tick(f"Testing {pname}…")
            if not akey:
                rows_html += _row(pname, "1. API reachability", "SKIP", "No API key configured")
                rows_html += _row(pname, "2. DB index readable by model", "SKIP", "No API key")
                rows_html += _row(pname, "3. Narrative from facts", "SKIP", "No API key")
                full_log.append(f"[{pname.upper()}] SKIP - no key")
                continue

            ping     = "Reply with the single word: ONLINE"
            api_ok   = False
            api_msg  = "No response"

            try:
                if pkey == "gemini":
                    import google.generativeai as _gnai
                    _gnai.configure(api_key=akey)
                    resp = _gnai.GenerativeModel("gemini-2.0-flash").generate_content(
                        ping, generation_config={"max_output_tokens": 5, "temperature": 0})
                    api_ok  = bool(resp.text)
                    api_msg = f"gemini-2.0-flash responded"
                elif pkey == "groq":
                    r = _req.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json"},
                        json={"model": "llama-3.3-70b-versatile",
                              "messages": [{"role": "user", "content": ping}],
                              "max_tokens": 5, "temperature": 0},
                        timeout=15)
                    r.raise_for_status()
                    api_ok, api_msg = True, f"llama-3.3-70b-versatile (HTTP {r.status_code})"
                elif pkey == "cohere":
                    r = _req.post(
                        "https://api.cohere.com/v2/chat",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json",
                                 "Accept": "application/json"},
                        json={"model": "command-r-plus",
                              "messages": [{"role": "user", "content": ping}],
                              "max_tokens": 5, "temperature": 0},
                        timeout=15)
                    r.raise_for_status()
                    api_ok, api_msg = True, f"command-r-plus (HTTP {r.status_code})"
                elif pkey == "openrouter":
                    r = _req.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json",
                                 "HTTP-Referer": "https://verighana.gh", "X-Title": "VeriGhana"},
                        json={"model": "meta-llama/llama-3.3-70b-instruct:free",
                              "messages": [{"role": "user", "content": ping}],
                              "max_tokens": 5, "temperature": 0},
                        timeout=15)
                    r.raise_for_status()
                    api_ok, api_msg = True, f"llama-3.3-70b:free (HTTP {r.status_code})"
            except Exception as e:
                api_msg = str(e)[:90]

            rows_html += _row(pname, "1. API reachability", "PASS" if api_ok else "FAIL", api_msg)
            full_log.append(f"[{pname.upper()}-API] {'PASS' if api_ok else 'FAIL'} - {api_msg}")
            _tick(f"{pname}: narrative test…")

            if not api_ok:
                rows_html += _row(pname, "2. DB index readable by model", "SKIP", "API unreachable")
                rows_html += _row(pname, "3. Narrative from facts", "SKIP", "API unreachable")
                continue

            narr_ok = db_ok_flag = False
            narr_msg = db_msg = ""
            try:
                narr_raw = ""
                if pkey == "gemini":
                    import google.generativeai as _gnai2
                    _gnai2.configure(api_key=akey)
                    narr_raw = _gnai2.GenerativeModel("gemini-2.0-flash").generate_content(
                        narr_prompt, generation_config={"max_output_tokens": 400, "temperature": 0.1}
                    ).text
                elif pkey == "groq":
                    r2 = _req.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json"},
                        json={"model": "llama-3.3-70b-versatile",
                              "messages": [{"role": "system", "content": "Return only valid JSON."},
                                           {"role": "user", "content": narr_prompt}],
                              "max_tokens": 400, "temperature": 0.1,
                              "response_format": {"type": "json_object"}},
                        timeout=25)
                    r2.raise_for_status()
                    narr_raw = r2.json()["choices"][0]["message"]["content"]
                elif pkey == "cohere":
                    r2 = _req.post(
                        "https://api.cohere.com/v2/chat",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json",
                                 "Accept": "application/json"},
                        json={"model": "command-r-plus",
                              "messages": [{"role": "user", "content": narr_prompt}],
                              "max_tokens": 400, "temperature": 0.1},
                        timeout=25)
                    r2.raise_for_status()
                    d2 = r2.json()
                    narr_raw = (d2.get("message", {}).get("content", [{}])[0].get("text")
                                or d2.get("text", ""))
                elif pkey == "openrouter":
                    r2 = _req.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json",
                                 "HTTP-Referer": "https://verighana.gh", "X-Title": "VeriGhana"},
                        json={"model": "meta-llama/llama-3.3-70b-instruct:free",
                              "messages": [{"role": "user", "content": narr_prompt}],
                              "max_tokens": 400, "temperature": 0.1},
                        timeout=25)
                    r2.raise_for_status()
                    narr_raw = r2.json()["choices"][0]["message"]["content"]

                if narr_raw:
                    _clean = _re.sub(r"```(?:json)?", "", narr_raw).strip().rstrip("`")
                    _m3    = _re.search(r"\{.*\}", _clean, _re.DOTALL)
                    _obj   = _json.loads(_m3.group()) if _m3 else {}
                    summary = _obj.get("summary", "")
                    score   = _obj.get("score", "?")
                    verdict = _obj.get("verdict", "?")

                    if db_results and summary:
                        _sw = set(_re.findall(r"\b[A-Za-z]{5,}\b",
                                             " ".join(r.get("title", "") for r in db_results[:3])))
                        _nw = set(_re.findall(r"\b[A-Za-z]{5,}\b", narr_raw))
                        _ov = len(_sw & _nw)
                        db_ok_flag = _ov >= 3
                        db_msg = (f"Model references DB content ({_ov} shared keywords)"
                                  if db_ok_flag else f"Low keyword overlap ({_ov})")
                    elif summary:
                        db_ok_flag, db_msg = True, "Valid response (no DB sources to cross-check)"
                    else:
                        db_ok_flag, db_msg = False, "JSON missing summary field"

                    narr_ok  = bool(summary) and len(summary) > 20
                    narr_msg = (f"[{verdict} | {score}/100] {summary[:130]}…"
                                if narr_ok else f"Summary missing: {str(_obj)[:80]}")

            except Exception as e:
                db_msg = narr_msg = f"Error: {str(e)[:80]}"

            rows_html += _row(pname, "2. DB index readable by model",
                              "PASS" if db_ok_flag else "FAIL", db_msg)
            rows_html += _row(pname, "3. Narrative from facts",
                              "PASS" if narr_ok else "FAIL", narr_msg)
            full_log.append(f"[{pname.upper()}-DB]   {'PASS' if db_ok_flag else 'FAIL'} - {db_msg}")
            full_log.append(f"[{pname.upper()}-NARR] {'PASS' if narr_ok else 'FAIL'} - {narr_msg}")
            _tick(f"{pname} done.")

        bar.empty()

        st.markdown(
            f'<div class="vg-card" style="padding:0;overflow:hidden;margin-top:1rem;">'
            f'<table class="admin-table">'
            f'<thead><tr>'
            f'<th style="width:110px;">PROVIDER</th>'
            f'<th>CHECK</th>'
            f'<th>RESULT</th>'
            f'</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )

        with st.expander("Raw diagnostic log"):
            st.code("\n".join(full_log), language="text")

        passes = rows_html.count(">PASS<")
        fails  = rows_html.count(">FAIL<")
        skips  = rows_html.count(">SKIP<")
        if fails == 0:
            st.success(f"All checks passed — {passes} PASS, {skips} SKIP")
        else:
            st.warning(f"{fails} check(s) failed · {passes} passed · {skips} skipped")

    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: SUPPORT TICKETS  (admin only)
# ══════════════════════════════════════════════
def page_tickets():
    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)
    st.markdown(
        '<div class="vg-page-head">'
        '<div class="vg-h1">Support <em>Tickets</em></div>'
        '<div class="vg-sub">Review, reply and manage all user-submitted support requests.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── CSS scoped to this page ──────────────────────────────────────────
    st.markdown("""
<style>
/* Panel shells */
.tk-box {
    background:#fff;
    border:1px solid #e2e8f0;
    border-radius:10px;
    overflow:hidden;
    display:flex;
    flex-direction:column;
}
.tk-hd {
    padding:10px 14px;
    border-bottom:1px solid #e2e8f0;
    background:#f8fafc;
    flex-shrink:0;
}
.tk-hd-label {
    font-family:"DM Mono",monospace;
    font-size:.6rem;
    font-weight:700;
    letter-spacing:.1em;
    text-transform:uppercase;
    color:#64748b;
}
.tk-body { padding:14px; }

/* Ticket list */
.tk-list { max-height:600px; overflow-y:auto; }
.tk-row  {
    padding:10px 14px;
    border-bottom:1px solid #f1f5f9;
    transition:background .12s;
}
.tk-row:hover  { background:#f8fafc; }
.tk-row.sel    {
    background:#eff6ff;
    border-left:3px solid #2563eb;
    padding-left:11px;
}

/* Message bubble */
.tk-bubble {
    background:#f0f4ff;
    border-radius:0 10px 10px 10px;
    padding:12px 14px;
    font-size:.875rem;
    color:#1e293b;
    line-height:1.75;
    white-space:pre-wrap;
    margin:10px 0;
    border:1px solid #dbeafe;
}

/* Profile rows */
.tk-pr {
    display:flex;
    justify-content:space-between;
    padding:7px 0;
    border-bottom:1px solid #f1f5f9;
    font-size:.8rem;
}
.tk-pr:last-child { border:none; }

/* Compact Streamlit buttons inside ticket page only */
section.main div[data-testid="column"] .stButton>button {
    height:32px !important;
    min-height:32px !important;
    padding:0 14px !important;
    font-size:.78rem !important;
    font-weight:600 !important;
    border-radius:6px !important;
    line-height:1 !important;
}
section.main div[data-testid="column"] .stTextArea textarea {
    font-size:.875rem !important;
    line-height:1.7 !important;
}
section.main div[data-testid="column"] .stSelectbox>div {
    font-size:.8rem !important;
}
</style>
""", unsafe_allow_html=True)

    # ── Load all tickets ──────────────────────────────────────────────────
    _tickets_all = []
    t_open = t_inprog = t_closed = 0
    if DB_OK:
        try:
            _tickets_all = (
                get_supabase_client()
                .table("support_tickets")
                .select("id,created_at,name,email,category,subject,message,status")
                .order("created_at", desc=True)
                .limit(200)
                .execute().data or []
            )
            t_open   = sum(1 for t in _tickets_all if t.get("status") == "open")
            t_inprog = sum(1 for t in _tickets_all if t.get("status") == "in_progress")
            t_closed = sum(1 for t in _tickets_all if t.get("status") in ("closed","resolved"))
        except Exception as _te:
            st.warning(f"Could not load tickets: {_te}")
    else:
        st.info("Database not connected — showing empty state.")

    # ── KPI row ───────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    for _col, (_val, _lbl, _clr) in zip([k1,k2,k3,k4], [
        (len(_tickets_all), "Total",           "#2563eb"),
        (t_open,            "Open",            "#dc2626"),
        (t_inprog,          "In Progress",     "#d97706"),
        (t_closed,          "Resolved/Closed", "#16a34a"),
    ]):
        with _col:
            st.markdown(
                f'<div class="spill">'
                f'<span class="spill-n" style="color:{_clr};">{_val}</span>'
                f'<span class="spill-l">{_lbl}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-top:1rem;'>", unsafe_allow_html=True)

    # ── Helpers ──────────────────────────────────────────────────────────
    def _badge(status):
        cfg = {
            "open":        ("#fef2f2","#dc2626","#fecaca","Open"),
            "in_progress": ("#fffbeb","#d97706","#fde68a","In Progress"),
            "resolved":    ("#f0fdf4","#15803d","#bbf7d0","Resolved"),
            "closed":      ("#f8fafc","#475569","#e2e8f0","Closed"),
        }
        bg,fg,bd,lbl = cfg.get((status or "open").lower(), ("#f8fafc","#475569","#e2e8f0","?"))
        return (f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
                f'font-size:.65rem;font-weight:700;font-family:DM Mono,monospace;'
                f'padding:.2rem .6rem;border-radius:999px;">{lbl}</span>')

    def _ts(iso, short=False):
        if not iso: return "—"
        try:
            dt = datetime.fromisoformat(iso.replace("Z","+00:00"))
            return dt.strftime("%d %b %H:%M") if short else dt.strftime("%d %b %Y · %H:%M UTC")
        except Exception:
            return iso[:16].replace("T"," ")

    def _av(name, sz=32):
        palette = ["#2563eb","#7c3aed","#0891b2","#0d9488","#16a34a","#d97706"]
        bg = palette[ord((name or "?")[0].upper()) % len(palette)]
        return (f'<span style="display:inline-flex;align-items:center;'
                f'justify-content:center;width:{sz}px;height:{sz}px;'
                f'border-radius:50%;background:{bg};color:#fff;'
                f'font-weight:800;font-size:{int(sz*.42)}px;'
                f'font-family:Syne,sans-serif;flex-shrink:0;">'
                f'{(name or "?")[0].upper()}</span>')

    # ── Filter bar ───────────────────────────────────────────────────────
    sf1, sf2, sf3 = st.columns([1,1,2])
    with sf1:
        _fstat = st.selectbox("Status",
            ["All","Open","In Progress","Resolved","Closed"],
            key="tkt_fstat", label_visibility="collapsed")
    with sf2:
        _fcat = st.selectbox("Category",
            ["All categories","Billing & payments","Account & login",
             "API & integrations","Verification results",
             "Feature request","Bug report","Other"],
            key="tkt_fcat", label_visibility="collapsed")
    with sf3:
        _fsrch = st.text_input("Search",
            placeholder="Search name, email or subject…",
            key="tkt_srch", label_visibility="collapsed")

    # Apply filters
    _vis = list(_tickets_all)
    if _fstat != "All":
        slug = _fstat.lower().replace(" ","_")
        _vis = [t for t in _vis if (t.get("status") or "").lower().replace(" ","_") == slug]
    if _fcat != "All categories":
        _vis = [t for t in _vis if t.get("category","") == _fcat]
    if _fsrch:
        q = _fsrch.lower()
        _vis = [t for t in _vis if
                q in (t.get("name","") or "").lower() or
                q in (t.get("email","") or "").lower() or
                q in (t.get("subject","") or "").lower() or
                q in (t.get("message","") or "").lower()]

    if not _vis:
        st.markdown(
            '<div class="vg-card" style="text-align:center;padding:3.5rem;margin-top:.75rem;">'
            '<div style="font-size:2rem;margin-bottom:.5rem;">🎫</div>'
            '<div style="color:#64748b;font-size:.9rem;">No tickets match the current filters.</div>'
            '</div>',
            unsafe_allow_html=True)
        st.markdown('</div></div></div>', unsafe_allow_html=True)
        return

    # ── Selection state — keyed by ticket ID ─────────────────────────────
    if "tkt_sel_id" not in st.session_state:
        st.session_state.tkt_sel_id = _vis[0].get("id","")
    if st.session_state.tkt_sel_id not in [t.get("id","") for t in _vis]:
        st.session_state.tkt_sel_id = _vis[0].get("id","")

    sel = next((t for t in _vis if t.get("id","") == st.session_state.tkt_sel_id), _vis[0])

    st.markdown(
        f'<div style="color:#64748b;font-size:.75rem;margin-bottom:.6rem;">'
        f'Showing <strong>{len(_vis)}</strong> of {len(_tickets_all)} ticket(s)</div>',
        unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    # THREE PANELS
    # ════════════════════════════════════════════════════════════
    col_list, col_detail, col_persona = st.columns([1, 2.1, 1.1], gap="small")

    sicons = {"open":"●","in_progress":"◑","resolved":"✓","closed":"○"}
    sclrs  = {"open":"#dc2626","in_progress":"#d97706","resolved":"#16a34a","closed":"#94a3b8"}

    # ── PANEL 1: list ────────────────────────────────────────────
    with col_list:
        st.markdown(
            f'<div class="tk-box" style="height:680px;">'
            f'<div class="tk-hd" style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span class="tk-hd-label">All Tickets</span>'
            f'<span style="background:#e2e8f0;color:#475569;font-family:DM Mono,monospace;'
            f'font-size:.6rem;font-weight:700;padding:.1rem .45rem;border-radius:999px;">'
            f'{len(_vis)}</span>'
            f'</div>'
            f'<div class="tk-list">',
            unsafe_allow_html=True,
        )
        for tk in _vis:
            tid_i   = tk.get("id","")
            is_sel  = tid_i == st.session_state.tkt_sel_id
            ts_i    = (tk.get("status") or "open").lower()
            subj_i  = tk.get("subject","(no subject)")
            name_i  = tk.get("name","Unknown")
            ts_str  = _ts(tk.get("created_at",""), short=True)
            sel_cls = " sel" if is_sel else ""

            st.markdown(
                f'<div class="tk-row{sel_cls}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;">'
                f'<span style="font-family:DM Mono,monospace;font-size:.6rem;color:#2563eb;font-weight:700;">'
                f'#{str(tid_i)[:7].upper()}</span>'
                f'<span style="font-size:.62rem;color:#94a3b8;">{ts_str}</span>'
                f'</div>'
                f'<div style="font-size:.8rem;font-weight:600;color:#0f172a;line-height:1.35;margin-bottom:2px;">'
                f'<span style="color:{sclrs.get(ts_i,"#94a3b8")};font-size:.7rem;">{sicons.get(ts_i,"●")}</span>'
                f' {subj_i[:34]}{"…" if len(subj_i)>34 else ""}'
                f'</div>'
                f'<div style="font-size:.7rem;color:#64748b;">{name_i}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("View", key=f"tkt_view_{tid_i}", use_container_width=True):
                st.session_state.tkt_sel_id = tid_i
                st.rerun()

        st.markdown('</div></div>', unsafe_allow_html=True)

    # ── PANEL 2: detail + reply ──────────────────────────────────
    with col_detail:
        tid    = sel.get("id","")
        tname  = sel.get("name","Unknown")
        temail = sel.get("email","—")
        tsubj  = sel.get("subject","(no subject)")
        tmsg   = sel.get("message","")
        tstat  = (sel.get("status") or "open").lower()
        tts    = _ts(sel.get("created_at",""))
        tcat   = sel.get("category","Other")
        tid_s  = str(tid)[:7].upper() or "——"

        st.markdown(
            f'<div class="tk-box" style="height:680px;">'
            # header
            f'<div class="tk-hd" style="display:flex;justify-content:space-between;align-items:flex-start;">'
            f'<div style="min-width:0;">'
            f'<div class="tk-hd-label">Ticket Details</div>'
            f'<div style="font-size:.88rem;font-weight:700;color:#0f172a;margin-top:3px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:340px;">'
            f'#{tid_s} — {tsubj}'
            f'</div>'
            f'</div>'
            f'{_badge(tstat)}'
            f'</div>'
            # sender meta
            f'<div style="padding:12px 14px 0;display:flex;align-items:center;gap:8px;'
            f'font-size:.75rem;color:#64748b;flex-wrap:wrap;">'
            f'{_av(tname, 26)}'
            f'<strong style="color:#334155;">{tname}</strong>'
            f'<a href="mailto:{temail}" style="color:#2563eb;text-decoration:none;">{temail}</a>'
            f'<span style="color:#cbd5e1;">·</span>'
            f'<span>{tts}</span>'
            f'</div>'
            f'<div style="padding:4px 14px 10px;">'
            f'<span style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;'
            f'font-size:.6rem;font-weight:600;font-family:DM Mono,monospace;'
            f'padding:.15rem .5rem;border-radius:999px;">{tcat}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # message bubble
        st.markdown(
            f'<div style="padding:0 14px;flex:1;overflow-y:auto;">'
            f'<div class="tk-bubble">{tmsg}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # divider + reply area
        st.markdown(
            '<div style="border-top:1px solid #e2e8f0;padding:12px 14px 14px;">'
            '<div class="tk-hd-label" style="margin-bottom:6px;">Agent Reply</div>',
            unsafe_allow_html=True,
        )

        reply_txt = st.text_area(
            "Reply", key=f"tkt_reply_{tid}",
            placeholder="Write your reply — it will be emailed to the user immediately…",
            height=110, label_visibility="collapsed",
        )

        rb1, rb2 = st.columns([1,1])
        with rb1:
            if st.button("✉  Send Reply", key=f"tkt_send_{tid}",
                         type="primary", use_container_width=True):
                if not (reply_txt or "").strip():
                    st.warning("Write something before sending.")
                else:
                    with st.spinner("Sending email…"):
                        ok, msg = _send_support_reply(
                            to_email  = temail,
                            to_name   = tname,
                            subject   = tsubj,
                            body      = reply_txt.strip(),
                            ticket_id = tid_s,
                        )
                    if ok:
                        if DB_OK and tid and tstat == "open":
                            try:
                                get_supabase_client().table("support_tickets").update({"status": "in_progress", "updated_at": datetime.utcnow().isoformat() + "Z"}).eq("id", tid).execute()
                            except Exception: pass
                        st.success(f"✓ {msg}")
                        st.rerun()
                    else:
                        st.error(msg)
        with rb2:
            s_opts  = ["open","in_progress","resolved","closed"]
            s_lbls  = ["Open","In Progress","Resolved","Closed"]
            cur_i   = s_opts.index(tstat) if tstat in s_opts else 0
            new_s   = st.selectbox("Status", s_lbls, index=cur_i,
                                   key=f"tkt_stat_{tid}", label_visibility="collapsed")
            if s_lbls[cur_i] != new_s and DB_OK and tid:
                try:
                    get_supabase_client().table("support_tickets").update({"status": s_opts[s_lbls.index(new_s)], "updated_at": datetime.utcnow().isoformat() + "Z"}).eq("id", tid).execute()
                    st.rerun()
                except Exception as _e:
                    st.error(str(_e))

        st.markdown('</div></div>', unsafe_allow_html=True)

    # ── PANEL 3: reporter + actions ──────────────────────────────
    with col_persona:
        tname  = sel.get("name","Unknown")
        temail = sel.get("email","—")
        tstat  = (sel.get("status") or "open").lower()
        tid    = sel.get("id","")

        # Fetch user profile
        _up = {}
        if DB_OK and temail not in ("","—"):
            try:
                _r = (get_supabase_client()
                      .table("user_profiles")
                      .select("tier,subscription_status,country")
                      .eq("email", temail).limit(1).execute().data or [])
                _up = _r[0] if _r else {}
            except Exception: pass

        u_tier    = _up.get("tier","free").capitalize()
        u_sub     = (_up.get("subscription_status") or "—").replace("_"," ").title()
        u_country = _up.get("country","—")
        t_clr     = {"Free":"#64748b","Pro":"#2563eb","Institutional":"#16a34a"}.get(u_tier,"#64748b")
        related   = [t for t in _tickets_all if t.get("email") == temail and t.get("id") != tid]

        st.markdown(
            '<div class="tk-box" style="height:680px;">'
            '<div class="tk-hd"><span class="tk-hd-label">Reporter</span></div>'
            '<div class="tk-body" style="overflow-y:auto;flex:1;">',
            unsafe_allow_html=True,
        )

        # Avatar + name/email
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
            f'{_av(tname, 42)}'
            f'<div style="min-width:0;">'
            f'<div style="font-weight:700;color:#0f172a;font-size:.88rem;">{tname}</div>'
            f'<a href="mailto:{temail}" style="color:#2563eb;font-size:.72rem;'
            f'text-decoration:none;word-break:break-all;">{temail}</a>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # Profile rows
        for lbl, val in [
            ("Plan",     f'<span style="color:{t_clr};font-weight:700;">{u_tier}</span>'),
            ("Billing",  u_sub),
            ("Location", u_country),
            ("Other tickets",
             f'<span style="color:#2563eb;font-weight:600;">{len(related)}</span>'
             if related else "None"),
        ]:
            st.markdown(
                f'<div class="tk-pr">'
                f'<span style="color:#64748b;">{lbl}</span>'
                f'<span style="color:#0f172a;">{val}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Quick actions
        st.markdown(
            '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #f1f5f9;">'
            '<div class="tk-hd-label" style="margin-bottom:8px;">Quick Actions</div>',
            unsafe_allow_html=True,
        )
        qa1, qa2 = st.columns(2)
        with qa1:
            lbl_r = "✓ Resolve" if tstat not in ("resolved","closed") else "↩ Reopen"
            key_r = f"tkt_resolve_{tid}"
            if st.button(lbl_r, key=key_r, use_container_width=True):
                new_stat = "open" if tstat in ("resolved","closed") else "resolved"
                if DB_OK and tid:
                    try:
                        get_supabase_client().table("support_tickets").update({"status": new_stat, "updated_at": datetime.utcnow().isoformat() + "Z"}).eq("id", tid).execute()
                        st.rerun()
                    except Exception as _e: st.error(str(_e))
        with qa2:
            if st.button("⚑ Escalate", key=f"tkt_esc_{tid}", use_container_width=True):
                st.toast("Ticket marked for escalation.", icon="⚑")
        st.markdown('</div>', unsafe_allow_html=True)

        # Related tickets
        if related:
            st.markdown(
                '<div style="margin-top:14px;padding-top:12px;border-top:1px solid #f1f5f9;">'
                '<div class="tk-hd-label" style="margin-bottom:8px;">Related Tickets</div>',
                unsafe_allow_html=True,
            )
            for rt in related[:6]:
                rt_s  = (rt.get("status") or "open").lower()
                rt_id = str(rt.get("id",""))[:7].upper()
                rt_sub = (rt.get("subject") or "—")[:28]
                st.markdown(
                    f'<div style="padding:5px 0;border-bottom:1px solid #f8fafc;font-size:.75rem;">'
                    f'<span style="color:{sclrs.get(rt_s,"#94a3b8")};">{sicons.get(rt_s,"●")}</span> '
                    f'<span style="color:#2563eb;font-family:DM Mono,monospace;font-size:.65rem;">'
                    f'#{rt_id}</span> '
                    f'<span style="color:#475569;">{rt_sub}{"…" if len(rt_sub)==28 else ""}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("View", key=f"tkt_rel_view_{rt.get('id','')}",
                             use_container_width=True):
                    st.session_state.tkt_sel_id = rt.get("id","")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  MAIN ROUTER
# ══════════════════════════════════════════════
#  NOTIFICATIONS  (email via SendGrid + SMS via Africa's Talking)
# ══════════════════════════════════════════════

def _email_html(plan_label: str, amount: float, name: str,
                order_ref: str, email: str) -> str:
    """Render a branded HTML confirmation email."""
    features = {
        "Pro Plan": [
            "Unlimited daily verifications",
            "All 4 AI models (Gemini, Groq, Cohere, OpenRouter)",
            "3 REST API keys for integrations",
            "CSV export & real-time alert webhooks",
            "Priority model queue — no delays",
        ],
        "Institutional Plan": [
            "Everything in Pro",
            "20 team seats & 20 API keys",
            "Bulk verify up to 20 claims at once",
            "White-label PDF/HTML reports",
            "SLA-backed uptime & dedicated support",
        ],
    }.get(plan_label, [])

    feat_rows = "".join(
        f'<tr><td style="padding:5px 0;color:#1e293b;font-size:14px;">' 
        f'<span style="color:#2563eb;margin-right:8px;">✓</span>{f}</td></tr>'
        for f in features
    )
    amount_str = f"${amount:.2f}" if amount > 0 else "FREE (promo applied)"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#f8fafc;padding:40px 20px;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;
                    border:1px solid rgba(255,255,255,0.08);overflow:hidden;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#1e3a8a,#1d4ed8);
                        padding:32px 40px;text-align:center;">
          <div style="font-family:Georgia,serif;font-weight:900;font-size:26px;
                      color:#fff;letter-spacing:-0.5px;">
            Veri<span style="color:#1d4ed8;">Ghana</span>
          </div>
          <div style="color:rgba(255,255,255,0.6);font-size:12px;
                      margin-top:4px;letter-spacing:1px;text-transform:uppercase;">
            National Fact Verification Platform
          </div>
        </td></tr>

        <!-- Success banner -->
        <tr><td style="padding:28px 40px 0;text-align:center;">
          <div style="font-size:40px;margin-bottom:12px;">🎉</div>
          <div style="font-size:22px;font-weight:700;color:#fff;margin-bottom:8px;">
            Payment Confirmed!
          </div>
          <div style="color:#64748b;font-size:15px;line-height:1.6;">
            Welcome to <strong style="color:#2563eb;">{plan_label}</strong>, {name}.<br>
            Your new features are active immediately.
          </div>
        </td></tr>

        <!-- Order details box -->
        <tr><td style="padding:24px 40px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:rgba(255,255,255,0.04);border-radius:10px;
                        border:1px solid rgba(255,255,255,0.08);padding:20px;">
            <tr><td colspan="2"
                    style="font-size:11px;color:#64748b;letter-spacing:1px;
                           text-transform:uppercase;padding-bottom:12px;
                           border-bottom:1px solid rgba(255,255,255,0.06);">
              ORDER SUMMARY
            </td></tr>
            <tr><td style="padding:10px 0 4px;color:#64748b;font-size:13px;">Order reference</td>
                <td style="padding:10px 0 4px;color:#1e293b;font-size:13px;
                           text-align:right;font-family:monospace;">{order_ref}</td></tr>
            <tr><td style="padding:4px 0;color:#64748b;font-size:13px;">Plan</td>
                <td style="padding:4px 0;color:#1e293b;font-size:13px;
                           text-align:right;">{plan_label}</td></tr>
            <tr><td style="padding:4px 0;color:#64748b;font-size:13px;">Billed to</td>
                <td style="padding:4px 0;color:#1e293b;font-size:13px;
                           text-align:right;">{email}</td></tr>
            <tr><td style="padding:8px 0 0;border-top:1px solid rgba(255,255,255,0.06);
                           color:#fff;font-size:15px;font-weight:700;">
              Total charged
            </td>
                <td style="padding:8px 0 0;border-top:1px solid rgba(255,255,255,0.06);
                           color:#2563eb;font-size:15px;font-weight:700;text-align:right;">
              {amount_str}
            </td></tr>
          </table>
        </td></tr>

        <!-- Features included -->
        <tr><td style="padding:0 40px 24px;">
          <div style="font-size:11px;color:#64748b;letter-spacing:1px;
                      text-transform:uppercase;margin-bottom:12px;">
            WHAT'S INCLUDED
          </div>
          <table width="100%" cellpadding="0" cellspacing="0">
            {feat_rows}
          </table>
        </td></tr>

        <!-- CTA -->
        <tr><td style="padding:0 40px 32px;text-align:center;">
          <a href="https://verighana.gh"
             style="display:inline-block;background:#2563eb;color:#fff;
                    font-weight:700;font-size:15px;padding:13px 32px;
                    border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
            Start Verifying →
          </a>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:rgba(0,0,0,0.3);padding:20px 40px;text-align:center;">
          <div style="color:#334155;font-size:12px;line-height:1.7;">
            Questions? Email us at
            <a href="mailto:support@verighana.gh"
               style="color:#2563eb;">support@verighana.gh</a><br>
            VeriGhana © 2026 — GIMPA Computer Science Research<br>
            <span style="color:#1e293b;">You can cancel anytime from your Account page.</span>
          </div>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_confirmation_email(to_email: str, to_name: str,
                             plan_key: str, amount: float,
                             order_ref: str) -> tuple:
    """
    Send a branded HTML confirmation email via SendGrid.
    Returns (success: bool, message: str).
    Falls back gracefully if SendGrid is not configured.
    """
    if not SENDGRID_API_KEY:
        return False, "SENDGRID_API_KEY not configured — email not sent."

    plan_label = _PLANS.get(plan_key, {}).get("label", plan_key.title())
    html_body  = _email_html(plan_label, amount, to_name, order_ref, to_email)
    text_body  = (
        f"VeriGhana — Payment Confirmed\n"
        f"Order: {order_ref}\n"
        f"Plan: {plan_label}\n"
        f"Amount: ${amount:.2f}\n"
        f"Your features are active. Visit https://verighana.gh"
    )

    payload = {
        "personalizations": [{"to": [{"email": to_email, "name": to_name}]}],
        "from": {"email": NOTIFY_FROM_EMAIL, "name": NOTIFY_FROM_NAME},
        "subject": f"VeriGhana — Your {plan_label} is active 🎉",
        "content": [
            {"type": "text/plain", "value": text_body},
            {"type": "text/html",  "value": html_body},
        ],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=10,
        )
        if resp.status_code in (200, 202):
            return True, "Email sent."
        return False, f"SendGrid error {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, f"Email exception: {exc}"


def send_confirmation_sms(phone: str, plan_key: str,
                           amount: float, order_ref: str) -> tuple:
    """
    Send an SMS confirmation via Africa's Talking.
    Returns (success: bool, message: str).
    Falls back gracefully if AT is not configured.
    """
    if not AT_USERNAME or not AT_API_KEY:
        return False, "AT_USERNAME / AT_API_KEY not configured — SMS not sent."

    plan_label = _PLANS.get(plan_key, {}).get("label", plan_key.title())
    amount_str = f"${amount:.2f}" if amount > 0 else "FREE"
    sms_text   = (
        f"VeriGhana: Payment of {amount_str} confirmed! "
        f"Your {plan_label} is now active. "
        f"Ref: {order_ref}. "
        f"Questions? support@verighana.gh"
    )

    # Normalise phone to E.164 (+233...)
    phone_clean = phone.strip().replace(" ", "").replace("-", "")
    if phone_clean.startswith("0") and len(phone_clean) == 10:
        phone_clean = "+233" + phone_clean[1:]  # Ghana local → E.164
    elif not phone_clean.startswith("+"):
        phone_clean = "+" + phone_clean

    try:
        resp = requests.post(
            "https://api.africastalking.com/version1/messaging",
            headers={
                "apiKey":       AT_API_KEY,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept":       "application/json",
            },
            data={
                "username": AT_USERNAME,
                "to":       phone_clean,
                "message":  sms_text,
                "from":     "VeriGhana",
            },
            timeout=10,
        )
        body = resp.json()
        recipients = body.get("SMSMessageData", {}).get("Recipients", [])
        if recipients and recipients[0].get("status") == "Success":
            return True, "SMS sent."
        return False, f"AT response: {body}"
    except Exception as exc:
        return False, f"SMS exception: {exc}"


# ── Card IIN/BIN prefix rules ─────────────────────────────────
# Each entry: (name, label, bg_colour, text_colour, cvv_len, accepted_lengths, prefixes)
# Prefixes are matched longest-first so 4917 beats 4.
_CARD_NETWORKS = [
    # Verve (must come before Visa — starts with 5061, 6500 etc.)
    ("verve",     "Verve",        "#009933", "#fff", 3, [16, 19],
     ["5061", "5062", "5063", "6500", "6501", "6502", "6503", "6504",
      "6505", "6506", "6507", "6508", "6509", "650", "6500"]),
    # American Express
    ("amex",      "Amex",         "#007bc1", "#fff", 4, [15],
     ["34", "37"]),
    # Mastercard (2-series and 5-series)
    ("mastercard","Mastercard",   "#eb001b", "#fff", 3, [16],
     ["51","52","53","54","55",
      "2221","2222","2223","2224","2225","2226","2227","2228","2229",
      "223","224","225","226","227","228","229",
      "23","24","25","26",
      "270","271","2720"]),
    # Visa
    ("visa",      "Visa",         "#1a1f71", "#fff", 3, [13, 16, 19],
     ["4"]),
    # UnionPay (must come before Discover — 622 prefix overlaps)
    ("unionpay",  "UnionPay",     "#e31837", "#fff", 3, [16, 17, 18, 19],
     ["62"]),
    # Discover (6011, 644-649, 65 — NOT 622 which belongs to UnionPay)
    ("discover",  "Discover",     "#f76f20", "#fff", 3, [16, 19],
     ["6011","644","645","646","647","648","649","65"]),
    # GhIPSS (Ghana domestic)
    ("ghipss",    "GhIPSS",       "#006633", "#fff", 3, [16],
     ["627117","627118"]),
    # Diners Club
    ("diners",    "Diners",       "#004b87", "#fff", 3, [14],
     ["300","301","302","303","304","305","36","38"]),
    # JCB
    ("jcb",       "JCB",          "#003087", "#fff", 3, [16],
     ["3528","3529","353","354","355","356","357","358"]),
]

def _detect_card(raw: str):
    """
    Given raw card number digits, return detected network dict or None.
    Tries longest prefix first so Verve beats generic Visa/MC prefixes.
    Returns dict with keys: id, label, bg, fg, cvv_len, lengths, max_len
    """
    digits = "".join(c for c in (raw or "") if c.isdigit())
    if not digits:
        return None
    # Sort all (prefix, network) pairs by prefix length descending
    candidates = []
    for net in _CARD_NETWORKS:
        nid, lbl, bg, fg, cvv_len, lengths, prefixes = net
        for pfx in prefixes:
            candidates.append((pfx, nid, lbl, bg, fg, cvv_len, lengths))
    candidates.sort(key=lambda x: -len(x[0]))
    for pfx, nid, lbl, bg, fg, cvv_len, lengths in candidates:
        if digits.startswith(pfx):
            return {
                "id": nid, "label": lbl, "bg": bg, "fg": fg,
                "cvv_len": cvv_len, "lengths": lengths,
                "max_len": max(lengths),
            }
    return None


def _fmt_card_num(raw: str, network: Optional[dict]) -> str:
    """Format card digits with spaces. Amex: 4-6-5. Others: groups of 4."""
    digits = "".join(c for c in raw if c.isdigit())
    if network and network["id"] == "amex":
        parts = [digits[:4], digits[4:10], digits[10:15]]
        return "  ".join(p for p in parts if p)
    # Groups of 4
    return "  ".join(digits[i:i+4] for i in range(0, len(digits), 4) if digits[i:i+4])


def _mock_process_payment(method: str, card_num: str = "",
                            momo_num: str = "",
                            card_issuer: str = "") -> tuple:
    """
    Mock payment processor — accepts any card with correct prefix+length.
    Returns (success: bool, order_ref: str, message: str).
    """
    import random, string
    time.sleep(0.8)
    ref = "VG-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    issuer_note = f" via {card_issuer}" if card_issuer else ""
    return True, ref, f"Payment authorised (mock{issuer_note})"


# ── Subscription helpers ──────────────────────────────────────────────────

def get_subscription_info(user_id: str) -> dict:
    """
    Fetch the current subscription row from user_profiles.
    Returns a dict with keys: tier, subscription_status,
    subscription_expires_at, cancelled_at  — or safe defaults.
    """
    defaults = {
        "tier":                     st.session_state.get("user_tier", "free"),
        "subscription_status":      "free",
        "subscription_expires_at":  None,
        "cancelled_at":             None,
    }
    if not DB_OK or not user_id or user_id == "admin-001":
        return defaults
    try:
        sb  = get_supabase_client()
        row = (sb.table("user_profiles")
                 .select("tier,subscription_status,subscription_expires_at,cancelled_at")
                 .eq("user_id", user_id)
                 .maybe_single()
                 .execute())
        if row and row.data:
            return {**defaults, **{k: v for k, v in row.data.items() if v is not None}}
    except Exception:
        pass
    return defaults


def cancel_subscription(user_id: str, user_email: str,
                        immediate: bool = False) -> tuple:
    """
    Cancel a subscription.
    immediate=False  -> stop renewal, keep access until subscription_expires_at
    immediate=True   -> drop tier to free right now

    Returns (success: bool, message: str)
    """
    if not DB_OK:
        return False, "Supabase not connected."
    try:
        sb      = get_supabase_client()
        now_iso = datetime.utcnow().isoformat() + "Z"

        if immediate:
            sb.table("user_profiles").upsert({
                "user_id":                   user_id,
                "email":                     user_email,
                "tier":                      "free",
                "subscription_status":       "expired",
                "cancelled_at":              now_iso,
                "updated_at":                now_iso,
            }, on_conflict="user_id").execute()
            st.session_state.user_tier = "free"
            return True, "Access ended. You have been moved to the Free tier."
        else:
            sb.table("user_profiles").upsert({
                "user_id":                   user_id,
                "email":                     user_email,
                "subscription_status":       "cancelled",
                "cancelled_at":              now_iso,
                "updated_at":                now_iso,
            }, on_conflict="user_id").execute()
            return True, "Subscription cancelled. Your access continues until the expiry date."
    except Exception as exc:
        return False, f"Cancellation error: {exc}"


def _expire_if_due(user_id: str, user_email: str, sub_info: dict) -> bool:
    """
    Called at page load — if status=cancelled and expiry has passed,
    automatically downgrades the user to free.
    Returns True if a downgrade happened.
    """
    if sub_info.get("subscription_status") not in ("cancelled", "active"):
        return False
    exp = sub_info.get("subscription_expires_at")
    if not exp:
        return False
    try:
        from datetime import timezone
        exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < exp_dt:
            return False
    except Exception:
        return False

    if DB_OK:
        try:
            sb      = get_supabase_client()
            now_iso = datetime.utcnow().isoformat() + "Z"
            sb.table("user_profiles").upsert({
                "user_id":               user_id,
                "email":                 user_email,
                "tier":                  "free",
                "subscription_status":   "expired",
                "updated_at":            now_iso,
            }, on_conflict="user_id").execute()
        except Exception:
            pass
    st.session_state.user_tier = "free"
    return True

def save_payment_to_db(
    order_ref:   str,
    user_id:     str,
    user_email:  str,
    full_name:   str,
    phone:       str,
    organisation:str,
    country:     str,
    plan_key:    str,
    amount:      float,
    currency:    str,
    pay_method:  str,
    promo_code:  str,
    discount:    float,
    email_sent:  bool,
    sms_sent:    bool,
) -> tuple:
    """
    Insert a payment record into the Supabase `payments` table.
    Returns (success: bool, message: str).
    Also updates the user_profiles table with the new tier.
    Safe to call even when DB_OK is False — returns gracefully.
    """
    if not DB_OK:
        return False, "Supabase not connected — payment not saved to DB."

    plan_label     = _PLANS.get(plan_key, {}).get("label", plan_key)
    now_iso        = datetime.utcnow().isoformat() + "Z"
    next_month_iso = (datetime.utcnow().replace(day=1)
                      .replace(month=(datetime.utcnow().month % 12) + 1)
                      ).isoformat() + "Z"

    record = {
        "order_ref":    order_ref,
        "user_id":      user_id     or None,
        "user_email":   user_email,
        "full_name":    full_name,
        "phone":        phone,
        "organisation": organisation or None,
        "country":      country,
        "plan_key":     plan_key,
        "plan_label":   plan_label,
        "amount":       amount,
        "currency":     currency,
        "payment_method": pay_method,
        "promo_code":   promo_code  or None,
        "discount":     discount,
        "status":       "succeeded",
        "email_sent":   email_sent,
        "sms_sent":     sms_sent,
        "created_at":   now_iso,
        "next_billing": next_month_iso,
        "processor":    "mock",
    }

    try:
        sb = get_supabase_client()

        # ── Insert payment record
        sb.table("payments").insert(record).execute()

        # ── Upsert user_profiles — tier + subscription lifecycle fields
        if user_id and user_id != "admin-001":
            try:
                sb.table("user_profiles").upsert({
                    "user_id":                  user_id,
                    "email":                    user_email,
                    "tier":                     plan_key,
                    "subscription_status":      "active",
                    "subscription_expires_at":  next_month_iso,
                    "cancelled_at":             None,
                    "updated_at":               now_iso,
                }, on_conflict="user_id").execute()
            except Exception:
                pass  # user_profiles table optional

        return True, "Payment saved to database."
    except Exception as exc:
        return False, f"DB save error: {exc}"


# ══════════════════════════════════════════════
#  PAGE: BILLING / CHECKOUT
# ══════════════════════════════════════════════
_PLANS = {
    "pro": {
        "label":    "Pro Plan",
        "price":    9.99,
        "billing":  "Monthly",
        "color":    "#2563eb",
        "gradient": "linear-gradient(135deg,#1e3a8a,#1d4ed8)",
        "features": [
            "Unlimited daily verifications",
            "All 4 AI models",
            "3 REST API keys",
            "CSV export & real-time alerts",
            "Priority queue — no delays",
        ],
    },
    "institutional": {
        "label":    "Institutional Plan",
        "price":    79.99,
        "billing":  "Monthly",
        "color":    "#16a34a",
        "gradient": "linear-gradient(135deg,#064e3b,#065f46)",
        "features": [
            "Everything in Pro",
            "20 team seats & API keys",
            "Bulk verify (20 claims at once)",
            "White-label PDF/HTML reports",
            "SLA-backed uptime & support",
        ],
    },
}

_PROMO_CODES = {
    "GIMPA2026": {"pct": 50, "desc": "GIMPA students & staff — 50% off"},
    "PRESS50":   {"pct": 50, "desc": "Press & media — 50% off"},
    "NGOFREE30": {"pct": 100, "desc": "NGOs — first month free"},
    "LAUNCH100": {"pct": 100, "desc": "Launch special — first month free"},
}


def page_billing():
    """Checkout / billing page — light theme."""
    step     = st.session_state.get("billing_step", "form")
    plan_key = st.session_state.get("billing_plan", "pro")

    # Activate light theme by adding billing-active class to the app root
    st.markdown(
        """<script>
        (function(){
          var app = document.querySelector('.stApp') || document.body;
          app.classList.add('billing-active');
        })();
        </script>""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="bill-shell"><div class="bill-wrap">', unsafe_allow_html=True)

    # ── Back button (light styled)
    st.markdown('<div class="bill-back">', unsafe_allow_html=True)
    if st.button("← Back to Account", key="bill_back"):
        _billing_deactivate()
        st.session_state.page = "account"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if step == "success":
        _billing_success(plan_key)
    else:
        _billing_form(plan_key)

    st.markdown('</div></div>', unsafe_allow_html=True)


def _billing_deactivate():
    """Remove billing-active class when leaving the billing page."""
    st.markdown(
        """<script>
        (function(){
          var app = document.querySelector('.stApp') || document.body;
          app.classList.remove('billing-active');
        })();
        </script>""",
        unsafe_allow_html=True,
    )


def _billing_success(plan_key: str):
    plan      = _PLANS.get(plan_key, _PLANS["pro"])
    order_ref = st.session_state.get("_bill_order_ref", "—")
    notif_log = st.session_state.get("_bill_notif_log", [])
    issuer    = st.session_state.get("_bill_card_issuer", "")
    paid_via  = (issuer + " card") if issuer else "Mobile Money"

    # ── Hero checkmark + heading
    st.markdown(
        f'<div style="text-align:center;padding:2.5rem 1rem 1.5rem;">'
        f'<div style="width:64px;height:64px;border-radius:50%;'
        f'background:linear-gradient(135deg,#dcfce7,#bbf7d0);'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:1.75rem;margin:0 auto 1rem;">&#10003;</div>'
        f'<div style="font-family:Syne,sans-serif;font-size:1.5rem;font-weight:800;'
        f'color:#0f172a;letter-spacing:-.03em;margin-bottom:.4rem;">Payment Confirmed</div>'
        f'<div style="color:#64748b;font-size:.9rem;max-width:360px;'
        f'margin:0 auto 1.5rem;line-height:1.6;">'
        f'You\'re now on <strong style="color:#1d4ed8;">{plan["label"]}</strong>. '
        f'Your features are active immediately.</div></div>',
        unsafe_allow_html=True,
    )

    # ── Receipt card wrapper open
    st.markdown(
        '<div style="max-width:480px;margin:0 auto 2rem;">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;'
        'padding:1.5rem;margin-bottom:1rem;box-shadow:0 1px 3px rgba(0,0,0,.06);">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-family:DM Mono,monospace;font-size:.6rem;font-weight:700;'
        'letter-spacing:.1em;text-transform:uppercase;color:#64748b;'
        'margin-bottom:1rem;">ORDER CONFIRMED</div>',
        unsafe_allow_html=True,
    )

    # ── Receipt rows — table avoids Streamlit sanitiser stripping nested divs
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;">'

        f'<tr>'
        f'<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        f'color:#64748b;font-size:.875rem;width:45%;">Order ref</td>'
        f'<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        f'color:#2563eb;font-weight:600;font-size:.875rem;'
        f'font-family:DM Mono,monospace;text-align:right;">{order_ref}</td>'
        f'</tr>'

        f'<tr>'
        f'<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        f'color:#64748b;font-size:.875rem;">Plan</td>'
        f'<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        f'color:#0f172a;font-weight:600;font-size:.875rem;'
        f'text-align:right;">{plan["label"]}</td>'
        f'</tr>'

        f'<tr>'
        f'<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        f'color:#64748b;font-size:.875rem;">Paid with</td>'
        f'<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        f'color:#0f172a;font-size:.875rem;'
        f'text-align:right;">{paid_via}</td>'
        f'</tr>'

        '<tr>'
        '<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        'color:#64748b;font-size:.875rem;">Billing</td>'
        '<td style="border:none;padding:8px 0;border-bottom:1px solid #f1f5f9;'
        'color:#0f172a;font-size:.875rem;'
        'text-align:right;">Monthly &middot; Cancel any time</td>'
        '</tr>'

        '<tr>'
        '<td style="border:none;padding:10px 0 0;'
        'color:#64748b;font-size:.875rem;">Status</td>'
        '<td style="border:none;padding:10px 0 0;'
        'color:#15803d;font-weight:700;font-size:.875rem;'
        'text-align:right;">&#10003; Payment authorised</td>'
        '</tr>'

        '</table>',
        unsafe_allow_html=True,
    )

    # ── Receipt card close
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Notification log (email / SMS confirmation lines)
    if notif_log:
        st.markdown(
            '<div style="background:#f8fafc;border:1px solid #e2e8f0;'
            'border-radius:10px;padding:1rem 1.25rem;">',
            unsafe_allow_html=True,
        )
        for n in notif_log:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;'
                f'padding:5px 0;border-bottom:1px solid #f1f5f9;'
                f'font-size:.8rem;color:#475569;">{n}</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Outer wrapper close
    st.markdown('</div>', unsafe_allow_html=True)


def _billing_form(plan_key: str):
    st.markdown("""
    <div style="padding:.5rem 0 1.5rem;">
      <div style="font-family:'Syne',sans-serif;font-size:1.45rem;font-weight:800;
                  color:#0f172a;letter-spacing:-.03em;margin-bottom:.3rem;">
        Checkout
      </div>
      <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;">
        <span style="color:#64748b;font-size:.82rem;display:flex;align-items:center;gap:5px;">
          🔒 256-bit SSL
        </span>
        <span style="color:#334155;">·</span>
        <span style="color:#64748b;font-size:.82rem;">↩️ 30-day money-back</span>
        <span style="color:#334155;">·</span>
        <span style="color:#64748b;font-size:.82rem;">✕ Cancel any time</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ────────────────────────────────────────────
    col_form, col_summary = st.columns([1.55, 1], gap="large")

    # ╔══════════════════════════════════╗
    # ║  LEFT — billing form             ║
    # ╚══════════════════════════════════╝
    with col_form:

        # ── Plan selector
        st.markdown('<div class="bill-card">', unsafe_allow_html=True)
        st.markdown('<span class="bill-label">Select Plan</span>',
                    unsafe_allow_html=True)
        plan_options = {"pro": "Pro — $9.99 / month", "institutional": "Institutional — $79.99 / month"}
        chosen_key = st.selectbox(
            "", options=list(plan_options.keys()),
            format_func=lambda k: plan_options[k],
            index=0 if plan_key == "pro" else 1,
            key="bill_plan_select",
            label_visibility="collapsed",
        )
        if chosen_key != plan_key:
            st.session_state.billing_plan = chosen_key
            st.rerun()

        # Promo code
        pc1, pc2 = st.columns([2.5, 1])
        with pc1:
            promo_in = st.text_input("", placeholder="Promo code (optional)",
                                     key="bill_promo", label_visibility="collapsed")
        with pc2:
            st.markdown('<div class="btn-ghost">', unsafe_allow_html=True)
            apply_promo = st.button("Apply", key="bill_apply_promo", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        promo_pct = 0
        promo_desc = ""
        if apply_promo:
            match = _PROMO_CODES.get((promo_in or "").upper())
            if match:
                st.session_state["_bill_promo_ok"]  = match["pct"]
                st.session_state["_bill_promo_desc"] = match["desc"]
                st.success(f"✓ {match['desc']}")
            else:
                st.session_state.pop("_bill_promo_ok",  None)
                st.session_state.pop("_bill_promo_desc", None)
                if promo_in:
                    st.error("Invalid or expired promo code.")
        promo_pct  = st.session_state.get("_bill_promo_ok",  0)
        promo_desc = st.session_state.get("_bill_promo_desc", "")
        if promo_pct and not apply_promo:
            st.success(f"✓ {promo_desc}")

        st.markdown('</div>', unsafe_allow_html=True)

        # ── Billing details
        st.markdown('<div class="bill-card">', unsafe_allow_html=True)
        st.markdown('<span class="bill-label">Billing Details</span>',
                    unsafe_allow_html=True)
        b1c1, b1c2 = st.columns(2)
        with b1c1:
            first_name = st.text_input("First Name", placeholder="Kwame", key="bill_fn")
        with b1c2:
            last_name  = st.text_input("Last Name",  placeholder="Mensah", key="bill_ln")
        bill_email = st.text_input("Email Address", placeholder="kwame@example.com", key="bill_email",
                                    value=st.session_state.user_email or "")
        bill_phone = st.text_input("Phone Number (for SMS alerts)",
                                    placeholder="+233 24 123 4567", key="bill_phone")
        b2c1, b2c2 = st.columns([2,1])
        with b2c1:
            bill_org   = st.text_input("Organisation (optional)",
                                        placeholder="Graphic Communications Group", key="bill_org")
        with b2c2:
            bill_country = st.selectbox("Country", ["Ghana", "Nigeria", "Kenya",
                                                     "South Africa", "United Kingdom",
                                                     "United States", "Other"],
                                         key="bill_country")
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Payment info
        st.markdown('<div class="bill-card-accent">', unsafe_allow_html=True)

        # Accepted network badges row
        _badge = lambda lbl,bg,fg: (
            f'<span style="background:{bg};color:{fg};font-size:.58rem;font-weight:700;' 
            f'padding:.18rem .55rem;border-radius:4px;letter-spacing:.04em;">{lbl}</span>'
        )
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem;">
          <span class="bill-label" style="margin:0;">Payment Details</span>
          <div style="display:flex;gap:.35rem;align-items:center;flex-wrap:wrap;">
            {_badge("VISA","#1a1f71","#fff")}
            {_badge("MC","#eb001b","#fff")}
            {_badge("AMEX","#007bc1","#fff")}
            {_badge("VERVE","#009933","#fff")}
            {_badge("DISCOVER","#f76f20","#fff")}
            {_badge("UNIONPAY","#e31837","#fff")}
            {_badge("GHIPSS","#006633","#fff")}
            {_badge("MTN","#ffcc00","#000")}
          </div>
        </div>
        <div style="background:#eff6ff;border:1px solid #bfdbfe;
                    border-radius:8px;padding:.75rem 1rem;margin-bottom:.75rem;
                    display:flex;align-items:center;gap:.5rem;">
          <span>🔒</span>
          <span style="color:#1d4ed8;font-size:.78rem;font-weight:500;">
            VeriGhana never stores raw card numbers. Any valid card is accepted for demo purposes.
          </span>
        </div>
        """, unsafe_allow_html=True)

        pay_method = st.radio("", ["Credit / Debit Card", "Mobile Money (MTN / Vodafone)"],
                               horizontal=True, key="bill_method", label_visibility="collapsed")

        if pay_method == "Credit / Debit Card":
            card_name = st.text_input("Name on card", placeholder="KWAME MENSAH", key="bill_cname")

            # ── Live card number field with issuer detection ──────
            raw_num   = st.session_state.get("bill_cnum_raw", "")
            network   = _detect_card(raw_num)
            max_digits = network["max_len"] if network else 19

            # Issuer indicator shown above the number field
            if network:
                exp_lens = " or ".join(str(l) for l in network["lengths"])
                cur_digits = len("".join(c for c in raw_num if c.isdigit()))
                len_ok  = cur_digits in network["lengths"]
                len_clr = "#4ade80" if len_ok else ("#f59e0b" if cur_digits > 0 else "#64748b")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:.6rem;
                            margin-bottom:.35rem;min-height:24px;">
                  <span style="background:{network["bg"]};color:{network["fg"]};
                               font-size:.65rem;font-weight:800;letter-spacing:.06em;
                               padding:.2rem .7rem;border-radius:5px;">
                    {network["label"].upper()}
                  </span>
                  <span style="color:{len_clr};font-size:.78rem;font-family:'DM Mono',monospace;">
                    {cur_digits} / {exp_lens} digits
                    {"✓" if len_ok else ""}
                  </span>
                </div>""", unsafe_allow_html=True)
            else:
                if raw_num:
                    st.markdown('<div style="color:#dc2626;font-size:.78rem;margin-bottom:.35rem;">' 
                                'Unrecognised card prefix</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="min-height:24px;margin-bottom:.35rem;"></div>',
                                unsafe_allow_html=True)

            # The actual input — no max_chars so any length works;
            # we validate at submit time based on detected network
            raw_input = st.text_input(
                "Card number",
                placeholder="Enter your card number",
                key="bill_cnum_raw",
                help="Start typing — your card network is detected automatically",
            )

            # Expiry + CVV row
            cvv_len = network["cvv_len"] if network else 3
            cvv_placeholder = "•" * cvv_len
            cc1, cc2 = st.columns([1.5, 1])
            with cc1:
                card_exp = st.text_input("Expiry (MM/YY)", placeholder="12/27",
                                          key="bill_exp", max_chars=5)
            with cc2:
                card_cvv = st.text_input(
                    f"CVV ({cvv_len} digits)",
                    placeholder=cvv_placeholder,
                    key="bill_cvv", max_chars=cvv_len, type="password",
                )
        else:
            momo_num = st.text_input("Mobile Money number",
                                      placeholder="+233 24 123 4567", key="bill_momo")
            st.markdown("""
            <div style="color:#64748b;font-size:.78rem;padding:.5rem 0;">
              You will receive a payment prompt on your phone. Approve to complete.
            </div>""", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # ── Terms & submit
        agree = st.checkbox("I agree to the Terms of Service and Privacy Policy", key="bill_agree")
        st.markdown("<div style='margin-top:.75rem;'>", unsafe_allow_html=True)

        plan    = _PLANS[chosen_key]
        base    = plan["price"]
        disc    = round(base * promo_pct / 100, 2)
        total   = round(base - disc, 2)
        btn_lbl = (f"Pay ${total:.2f} now — {plan['label']}"
                   if total > 0 else f"Activate Free Month — {plan['label']}")

        st.markdown('<div class="bill-pay-btn">', unsafe_allow_html=True)
        if st.button(btn_lbl, key="bill_pay", use_container_width=True, type="primary"):
            errs = []
            if not first_name or not last_name: errs.append("Full name is required.")
            if not bill_email:                  errs.append("Email address is required.")
            if not bill_phone:                  errs.append("Phone number is required for SMS alerts.")
            if pay_method == "Credit / Debit Card":
                _raw  = st.session_state.get("bill_cnum_raw", "")
                _net  = _detect_card(_raw)
                _digs = len("".join(c for c in _raw if c.isdigit()))
                if not _raw:
                    errs.append("Card number is required.")
                elif _net is None:
                    errs.append("Unrecognised card prefix — please check your card number.")
                elif _digs not in _net["lengths"]:
                    _exp = " or ".join(str(l) for l in _net["lengths"])
                    errs.append(
                        f"{_net['label']} cards require {_exp} digits "
                        f"— you entered {_digs}."
                    )
                if not st.session_state.get("bill_exp"):  errs.append("Expiry date is required.")
                if not st.session_state.get("bill_cvv"):  errs.append("CVV is required.")
            else:
                if not st.session_state.get("bill_momo"): errs.append("Mobile Money number is required.")
            if not agree: errs.append("Please accept the Terms of Service to continue.")

            if errs:
                for e in errs:
                    st.error(e)
            else:
                with st.spinner("Authorising payment…"):
                    _craw   = st.session_state.get("bill_cnum_raw", "")
                    _cnet   = _detect_card(_craw)
                    _issuer = _cnet["label"] if _cnet else ""
                    momo    = st.session_state.get("bill_momo", "")
                    ok, order_ref, pay_msg = _mock_process_payment(
                        pay_method, _craw, momo, _issuer
                    )

                if ok:
                    full_name  = f"{first_name} {last_name}".strip()
                    promo_code = st.session_state.get("bill_promo", "")

                    # ── 1. Upgrade session tier immediately
                    st.session_state.user_tier = chosen_key
                    save_session_cookie()
                    st.session_state["_bill_order_ref"]  = order_ref
                    st.session_state["_bill_card_issuer"] = _issuer

                    # ── 2. Persist payment to Supabase
                    with st.spinner("Saving payment record…"):
                        _method_label = (
                            f"{pay_method} ({_issuer})" if _issuer else pay_method
                        )
                        db_ok, db_msg = save_payment_to_db(
                            order_ref    = order_ref,
                            user_id      = str(st.session_state.get("user_id") or ""),
                            user_email   = bill_email,
                            full_name    = full_name,
                            phone        = bill_phone,
                            organisation = st.session_state.get("bill_org", ""),
                            country      = st.session_state.get("bill_country", ""),
                            plan_key     = chosen_key,
                            amount       = total,
                            currency     = "USD",
                            pay_method   = _method_label,
                            promo_code   = promo_code,
                            discount     = disc,
                            email_sent   = False,   # updated below
                            sms_sent     = False,   # updated below
                        )

                    # ── 3. Email notification
                    with st.spinner("Sending confirmation email…"):
                        e_ok, e_msg = send_confirmation_email(
                            bill_email, full_name, chosen_key, total, order_ref
                        )

                    # ── 4. SMS notification
                    with st.spinner("Sending SMS alert…"):
                        s_ok, s_msg = send_confirmation_sms(
                            bill_phone, chosen_key, total, order_ref
                        )

                    # ── 5. Patch notification flags on the DB record
                    if db_ok and DB_OK and (e_ok or s_ok):
                        try:
                            get_supabase_client().table("payments").update({
                                "email_sent": e_ok,
                                "sms_sent":   s_ok,
                            }).eq("order_ref", order_ref).execute()
                        except Exception:
                            pass

                    # ── 6. Build notification log for success screen
                    notif_log = []
                    if db_ok:
                        notif_log.append("🗄️ Payment record saved to database")
                    else:
                        notif_log.append(f"🗄️ DB note: {db_msg}")
                    if e_ok:
                        notif_log.append(f"📧 Confirmation email sent to {bill_email}")
                    else:
                        notif_log.append(f"📧 Email note: {e_msg}")
                    if s_ok:
                        notif_log.append(f"📱 SMS alert sent to {bill_phone}")
                    else:
                        notif_log.append(f"📱 SMS note: {s_msg}")

                    st.session_state["_bill_notif_log"] = notif_log
                    st.session_state.billing_step = "success"
                    st.session_state.pop("_bill_promo_ok",  None)
                    st.session_state.pop("_bill_promo_desc", None)
                    st.rerun()
                else:
                    st.error(f"Payment failed: {pay_msg}")

        st.markdown("</div>", unsafe_allow_html=True)  # bill-pay-btn
        st.markdown("</div>", unsafe_allow_html=True)  # margin-top wrapper

    # ╔══════════════════════════════════╗
    # ║  RIGHT — order summary sidebar   ║
    # ╚══════════════════════════════════╝
    with col_summary:
        plan  = _PLANS[chosen_key]
        base  = plan["price"]
        disc  = round(base * promo_pct / 100, 2)
        total = round(base - disc, 2)

        feat_html = "".join(
            f'<div style="display:flex;gap:.6rem;align-items:flex-start;'
            f'padding:.45rem 0;border-bottom:1px solid #f1f5f9;">'
            f'<span style="color:{plan["color"]};font-size:.85rem;flex-shrink:0;margin-top:1px;">✓</span>'
            f'<span style="color:#334155;font-size:.82rem;line-height:1.5;">{f}</span>'
            f'</div>'
            for f in plan["features"]
        )

        disc_row = (
            f'<div style="display:flex;justify-content:space-between;'
            f'color:#16a34a;font-size:.85rem;font-weight:600;padding:.3rem 0;">'
            f'<span>Promo discount</span><span>−${disc:.2f}</span></div>'
        ) if disc > 0 else ""

        # ── Order summary card — split into individual calls to avoid Streamlit sanitiser
        st.markdown(
            '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;'
            'padding:1.5rem;position:sticky;top:120px;'
            'box-shadow:0 4px 16px rgba(0,0,0,.06);">',
            unsafe_allow_html=True,
        )

        # Label
        st.markdown('<span class="bill-label">Order Summary</span>', unsafe_allow_html=True)

        # Plan header pill
        st.markdown(
            f'<div style="background:{plan["gradient"]};border-radius:8px;'
            f'padding:1rem 1.1rem;margin-bottom:1rem;">'
            f'<div style="font-family:\'DM Mono\',monospace;font-size:.6rem;'
            f'color:rgba(255,255,255,.7);letter-spacing:.1em;'
            f'text-transform:uppercase;margin-bottom:.3rem;">{plan["label"]}</div>'
            f'<div style="font-family:\'Syne\',sans-serif;font-weight:800;'
            f'font-size:1.5rem;color:#fff;line-height:1;">'
            f'${base:.2f}<span style="font-size:.82rem;font-weight:400;'
            f'color:rgba(255,255,255,.65);">&thinsp;/mo</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Feature list
        st.markdown(
            f'<div style="margin-bottom:1rem;">{feat_html}</div>',
            unsafe_allow_html=True,
        )

        # Price rows — use table so nesting doesn't get stripped
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;'
            f'border-top:1px solid #f1f5f9;padding-top:.85rem;margin-top:.85rem;">'
            f'<tr>'
            f'<td style="border:none;color:#64748b;font-size:.85rem;padding:.3rem 0;">{plan["label"]}</td>'
            f'<td style="border:none;color:#64748b;font-size:.85rem;text-align:right;">${base:.2f}/mo</td>'
            f'</tr>'
            + (
                f'<tr>'
                f'<td style="border:none;color:#16a34a;font-size:.85rem;font-weight:600;padding:.3rem 0;">Promo discount</td>'
                f'<td style="border:none;color:#16a34a;font-size:.85rem;font-weight:600;text-align:right;">−${disc:.2f}</td>'
                f'</tr>'
                if disc > 0 else ""
            ) +
            f'<tr style="border-top:1.5px solid #e2e8f0;">'
            f'<td style="border:none;color:#0f172a;font-weight:800;font-size:1.05rem;padding:.6rem 0 0;">Total today</td>'
            f'<td style="border:none;color:{plan["color"]};font-weight:800;font-size:1.05rem;text-align:right;padding:.6rem 0 0;">${total:.2f}</td>'
            f'</tr>'
            f'</table>'
            f'<div style="color:#64748b;font-size:.72rem;margin-top:.35rem;">'
            f'Then ${base:.2f}/month · Cancel anytime</div>',
            unsafe_allow_html=True,
        )

        # Trust signals
        for icon, txt in [
            ("🔒", "256-bit SSL encryption"),
            ("↩️", "30-day money-back guarantee"),
            ("📧", "Confirmation by email &amp; SMS"),
        ]:
            st.markdown(
                f'<div style="display:flex;gap:.5rem;align-items:center;'
                f'color:#475569;font-size:.76rem;padding:.2rem 0;'
                f'border-top:1px solid #f8fafc;margin-top:.5rem;">'
                f'{icon}&nbsp;{txt}</div>',
                unsafe_allow_html=True,
            )

        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: CONTACT & SUPPORT
# ══════════════════════════════════════════════
_FAQ = [
    (
        "What is the difference between Free, Pro and Institutional plans?",
        "The Free plan gives you 5 verifications per day using a single AI model. "
        "The Pro plan ($9.99/mo) unlocks unlimited daily verifications, all 4 AI models "
        "(Gemini, Groq, Cohere, OpenRouter), 3 REST API keys, CSV export and real-time "
        "alert webhooks. The Institutional plan ($79.99/mo) adds 20 team seats, 20 API keys, "
        "bulk verification of up to 20 claims at once, white-label PDF/HTML reports and an "
        "SLA-backed uptime guarantee — ideal for newsrooms, NGOs and government agencies."
    ),
    (
        "How does VeriGhana's AI verification actually work?",
        "When you submit a claim, VeriGhana searches its indexed database of 60+ trusted "
        "Ghanaian sources — government portals, regulatory bodies, major media outlets — "
        "for matching articles and statements. Those results are then passed to an AI model "
        "(Gemini by default, with Groq, Cohere and OpenRouter as fallbacks) which analyses "
        "the evidence and returns a structured verdict: Verified, Partial, False or "
        "Uncorroborated. A confidence score (0–100%) and a narrative explanation citing "
        "specific sources are included in every result."
    ),
    (
        "How do I get API access and what can I build with it?",
        "API keys are available on Pro and Institutional plans. Once upgraded, go to your "
        "Account page to generate a key. The REST API exposes a single POST /verify endpoint "
        "that accepts a claim text and returns the full JSON verdict. Common use-cases include "
        "integrating fact-checks directly into newsroom CMS platforms, automated WhatsApp "
        "bot fact-checkers, and academic research pipelines. Full API documentation is "
        "available at docs.verighana.gh."
    ),
    (
        "Which Ghanaian sources does VeriGhana cover?",
        "VeriGhana indexes 65+ authoritative Ghanaian sources across government, media and "
        "regulatory bodies — including the Office of the President, Parliament of Ghana, Bank "
        "of Ghana, Electoral Commission, Ghana Health Service, Ghana Revenue Authority, "
        "Ghana News Agency, Citi Newsroom, Joy Online, Graphic Online and many others. "
        "The database is refreshed continuously via automated scrapers. You can see the full "
        "source list on the Verify page under Database Stats."
    ),
    (
        "How do I cancel my subscription or request a refund?",
        "You can cancel at any time from your Account page — your plan stays active until "
        "the end of the current billing period and you will not be charged again. For refund "
        "requests within the 30-day money-back guarantee window, email support@verighana.gh "
        "with your order reference. Refunds are processed within 5–7 business days."
    ),
    (
        "I applied a promo code but it did not work — what should I do?",
        "Promo codes are case-insensitive and entered at checkout. Currently active codes "
        "include GIMPA2026 (50% off Pro for GIMPA students and staff), PRESS50 (50% off Pro "
        "for press and media), NGOFREE30 (first month free for NGOs) and LAUNCH100 (first "
        "month 100% free). If your code still does not work, email support@verighana.gh with "
        "a screenshot and we will apply the discount manually."
    ),
]


def _save_ticket_to_db(name: str, email: str, subject: str,
                        message: str, category: str) -> tuple:
    """Insert a support ticket into Supabase. Returns (ok, msg)."""
    if not DB_OK:
        return False, "DB not connected — ticket not saved."
    try:
        sb = get_supabase_client()
        sb.table("support_tickets").insert({
            "name":       name,
            "email":      email,
            "subject":    subject,
            "message":    message,
            "category":   category,
            "status":     "open",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "user_id":    str(st.session_state.get("user_id") or "") or None,
        }).execute()
        return True, "Ticket saved."
    except Exception as e:
        return False, str(e)


def _send_support_reply(
    to_email:   str,
    to_name:    str,
    subject:    str,
    body:       str,
    ticket_id:  str = "",
) -> tuple:
    """
    Send a support reply via Resend (https://resend.com — free 3,000/month).

    From-address logic:
      • If RESEND_FROM_EMAIL is set in .env, use it (requires verified domain on Resend).
      • Otherwise fall back to onboarding@resend.dev — Resend's shared domain that
        works immediately with no domain verification required.
        NOTE: with the shared domain, Resend only delivers to the email address that
        owns the Resend account. Verify your domain to send to any address.

    Returns (ok: bool, message: str).
    """
    api_key   = os.getenv("RESEND_API_KEY", "")
    from_name = os.getenv("NOTIFY_FROM_NAME", "VeriGhana Support")

    # Use verified custom domain if configured, else Resend shared onboarding domain
    custom_from = os.getenv("RESEND_FROM_EMAIL", "").strip()
    from_addr   = custom_from if custom_from else "onboarding@resend.dev"

    ref_line  = f"\n\n—\nTicket ref: {ticket_id}" if ticket_id else ""
    html_body = (
        f"<div style='font-family:Arial,sans-serif;font-size:15px;color:#1e293b;"
        f"max-width:600px;margin:0 auto;line-height:1.6;'>"
        f"<div style='background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0;'>"
        f"<span style='font-weight:800;font-size:18px;color:#fff;'>"
        f"Veri<span style='color:#60a5fa;'>Ghana</span></span>"
        f"</div>"
        f"<div style='padding:24px;border:1px solid #e2e8f0;border-top:none;"
        f"border-radius:0 0 8px 8px;background:#ffffff;'>"
        f"<p style='margin:0 0 16px;'>Hi <strong>{to_name}</strong>,</p>"
        f"<div style='white-space:pre-wrap;'>{body}</div>"
        f"<hr style='margin:24px 0;border:none;border-top:1px solid #e2e8f0;'>"
        f"<p style='font-size:12px;color:#94a3b8;margin:0;'>"
        f"VeriGhana Support"
        f"{'<br>Ticket ref: ' + ticket_id if ticket_id else ''}"
        f"</p></div></div>"
    )

    if not api_key:
        print(f"[RESEND] No API key — would have sent to {to_email}: {subject}")
        return False, "RESEND_API_KEY not set in .env — reply not sent."

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "from":     f"{from_name} <{from_addr}>",
                "to":       [to_email],
                "subject":  f"Re: {subject}",
                "html":     html_body,
                "text":     f"Hi {to_name},\n\n{body}{ref_line}\n\n— VeriGhana Support",
                "reply_to": os.getenv("NOTIFY_FROM_EMAIL", from_addr),
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return True, f"Reply sent to {to_email}."
        # Surface a cleaner error for the 403 domain-not-verified case
        try:
            err_json = resp.json()
            err_msg  = err_json.get("message", resp.text[:160])
        except Exception:
            err_msg  = resp.text[:160]
        if resp.status_code == 403 and "domain" in err_msg.lower():
            return False, (
                "Domain not verified on Resend. "
                "Either add RESEND_FROM_EMAIL=onboarding@resend.dev to .env "
                "(sends only to your Resend account email), "
                "or verify verighana.gh at resend.com/domains."
            )
        return False, f"Resend {resp.status_code}: {err_msg}"
    except Exception as exc:
        return False, f"Send failed: {exc}"


def page_contact():
    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)

    # ── Page header
    st.markdown("""
    <div class="vg-page-head">
      <div class="vg-h1">Contact &amp; <em>Support</em></div>
      <div class="vg-sub">
        We typically respond within one business day.
        For urgent issues email us directly at
        <a href="mailto:support@verighana.gh"
           style="color:#2563eb;text-decoration:none;">support@verighana.gh</a>
      </div>
    </div>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([1.35, 1], gap="large")

    # ╔══════════════════════════════╗
    # ║  LEFT — contact form         ║
    # ╚══════════════════════════════╝
    with left_col:

        st.markdown('<div class="vg-card">', unsafe_allow_html=True)
        st.markdown(
            '<span style="font-family:\'DM Mono\',monospace;font-size:.6rem;'
            'font-weight:700;letter-spacing:.1em;text-transform:uppercase;'
            'color:#64748b;display:block;margin-bottom:1rem;">SEND A MESSAGE</span>',
            unsafe_allow_html=True,
        )

        if st.session_state.get("_contact_sent"):
            # ── Success state
            submitter_name = st.session_state.get("_contact_name", "there")
            st.markdown(f"""
            <div style="text-align:center;padding:2rem 1rem;">
              <div style="width:56px;height:56px;border-radius:50%;
                          background:linear-gradient(135deg,#dcfce7,#bbf7d0);
                          display:flex;align-items:center;justify-content:center;
                          font-size:1.5rem;margin:0 auto .75rem;">✓</div>
              <div style="font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:700;
                          color:#0f172a;margin-bottom:.4rem;">Message received!</div>
              <div style="color:#64748b;font-size:.875rem;line-height:1.6;">
                Thanks {submitter_name} — we'll get back to you within one business day.<br>
                Check your inbox at
                <strong style="color:#2563eb;">{st.session_state.get("_contact_email","")}</strong>
                for a confirmation.
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('<div class="btn-ghost" style="margin-top:1rem;">', unsafe_allow_html=True)
            if st.button("Send another message", key="contact_reset", use_container_width=True):
                for k in ("_contact_sent", "_contact_name", "_contact_email"):
                    st.session_state.pop(k, None)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # ── Contact form
            fn_col, ln_col = st.columns(2)
            with fn_col:
                c_first = st.text_input("First Name", placeholder="Kwame", key="c_first")
            with ln_col:
                c_last  = st.text_input("Last Name",  placeholder="Mensah", key="c_last")

            c_email = st.text_input(
                "Email Address",
                placeholder="kwame@example.com",
                key="c_email",
                value=st.session_state.user_email or "",
            )

            c_cat = st.selectbox(
                "Category",
                ["Billing & payments", "Account & login",
                 "API & integrations", "Verification results",
                 "Feature request", "Bug report", "Other"],
                key="c_cat",
            )

            c_subject = st.text_input(
                "Subject",
                placeholder="Brief description of your issue",
                key="c_subject",
            )

            c_message = st.text_area(
                "Message",
                placeholder="Describe your issue or question in detail…",
                key="c_message",
                height=130,
            )

            st.markdown("<div style='margin-top:.5rem;'>", unsafe_allow_html=True)
            st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
            if st.button("Send Message →", key="contact_send", use_container_width=True):
                errs = []
                if not c_first: errs.append("First name is required.")
                if not c_email: errs.append("Email address is required.")
                if not c_subject: errs.append("Subject is required.")
                if not c_message or len(c_message.strip()) < 10:
                    errs.append("Please write a message (at least 10 characters).")
                if errs:
                    for e in errs:
                        st.error(e)
                else:
                    full_name = f"{c_first} {c_last}".strip()
                    with st.spinner("Sending…"):
                        db_ok, db_msg = _save_ticket_to_db(
                            name=full_name, email=c_email,
                            subject=c_subject, message=c_message,
                            category=st.session_state.get("c_cat", "Other"),
                        )
                    st.session_state["_contact_sent"]  = True
                    st.session_state["_contact_name"]  = c_first
                    st.session_state["_contact_email"] = c_email
                    st.rerun()
            st.markdown('</div></div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)  # vg-card

    # ╔══════════════════════════════╗
    # ║  RIGHT — info + FAQ          ║
    # ╚══════════════════════════════╝
    with right_col:

        # ── Quick contact info card (flat rows — avoids Streamlit sanitiser stripping nested divs)
        st.markdown('<div class="vg-card" style="margin-bottom:1rem;">', unsafe_allow_html=True)
        st.markdown(
            '<span style="font-family:\'DM Mono\',monospace;font-size:.6rem;font-weight:700;'
            'letter-spacing:.1em;text-transform:uppercase;color:#64748b;'
            'display:block;margin-bottom:1rem;">GET IN TOUCH</span>',
            unsafe_allow_html=True,
        )

        # Row 1 — Email
        st.markdown(
            '<table style="border:none;border-collapse:collapse;width:100%;margin-bottom:.75rem;">'
            '<tr style="border:none;">'
            '<td style="border:none;width:32px;vertical-align:top;padding:0;font-size:1.1rem;padding-top:2px;">📧</td>'
            '<td style="border:none;padding:0;vertical-align:top;">'
            '<div style="font-size:.82rem;font-weight:600;color:#0f172a;margin-bottom:.15rem;">Email Support</div>'
            '<a href="mailto:support@verighana.gh" style="color:#2563eb;font-size:.82rem;text-decoration:none;">'
            'support@verighana.gh</a>'
            '<div style="color:#64748b;font-size:.74rem;margin-top:.15rem;">Response within 1 business day</div>'
            '</td></tr></table>',
            unsafe_allow_html=True,
        )

        # Row 2 — Hours
        st.markdown(
            '<table style="border:none;border-collapse:collapse;width:100%;margin-bottom:.75rem;">'
            '<tr style="border:none;">'
            '<td style="border:none;width:32px;vertical-align:top;padding:0;font-size:1.1rem;padding-top:2px;">🕐</td>'
            '<td style="border:none;padding:0;vertical-align:top;">'
            '<div style="font-size:.82rem;font-weight:600;color:#0f172a;margin-bottom:.15rem;">Support Hours</div>'
            '<div style="color:#475569;font-size:.82rem;">Mon–Fri, 8 AM – 6 PM GMT</div>'
            '<div style="color:#64748b;font-size:.74rem;margin-top:.15rem;">Institutional plans: 24/7 SLA support</div>'
            '</td></tr></table>',
            unsafe_allow_html=True,
        )

        # Row 3 — Office
        st.markdown(
            '<table style="border:none;border-collapse:collapse;width:100%;margin-bottom:.25rem;">'
            '<tr style="border:none;">'
            '<td style="border:none;width:32px;vertical-align:top;padding:0;font-size:1.1rem;padding-top:2px;">🏫</td>'
            '<td style="border:none;padding:0;vertical-align:top;">'
            '<div style="font-size:.82rem;font-weight:600;color:#0f172a;margin-bottom:.15rem;">Research Office</div>'
            '<div style="color:#475569;font-size:.82rem;">GIMPA Computer Science Dept.</div>'
            '<div style="color:#475569;font-size:.82rem;">Accra, Ghana</div>'
            '</td></tr></table>',
            unsafe_allow_html=True,
        )

        st.markdown('</div>', unsafe_allow_html=True)

        # ── Quick links
        st.markdown("""
        <div class="vg-card" style="margin-bottom:1rem;">
          <span style="font-family:'DM Mono',monospace;font-size:.6rem;font-weight:700;
                       letter-spacing:.1em;text-transform:uppercase;color:#64748b;
                       display:block;margin-bottom:.85rem;">QUICK LINKS</span>
          <div style="display:flex;flex-direction:column;gap:.45rem;">
        """, unsafe_allow_html=True)

        for icon, label, href in [
            ("📖", "API Documentation",   "https://docs.verighana.gh"),
            ("💳", "Pricing & Plans",     "#"),
            ("🔐", "Privacy Policy",      "#"),
            ("📜", "Terms of Service",    "#"),
            ("🐛", "Report a Bug",        "mailto:bugs@verighana.gh"),
        ]:
            st.markdown(
                f'<a href="{href}" style="display:flex;align-items:center;gap:.55rem;'
                f'padding:.35rem 0;color:#334155;font-size:.83rem;text-decoration:none;'
                f'border-bottom:1px solid #f1f5f9;">'
                f'<span>{icon}</span><span>{label}</span>'
                f'<span style="margin-left:auto;color:#334155;font-size:.75rem;">→</span>'
                f'</a>',
                unsafe_allow_html=True,
            )
        st.markdown('</div></div>', unsafe_allow_html=True)

    # ── FAQ section — full width below
    st.markdown('<hr style="margin:1.5rem 0;">', unsafe_allow_html=True)
    st.markdown("""
    <div style="margin-bottom:1.25rem;">
      <div class="vg-h2" style="font-size:1.1rem;margin-bottom:.2rem;">
        Frequently Asked Questions
      </div>
      <div class="vg-sub">Click a question to expand the answer.</div>
    </div>
    """, unsafe_allow_html=True)

    for i, (question, answer) in enumerate(_FAQ):
        with st.expander(question, expanded=(i == 0)):
            st.markdown(
                f'<div style="color:#475569;font-size:.875rem;line-height:1.75;'
                f'padding:.25rem 0 .5rem;">{answer}</div>',
                unsafe_allow_html=True,
            )

    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
def main():
    inject_css()

    # Step 1: try to restore session from browser cookie / localStorage
    restore_session_from_cookie()

    # Step 2: if still not logged in, inject JS reader and show auth page
    if not st.session_state.logged_in:
        inject_session_reader()   # JS reads cookie/localStorage → sets ?_vg= → triggers re-run
        page_auth()
        return

    render_nav()
    render_tabs()

    st.markdown("""
    <style>
    [data-testid="stAppViewBlockContainer"],
    [data-testid="stMainBlockContainer"],
    .block-container {
        max-width: 1080px !important;
        margin: 0 auto !important;
        padding: 0 2rem !important;
        padding-top: 0 !important;
    }
    </style>""", unsafe_allow_html=True)

    p     = st.session_state.page
    admin = is_admin()

    if   p == "verify":               page_verify()
    elif p == "history":              page_history()
    elif p == "account":              page_account()
    elif p == "billing":              page_billing()
    elif p == "contact":              page_contact()
    elif p == "admin"   and admin:    page_admin()
    elif p == "tickets" and admin:    page_tickets()
    elif p == "tester"  and admin:    page_tester()
    else:
        st.session_state.page = "verify"; st.rerun()

    st.markdown(
        '<div style="text-align:center;padding:2rem;font-size:.72rem;color:#334155;">'
        '<span class="vg-logo" style="font-size:.78rem;vertical-align:middle;">'
        'Veri<em>Ghana</em></span>'
        ' © 2026 — GIMPA Computer Science Research — '
        'Combating information disorder in Ghana with AI.</div>',
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()