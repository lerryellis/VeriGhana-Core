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

TIER_LIMITS = {"free": 5, "pro": None, "institutional": None}
TIER_MODELS = {
    "free":          [list(FREE_MODELS.keys())[-1]],
    "pro":           list(FREE_MODELS.keys()),
    "institutional": list(FREE_MODELS.keys()),
}


# ══════════════════════════════════════════════
#  SESSION PERSISTENCE
#  Token = base64(json_payload) + "." + HMAC-SHA256
#  Stored in browser cookie AND localStorage.
#  On every reload the JS sets ?_vg=<token> so
#  Python can restore session_state without extra packages.
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
    Injected on every page load when not yet logged in.
    Reads cookie (or localStorage fallback), sets ?_vg= to trigger a
    Streamlit re-run so Python can restore session_state.
    sessionStorage flag prevents infinite redirect loops.
    """
    return """
<script>
(function() {
  if (sessionStorage.getItem("vg_redirected") === "1") return;

  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }

  var token = getCookie("vg_session");

  // Restore cookie from localStorage if it was cleared
  if (!token) {
    try { token = localStorage.getItem("vg_token"); } catch(e) {}
    if (token) {
      var exp = new Date(Date.now() + 30 * 864e5).toUTCString();
      document.cookie = "vg_session=" + encodeURIComponent(token)
                      + "; expires=" + exp + "; path=/; SameSite=Lax";
    }
  }

  if (!token) return;

  var params = new URLSearchParams(window.location.search);
  if (params.get("_vg") === token) return;  // already set, avoid loop

  sessionStorage.setItem("vg_redirected", "1");
  params.set("_vg", token);
  window.location.search = params.toString();
})();
</script>"""


def _clear_redirect_flag_js() -> str:
    return """<script>
(function() { try { sessionStorage.removeItem("vg_redirected"); } catch(e) {} })();
</script>"""


def restore_session_from_cookie():
    """Called once at the top of main(). Restores session from ?_vg= token."""
    if st.session_state.get("logged_in"):
        save_session_cookie()   # silently roll the 30-day window
        return

    token = st.query_params.get("_vg", "")
    if not token:
        return

    payload = _verify_token(token)
    if not payload:
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
    st.query_params.clear()
    st.components.v1.html(_clear_redirect_flag_js(), height=0)


def save_session_cookie():
    """Write / refresh cookie + localStorage. Safe to call on every load."""
    token = _make_session_token(
        email   = st.session_state.user_email or "",
        name    = st.session_state.user_name  or "",
        role    = st.session_state.user_role  or "client",
        tier    = st.session_state.user_tier  or "free",
        user_id = str(st.session_state.user_id or ""),
    )
    st.components.v1.html(_cookie_js(token), height=0)


def clear_session_cookie():
    """Delete cookie + localStorage and wipe relevant session_state keys."""
    st.components.v1.html(_clear_cookie_js(), height=0)
    for key in ("logged_in", "user_email", "user_name",
                "user_role", "user_tier", "user_id"):
        st.session_state.pop(key, None)


def inject_session_reader():
    """Injected every page load when not logged in — JS does the cookie read."""
    if not st.session_state.get("logged_in"):
        st.components.v1.html(_read_session_js(), height=0)


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
/* ─── GLOBAL RESET ─── */
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif!important;}
#MainMenu,footer,header{visibility:hidden!important;height:0!important;overflow:hidden!important;}
.stApp{background:#0f2240!important;min-height:100vh;}

/* ─── NUKE ALL STREAMLIT PADDING ─── */
.block-container{padding:0!important;padding-top:0!important;max-width:100%!important;margin:0!important;}
[data-testid="stAppViewBlockContainer"]{padding:0!important;padding-top:0!important;max-width:100%!important;}
[data-testid="stMainBlockContainer"]{padding:0!important;padding-top:0!important;max-width:100%!important;}
.stMainBlockContainer{padding:0!important;padding-top:0!important;}
section.main > div{padding:0!important;padding-top:0!important;}
section.main > div > div{padding:0!important;}
section[data-testid="stSidebar"]{display:none!important;}
[data-testid="stVerticalBlock"]{gap:0 !important;}
.vg-wrap [data-testid="stVerticalBlock"]{gap:.4rem !important;}

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:4px}

/* ─── AUTH PAGE ─── */
.auth-mode .stApp{
  display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  min-height:100vh;
  background:linear-gradient(160deg,#0a1628 0%,#0d1f42 60%,#0f2240 100%) !important;
}
.auth-mode .block-container,
.auth-mode [data-testid="stAppViewBlockContainer"],
.auth-mode [data-testid="stMainBlockContainer"]{
  width:100%!important;max-width:440px!important;
  margin:0 auto!important;padding:0 1rem!important;
}
.auth-bg-grid{
  position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:
    linear-gradient(rgba(37,99,235,.05) 1px,transparent 1px),
    linear-gradient(90deg,rgba(37,99,235,.05) 1px,transparent 1px);
  background-size:44px 44px;
}

/* ─── NAV BAR ─── */
.vg-nav{
  background:rgba(9,19,40,.98);
  border-bottom:1px solid rgba(255,255,255,.07);
  padding:0 2rem;
  display:flex;align-items:center;
  height:52px;gap:1rem;
  position:sticky;top:0;z-index:300;
  width:100%;
}
.vg-logo{font-family:'Syne',sans-serif;font-weight:800;font-size:1.15rem;
  color:#fff;letter-spacing:-.02em;text-decoration:none;white-space:nowrap;}
.vg-logo em{font-style:normal;color:#60a5fa;}
.vg-sep{width:1px;height:16px;background:rgba(255,255,255,.1);}
.vg-nav-sub{font-family:'DM Mono',monospace;font-size:.62rem;color:#334155;
  letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;}
.vg-nav-right{margin-left:auto;display:flex;align-items:center;gap:.75rem;}
.vg-avatar{width:24px;height:24px;border-radius:50%;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  display:flex;align-items:center;justify-content:center;
  font-family:'Syne',sans-serif;font-weight:700;
  font-size:.6rem;color:#fff;flex-shrink:0;}

/* ─── TAB BAR ─── */
/* Sticky wrapper sits under the nav bar */
div[data-testid="stHorizontalBlock"].vg-tabrow{
  background:rgba(7,15,32,.97)!important;
  border-bottom:1px solid rgba(255,255,255,.06)!important;
  position:sticky!important;top:52px!important;z-index:200!important;
  padding:0 2rem!important;gap:0!important;
}
/* All tab buttons: flat, transparent */
.vg-tabrow div[data-testid="column"] .stButton>button{
  background:transparent!important;border:none!important;border-radius:0!important;
  color:#3d5068!important;font-family:'DM Sans',sans-serif!important;
  font-size:.8rem!important;font-weight:400!important;
  padding:.65rem 1.1rem!important;width:auto!important;
  border-bottom:2px solid transparent!important;
  white-space:nowrap!important;letter-spacing:.01em!important;
  transition:color .15s,border-color .15s!important;
}
.vg-tabrow div[data-testid="column"] .stButton>button:hover{
  background:transparent!important;color:#94a3b8!important;
}
/* Active tab: use primary type → style as active */
.vg-tabrow div[data-testid="column"] .stButton>button[kind="primary"]{
  color:#e2e8f0!important;font-weight:500!important;
  border-bottom-color:#2563eb!important;background:transparent!important;
}
/* Admin tabs */
.vg-tabrow div[data-testid="column"].admin-col .stButton>button{color:#5a4830!important;}
.vg-tabrow div[data-testid="column"].admin-col .stButton>button[kind="primary"]{
  color:#fbbf24!important;border-bottom-color:#d97706!important;
}
/* Remove Streamlit column padding inside tabrow */
.vg-tabrow div[data-testid="column"]{padding:0!important;flex:0 0 auto!important;}

/* ─── PAGE SHELL ─── */
.vg-shell{background:#0f2240;width:100%;}
.vg-wrap{max-width:1080px;margin:0 auto;padding:.75rem 2rem 2rem;}

/* ─── PAGE HEADER ─── */
.vg-page-head{border-bottom:1px solid rgba(255,255,255,.05);
  padding:.75rem 0 .75rem;margin-bottom:1rem;}

/* ─── CARDS ─── */
.vg-card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:10px;padding:1.25rem;margin-bottom:.75rem;}
.vg-card-flat{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);
  border-radius:8px;padding:.85rem 1rem;margin-bottom:.6rem;}

/* ─── TYPOGRAPHY ─── */
.vg-h1{font-family:'Syne',sans-serif;font-size:1.45rem;font-weight:800;
  color:#f1f5f9;letter-spacing:-.03em;margin:0 0 .2rem;line-height:1.2;display:inline;}
.vg-h1 em{font-style:normal;color:#60a5fa;}
.vg-h2{font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;
  color:#e2e8f0;margin:0 0 .6rem;}
.vg-h3{font-family:'Syne',sans-serif;font-size:.875rem;font-weight:700;
  color:#cbd5e1;margin:0 0 .3rem;}
.vg-sub{color:#4b6080;font-size:.8rem;font-weight:400;
  line-height:1.55;margin:.3rem 0 0;display:block;}
.vg-mono{font-family:'DM Mono',monospace;font-size:.65rem;color:#3d5068;
  letter-spacing:.06em;text-transform:uppercase;}

/* ─── BADGE ─── */
.vg-badge{display:inline-flex;align-items:center;gap:.3rem;
  background:rgba(37,99,235,.1);border:1px solid rgba(59,130,246,.2);
  color:#93c5fd;font-size:.62rem;font-weight:600;
  letter-spacing:.08em;text-transform:uppercase;
  padding:.2rem .7rem;border-radius:999px;}

/* ─── VERDICT CHIPS ─── */
.v-VERIFIED      {background:rgba(22,163,74,.1); color:#4ade80;border:1px solid rgba(22,163,74,.2);}
.v-FALSE         {background:rgba(220,38,38,.1); color:#f87171;border:1px solid rgba(220,38,38,.2);}
.v-PARTIAL       {background:rgba(217,119,6,.1); color:#fbbf24;border:1px solid rgba(217,119,6,.2);}
.v-UNCORROBORATED{background:rgba(71,85,105,.1); color:#64748b;border:1px solid rgba(71,85,105,.2);}
.v-UNAVAILABLE   {background:rgba(37,99,235,.1); color:#93c5fd;border:1px solid rgba(37,99,235,.2);}
.v-ERROR         {background:rgba(220,38,38,.1); color:#f87171;border:1px solid rgba(220,38,38,.2);}
.vchip{display:inline-block;padding:.2rem .65rem;border-radius:5px;
  font-family:'Syne',sans-serif;font-weight:700;font-size:.75rem;}

/* ─── TIER CHIPS ─── */
.t-free {background:rgba(71,85,105,.15);color:#64748b;border:1px solid rgba(71,85,105,.25);}
.t-pro  {background:rgba(37,99,235,.15);color:#93c5fd;border:1px solid rgba(37,99,235,.25);}
.t-inst {background:rgba(22,163,74,.15);color:#4ade80;border:1px solid rgba(22,163,74,.25);}
.t-admin{background:rgba(217,119,6,.15);color:#fbbf24;border:1px solid rgba(217,119,6,.25);}
.tchip{display:inline-block;padding:.12rem .55rem;border-radius:999px;
  font-family:'DM Mono',monospace;font-size:.6rem;letter-spacing:.04em;text-transform:uppercase;}

/* ─── TRUTH BAR ─── */
.tbar-bg{height:7px;background:rgba(255,255,255,.07);border-radius:99px;overflow:hidden;margin:.45rem 0;}
.tbar-fill{height:100%;border-radius:99px;}
.tbar-green {background:linear-gradient(90deg,#16a34a,#4ade80);}
.tbar-orange{background:linear-gradient(90deg,#d97706,#fbbf24);}
.tbar-red   {background:linear-gradient(90deg,#dc2626,#f87171);}
.tbar-gray  {background:linear-gradient(90deg,#475569,#94a3b8);}

/* ─── SCORE ─── */
.score-num{font-family:'Syne',sans-serif;font-size:2.75rem;font-weight:800;line-height:1;}
.sc-green{color:#4ade80;}.sc-orange{color:#fbbf24;}.sc-red{color:#f87171;}.sc-gray{color:#64748b;}

/* ─── STAT PILLS ─── */
.spill{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  border-radius:8px;padding:.75rem 1rem;text-align:center;}
.spill-n{font-family:'Syne',sans-serif;font-size:1.35rem;font-weight:800;
  color:#fff;display:block;letter-spacing:-.02em;}
.spill-l{font-size:.6rem;color:#3d5068;font-family:'DM Mono',monospace;
  letter-spacing:.06em;text-transform:uppercase;display:block;margin-top:.15rem;}

/* ─── SOURCE ROWS ─── */
.src-row{display:flex;align-items:flex-start;gap:.45rem;
  padding:.45rem 0;border-bottom:1px solid rgba(255,255,255,.04);}
.src-row:last-child{border-bottom:none;}
.src-dot{width:5px;height:5px;border-radius:50%;background:#3b82f6;flex-shrink:0;margin-top:5px;}
.src-title a{color:#60a5fa;font-size:.8rem;text-decoration:none;line-height:1.4;}
.src-title a:hover{text-decoration:underline;}
.src-by{color:#2d3f55;font-family:'DM Mono',monospace;font-size:.62rem;}

/* ─── INPUTS ─── */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea{
  background:rgba(255,255,255,.05)!important;border:1px solid rgba(255,255,255,.1)!important;
  border-radius:7px!important;color:#f1f5f9!important;
  font-family:'DM Sans',sans-serif!important;font-size:.9rem!important;}
.stTextInput>div>div>input::placeholder,
.stTextArea>div>div>textarea::placeholder{color:rgba(255,255,255,.2)!important;}
.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus{
  border-color:rgba(59,130,246,.5)!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.1)!important;}
.stSelectbox>div>div{background:rgba(255,255,255,.05)!important;
  border:1px solid rgba(255,255,255,.1)!important;
  border-radius:7px!important;color:#f1f5f9!important;}
div[data-baseweb="select"] *{color:#e2e8f0!important;}
label{color:#3d5068!important;font-size:.62rem!important;
  font-family:'DM Mono',monospace!important;
  letter-spacing:.06em!important;text-transform:uppercase!important;}

/* ─── BUTTONS ─── */
.stButton>button{
  background:#ea580c!important;color:#fff!important;border:none!important;
  border-radius:6px!important;font-family:'DM Sans',sans-serif!important;
  font-weight:600!important;font-size:.85rem!important;
  padding:.55rem 1.25rem!important;transition:background .15s!important;
  letter-spacing:.01em!important;width:100%;}
.stButton>button:hover{background:#f97316!important;}
.btn-ghost .stButton>button{background:transparent!important;
  border:1px solid rgba(255,255,255,.1)!important;color:#64748b!important;}
.btn-ghost .stButton>button:hover{background:rgba(255,255,255,.05)!important;color:#94a3b8!important;}
.btn-blue .stButton>button{background:#1d4ed8!important;}
.btn-blue .stButton>button:hover{background:#2563eb!important;}
.btn-green .stButton>button{background:#15803d!important;}
.btn-green .stButton>button:hover{background:#16a34a!important;}
.btn-red .stButton>button{background:transparent!important;
  border:1px solid rgba(220,38,38,.3)!important;color:#f87171!important;}
.btn-red .stButton>button:hover{background:rgba(220,38,38,.1)!important;}

/* ─── ALERTS ─── */
div[data-testid="stAlert"]{border-radius:7px!important;}
.stSuccess{background:rgba(22,163,74,.07)!important;border:1px solid rgba(22,163,74,.2)!important;color:#4ade80!important;}
.stError  {background:rgba(220,38,38,.07)!important;border:1px solid rgba(220,38,38,.2)!important;}
.stWarning{background:rgba(217,119,6,.07)!important;border:1px solid rgba(217,119,6,.2)!important;}
.stInfo   {background:rgba(37,99,235,.07)!important;border:1px solid rgba(37,99,235,.2)!important;}

/* ─── DIVIDER ─── */
hr{border:none!important;border-top:1px solid rgba(255,255,255,.06)!important;margin:.9rem 0!important;}

/* ─── EXPANDER ─── */
.streamlit-expanderHeader{background:rgba(255,255,255,.03)!important;
  border:1px solid rgba(255,255,255,.07)!important;border-radius:7px!important;
  color:#64748b!important;font-family:'DM Sans',sans-serif!important;font-size:.82rem!important;}

/* ─── SPINNER / PROGRESS ─── */
.stSpinner>div{border-top-color:#2563eb!important;}
.stProgress>div>div{background:#2563eb!important;}

/* ─── INNER TABS (login) ─── */
.stTabs [data-baseweb="tab-list"]{background:rgba(255,255,255,.03)!important;
  border:1px solid rgba(255,255,255,.07)!important;border-radius:7px!important;
  padding:.15rem!important;gap:.15rem!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#3d5068!important;
  border-radius:5px!important;font-family:'DM Sans',sans-serif!important;
  font-size:.82rem!important;border:none!important;padding:.4rem .85rem!important;}
.stTabs [aria-selected="true"]{background:rgba(37,99,235,.18)!important;color:#e2e8f0!important;}

/* ─── ADMIN TABLE ─── */
.admin-table{width:100%;border-collapse:collapse;}
.admin-table th{padding:.5rem .85rem;text-align:left;font-family:'DM Mono',monospace;
  font-size:.62rem;color:#3d5068;letter-spacing:.06em;font-weight:500;
  border-bottom:1px solid rgba(255,255,255,.06);}
.admin-table td{padding:.6rem .85rem;font-size:.8rem;color:#e2e8f0;
  border-bottom:1px solid rgba(255,255,255,.04);}
.admin-table tr:hover td{background:rgba(255,255,255,.015);}

/* ─── PLAN CARDS ─── */
.plan-card{border:1px solid rgba(255,255,255,.08);border-radius:10px;overflow:hidden;}
.plan-card.featured{border-color:rgba(37,99,235,.4);}
.plan-header.pro {background:linear-gradient(135deg,#1e3a8a,#1d4ed8);}
.plan-header.inst{background:linear-gradient(135deg,#064e3b,#065f46);}
.plan-header.free{background:#172033;}
.plan-header{padding:1rem 1.25rem;border-bottom:1px solid rgba(255,255,255,.07);}
.plan-body  {padding:1rem 1.25rem;background:rgba(255,255,255,.015);}
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
        Veri<em style="font-style:normal;color:#60a5fa;">Ghana</em>
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
          <span style="font-size:.72rem;color:#2d4060;">
            Admin access: set <code style="color:#60a5fa;font-size:.7rem;">ADMIN_EMAIL</code> in .env
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
          <span style="font-size:.72rem;color:#2d4060;">
            GIMPA students — promo code
            <code style="color:#60a5fa;background:rgba(37,99,235,.08);
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
        <span style="color:#2d4060;font-family:'DM Mono',monospace;font-size:.68rem;">{email}</span>
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
        pages += [("admin", "Admin", True), ("tester", "Site Tester", True)]

    # Build per-key CSS so each button is styled as a tab item.
    # Active key gets blue underline + bright text; admin keys get amber tint.
    css_rules = """
<style>
/* Tab row container */
div[data-testid="stHorizontalBlock"]:has(> div > div > div > button[data-testid="baseButton-secondary"],
                                          > div > div > div > button[data-testid="baseButton-primary"]) {
  background: rgba(7,15,32,.97) !important;
  border-bottom: 1px solid rgba(255,255,255,.06) !important;
  position: sticky !important;
  top: 52px !important;
  z-index: 200 !important;
  padding: 0 2rem !important;
  gap: 0 !important;
}
/* Column sizing */
div[data-testid="stHorizontalBlock"]:has(> div > div > div > button[data-testid="baseButton-secondary"],
                                          > div > div > div > button[data-testid="baseButton-primary"])
  > div[data-testid="column"] {
  flex: 0 0 auto !important;
  padding: 0 !important;
  min-width: 0 !important;
}
/* All tab buttons base style */
div[data-testid="stHorizontalBlock"]:has(> div > div > div > button[data-testid="baseButton-secondary"],
                                          > div > div > div > button[data-testid="baseButton-primary"])
  button {
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  color: #3d5068 !important;
  font-family: "DM Sans", sans-serif !important;
  font-size: .8rem !important;
  font-weight: 400 !important;
  padding: .65rem 1.1rem !important;
  width: auto !important;
  white-space: nowrap !important;
  box-shadow: none !important;
  transition: color .15s, border-color .15s !important;
}
div[data-testid="stHorizontalBlock"]:has(> div > div > div > button[data-testid="baseButton-secondary"],
                                          > div > div > div > button[data-testid="baseButton-primary"])
  button:hover {
  background: transparent !important;
  color: #94a3b8 !important;
}
/* Active tab = primary button type */
div[data-testid="stHorizontalBlock"]:has(> div > div > div > button[data-testid="baseButton-secondary"],
                                          > div > div > div > button[data-testid="baseButton-primary"])
  button[data-testid="baseButton-primary"] {
  color: #e2e8f0 !important;
  font-weight: 500 !important;
  border-bottom-color: #2563eb !important;
  background: transparent !important;
}
</style>"""
    st.markdown(css_rules, unsafe_allow_html=True)

    cols = st.columns(len(pages), gap="small")
    for i, (k, lbl, is_adm) in enumerate(pages):
        with cols[i]:
            is_active = (k == page)
            if st.button(lbl, key=f"nav_{k}",
                         type="primary" if is_active else "secondary",
                         use_container_width=False):
                st.session_state.page = k
                st.rerun()


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
              <div style="font-size:.875rem;color:#94a3b8;line-height:1.65;
                           font-style:italic;margin-top:.75rem;">
                {explanation}
              </div>
            </div>
            """, unsafe_allow_html=True)

            if summary and summary != explanation:
                st.markdown(f"""
                <div class="vg-card" style="margin-top:.75rem;border-left:3px solid #2563eb;">
                  <div class="vg-mono" style="margin-bottom:.5rem;color:#60a5fa;">AI ANALYSIS SUMMARY</div>
                  <div style="font-size:.875rem;color:#cbd5e1;line-height:1.7;">{summary}</div>
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
          <span style="color:#94a3b8;font-size:.875rem;font-style:italic;">
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
                            f'<div style="color:#e2e8f0;font-size:.82rem;padding:.25rem 0;">'
                            f'<span style="color:#60a5fa;">•</span> '
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
                      <div style="color:#94a3b8;font-size:.875rem;line-height:1.6;font-style:italic;margin-top:.75rem;">
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
          {"<div style='color:#4ade80;font-family:Syne,sans-serif;font-size:1.5rem;font-weight:800;'>Unlimited</div>"
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
        st.markdown('<div class="vg-h2">Upgrade Your Plan</div>', unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        with p1:
            st.markdown("""
            <div class="plan-card featured">
              <div class="plan-header pro">
                <div class="vg-mono" style="color:rgba(255,255,255,.5);margin-bottom:.4rem;">MOST POPULAR</div>
                <div class="vg-h3" style="color:#fff;">Pro — $9.99/mo</div>
                <div style="color:rgba(255,255,255,.6);font-size:.8rem;">Journalists &amp; researchers</div>
              </div>
              <div class="plan-body">
                <ul style="color:#e2e8f0;font-size:.875rem;padding-left:1.25rem;line-height:2.1;margin:0;">
                  <li>Unlimited verifications</li>
                  <li>All 4 AI models</li>
                  <li>3 REST API keys</li>
                  <li>Export history · Real-time alerts</li>
                </ul>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.text_input("Promo code", placeholder="GIMPA2026 · PRESS50", key="promo_pro")
            st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
            if st.button("Upgrade to Pro", key="up_pro", use_container_width=True):
                st.info("Payment integration coming soon. Use code GIMPA2026 for 50% off.")
            st.markdown('</div>', unsafe_allow_html=True)

        with p2:
            st.markdown("""
            <div class="plan-card">
              <div class="plan-header inst">
                <div class="vg-mono" style="color:rgba(255,255,255,.5);margin-bottom:.4rem;">INSTITUTIONAL</div>
                <div class="vg-h3" style="color:#fff;">Institutional — $79.99/mo</div>
                <div style="color:rgba(255,255,255,.6);font-size:.8rem;">Newsrooms, NGOs &amp; gov't</div>
              </div>
              <div class="plan-body">
                <ul style="color:#e2e8f0;font-size:.875rem;padding-left:1.25rem;line-height:2.1;margin:0;">
                  <li>Everything in Pro</li>
                  <li>Bulk verify (20 claims)</li>
                  <li>20 API keys · 20 team seats</li>
                  <li>White-label reports</li>
                </ul>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('<div class="btn-green">', unsafe_allow_html=True)
            if st.button("Contact Sales", key="up_inst", use_container_width=True):
                st.info("sales@verighana.gh")
            st.markdown('</div>', unsafe_allow_html=True)

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
    st.markdown("""
    <div class="vg-page-head">
      <div class="vg-h1">Admin <em>Dashboard</em></div>
      <div class="vg-sub">Platform statistics, user management and promo controls.</div>
    </div>
    """, unsafe_allow_html=True)

    articles, sources_count = 0, 0
    if DB_OK:
        try:
            sb            = get_supabase_client()
            articles      = sb.table("fact_entries").select("id",count="exact").execute().count or 0
            sources_count = sb.table("trusted_sources").select("id",count="exact").execute().count or 0
        except Exception: pass

    s1,s2,s3,s4 = st.columns(4)
    for col,(val,lbl) in zip([s1,s2,s3,s4],[
        (f"{articles:,}","Articles Indexed"),
        (f"{sources_count:,}","Trusted Sources"),
        (len(st.session_state.history),"Session Checks"),
        (len(SITES_TO_TEST),"Sites in Test List"),
    ]):
        with col:
            st.markdown(f'<div class="spill"><span class="spill-n">{val}</span>'
                        f'<span class="spill-l">{lbl}</span></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    ad1, ad2 = st.columns([1.6, 1])

    with ad1:
        st.markdown('<div class="vg-h3" style="margin-bottom:1rem;">Promo Codes</div>',
                    unsafe_allow_html=True)
        promos = [
            ("GIMPA2026","Discount","50% off","200","Active","#4ade80"),
            ("PRESS50",  "Discount","50% off", "50","Active","#4ade80"),
            ("NGOFREE30","Tier Unlock","Pro 30d","30","Active","#4ade80"),
            ("LAUNCH100","Discount","100% off","100","Active","#4ade80"),
        ]
        rows = ""
        for code,typ,disc,mx,status,sc_color in promos:
            rows += (f"<tr><td style='color:#60a5fa;font-family:\"DM Mono\",monospace;'>{code}</td>"
                     f"<td>{typ}</td><td>{disc}</td><td>0 / {mx}</td>"
                     f"<td><span style='color:{sc_color};'>● {status}</span></td></tr>")
        st.markdown(f"""
        <div class="vg-card" style="padding:0;overflow:hidden;">
          <table class="admin-table">
            <thead><tr><th>CODE</th><th>TYPE</th><th>DISCOUNT</th><th>USES</th><th>STATUS</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """, unsafe_allow_html=True)

    with ad2:
        st.markdown('<div class="vg-h3" style="margin-bottom:1rem;">Create Promo Code</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="vg-card">', unsafe_allow_html=True)
        np_code = st.text_input("Code", placeholder="NEWCODE2026", key="np_code")
        np_type = st.selectbox("Type", ["discount","tier_unlock"], key="np_type")
        np_disc = st.slider("Discount %", 0, 100, 50, key="np_disc")
        np_max  = st.number_input("Max uses", 1, 10000, 100, key="np_max")
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Create Code", key="create_promo", use_container_width=True):
            if np_code:
                st.success(f"Code {np_code.upper()} created.")
            else:
                st.error("Enter a code name.")
        st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="vg-h2" style="margin-bottom:1rem;">Scraper Controls</div>',
                unsafe_allow_html=True)
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Run RSS Scraper", key="run_rss", use_container_width=True):
            with st.spinner("Running…"):
                try:
                    from scraper import run_scraper; run_scraper()
                    st.success("RSS scraper done.")
                except Exception as e: st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
    with sc2:
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Run HTML Scraper", key="run_html", use_container_width=True):
            with st.spinner("Running…"):
                try:
                    from scrapers.html_scraper import run_html_ingestion
                    run_html_ingestion(); st.success("HTML scraper done.")
                except Exception as e: st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
    with sc3:
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("Run Embedder", key="run_embed", use_container_width=True):
            with st.spinner("Running…"):
                try:
                    from embedder import run_embedder
                    run_embedder(); st.success("Embedder done.")
                except Exception as e: st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)

    # ── LLM Diagnostics
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown("""
    <div class="vg-h2" style="margin-bottom:.25rem;">LLM Diagnostics</div>
    <div class="vg-sub" style="margin-bottom:1.5rem;">
      Run live checks against each AI provider and your Supabase database.<br>
      Tests: API reachability &nbsp;·&nbsp; DB index readable &nbsp;·&nbsp; Narrative from facts
    </div>
    """, unsafe_allow_html=True)

    diag_claim = st.text_input(
        "Test claim",
        value="The government of Ghana has increased fuel prices",
        key="diag_claim",
        help="Use a real claim you know exists in your database for the best DB read test."
    )

    run_diag = st.button("Run Full Diagnostics", key="run_diag", type="primary")

    def _badge(status, msg=""):
        cfg = {
            "PASS": ("#4ade80", "#052e16", "PASS"),
            "FAIL": ("#f87171", "#2d0a0a", "FAIL"),
            "SKIP": ("#94a3b8", "#1e293b", "SKIP"),
        }
        c, bg, lbl = cfg.get(status, cfg["SKIP"])
        detail = f' <span style="color:#94a3b8;font-size:.74rem;">{msg}</span>' if msg else ""
        return (f'<span style="background:{bg};color:{c};border:1px solid {c}33;'
                f'padding:.2rem .6rem;border-radius:4px;font-size:.74rem;'
                f'font-family:\'DM Mono\',monospace;font-weight:600;">{lbl}</span>{detail}')

    def _row(prov, check, status, detail=""):
        return (f"<tr><td style='color:#cbd5e1;font-weight:600;'>{prov}</td>"
                f"<td style='color:#94a3b8;'>{check}</td>"
                f"<td>{_badge(status, detail)}</td></tr>")

    if run_diag:
        import re as _re, json as _json
        import requests as _req
        rows_html = ""
        full_log  = []

        def _safe_key(k):
            return (k or "").encode("ascii", errors="ignore").decode("ascii").strip()

        providers = [
            ("Gemini",     _safe_key(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY","")), "gemini"),
            ("Groq",       _safe_key(os.getenv("GROQ_API_KEY","")),        "groq"),
            ("Cohere",     _safe_key(os.getenv("COHERE_API_KEY","")),      "cohere"),
            ("OpenRouter", _safe_key(os.getenv("OPENROUTER_API_KEY","")),  "openrouter"),
        ]

        total_steps = len(providers) * 3 + 2
        step_n = [0]
        bar = st.progress(0, text="Starting diagnostics...")

        def _tick(msg=""):
            step_n[0] = min(step_n[0] + 1, total_steps)
            bar.progress(step_n[0] / total_steps, text=msg)

        _tick("Checking Supabase connection...")
        try:
            sb  = get_supabase_client()
            cnt = sb.table("fact_entries").select("id", count="exact").execute().count or 0
            rows_html += _row("Supabase", "1. Connection + row count", "PASS", f"{cnt:,} rows in fact_entries")
            full_log.append(f"[DB-CONNECT] PASS - {cnt:,} rows")
        except Exception as e:
            cnt = 0
            rows_html += _row("Supabase", "1. Connection + row count", "FAIL", str(e)[:80])
            full_log.append(f"[DB-CONNECT] FAIL - {e}")

        _tick("Testing keyword search...")
        db_results = []
        db_search_errors = []
        try:
            sb2   = get_supabase_client()
            probe = sb2.table("fact_entries").select("*").limit(1).execute()
            actual_cols = list(probe.data[0].keys()) if probe.data else []
            full_log.append(f"[DB-COLS] {actual_cols}")

            import re as _re2
            raw_words = [w.lower() for w in _re2.findall(r"[a-zA-Z]{3,}", diag_claim)]
            full_log.append(f"[DB-WORDS] extracted: {raw_words}")

            text_cols = [c for c in ["title","content","headline","body","text","description"]
                         if c in actual_cols]
            full_log.append(f"[DB-TEXT-COLS] searchable: {text_cols}")

            for word in raw_words[:8]:
                if db_results:
                    break
                for col in text_cols[:2]:
                    try:
                        r = sb2.table("fact_entries").select("*").ilike(col, f"%{word}%").limit(5).execute()
                        if r.data:
                            db_results.extend(r.data)
                            full_log.append(f"[DB-SEARCH] ilike {col} LIKE %{word}% -> {len(r.data)} rows")
                            break
                        else:
                            full_log.append(f"[DB-SEARCH] ilike {col} LIKE %{word}% -> 0 rows")
                    except Exception as ce:
                        full_log.append(f"[DB-SEARCH] ilike {col} error: {ce}")
                        db_search_errors.append(str(ce)[:60])

            if not db_results:
                full_log.append("[DB-SEARCH] no ilike hits - trying recent rows fallback")
                order_col = "published_date" if "published_date" in actual_cols else (
                    "created_at" if "created_at" in actual_cols else None)
                try:
                    q = sb2.table("fact_entries").select("*")
                    if order_col:
                        q = q.order(order_col, desc=True)
                    r = q.limit(5).execute()
                    if r.data:
                        db_results.extend(r.data)
                        full_log.append(f"[DB-FALLBACK] got {len(r.data)} recent rows")
                except Exception as fe:
                    full_log.append(f"[DB-FALLBACK] failed: {fe}")

            if db_results:
                def _norm(row):
                    return {
                        "id":             row.get("id",""),
                        "title":          row.get("title") or row.get("headline") or row.get("body","")[:80],
                        "content":        row.get("content") or row.get("body") or row.get("text",""),
                        "url_link":       row.get("url_link") or row.get("url","#"),
                        "source_name":    row.get("source_name") or row.get("source","Unknown"),
                        "published_date": row.get("published_date") or row.get("created_at",""),
                    }
                db_results = [_norm(r) for r in db_results]
                sample = " | ".join(r.get("title","?")[:40] for r in db_results[:2])
                rows_html += _row("Supabase", "2. Keyword search (fact_entries)", "PASS",
                                  f"{len(db_results)} rows - e.g. {sample}")
                full_log.append(f"[DB-SEARCH] PASS - {len(db_results)} results")
            else:
                err_detail = (" | ".join(db_search_errors[:2])) if db_search_errors else "unknown"
                rows_html += _row("Supabase", "2. Keyword search (fact_entries)", "FAIL",
                                  f"0 results. Cols={actual_cols[:5]} Words={raw_words[:4]} Err={err_detail}")
                full_log.append(f"[DB-SEARCH] FAIL - cols={actual_cols} words={raw_words}")
        except Exception as e:
            rows_html += _row("Supabase", "2. Keyword search (fact_entries)", "FAIL", str(e)[:120])
            full_log.append(f"[DB-SEARCH] FAIL - {e}")

        src_block = "\n".join(
            f"[{i+1}] {r.get('source_name','?')} - {r.get('title','?')}: {(r.get('content') or '')[:150]}"
            for i, r in enumerate(db_results[:3])
        ) or "(no sources found in database)"

        narr_prompt = (
            "You are VeriGhana, a Ghana fact-checker.\n\n"
            f"CLAIM: {diag_claim}\n\nSOURCES:\n{src_block}\n\n"
            "Return ONLY valid JSON: "
            '{"verdict":"VERIFIED or PARTIAL or FALSE or UNCORROBORATED",'
            '"score":50,"summary":"2-3 sentence narrative from the sources above"}'
        )

        for pname, akey, pkey in providers:
            _tick(f"Testing {pname} API...")

            if not akey:
                for chk in ("1. API reachability", "2. DB index readable", "3. Narrative from facts"):
                    rows_html += _row(pname, chk, "SKIP", "No API key in .env")
                full_log.append(f"[{pname.upper()}] SKIP - no key")
                step_n[0] = min(step_n[0] + 2, total_steps)
                continue

            api_ok, api_msg, narr_raw = False, "", None
            try:
                ping = '{"ok": true}'
                if pkey == "gemini":
                    try:
                        import google.generativeai as _gnai
                        _gnai.configure(api_key=akey)
                        _gnai.GenerativeModel("gemini-2.0-flash").generate_content(
                            ping, generation_config={"max_output_tokens": 10, "temperature": 0}
                        )
                        api_ok, api_msg = True, "gemini-2.0-flash responded"
                    except ImportError:
                        api_msg = "google-generativeai not installed. Run: pip install google-generativeai"
                elif pkey == "groq":
                    r = _req.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json"},
                        json={"model": "llama-3.1-8b-instant",
                              "messages": [{"role": "user", "content": ping}],
                              "max_tokens": 10, "temperature": 0,
                              "response_format": {"type": "json_object"}},
                        timeout=15
                    )
                    r.raise_for_status()
                    api_ok, api_msg = True, f"llama-3.1-8b-instant responded (HTTP {r.status_code})"
                elif pkey == "cohere":
                    r = _req.post(
                        "https://api.cohere.com/v2/chat",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json",
                                 "Accept": "application/json"},
                        json={"model": "command-r", "messages": [{"role": "user", "content": ping}],
                              "max_tokens": 10, "temperature": 0},
                        timeout=15
                    )
                    r.raise_for_status()
                    api_ok, api_msg = True, f"command-r responded (HTTP {r.status_code})"
                elif pkey == "openrouter":
                    r = _req.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {akey}", "Content-Type": "application/json",
                                 "HTTP-Referer": "https://verighana.gh", "X-Title": "VeriGhana"},
                        json={"model": "meta-llama/llama-3.3-70b-instruct:free",
                              "messages": [{"role": "user", "content": ping}],
                              "max_tokens": 10, "temperature": 0},
                        timeout=15
                    )
                    r.raise_for_status()
                    api_ok, api_msg = True, f"llama-3.3-70b:free responded (HTTP {r.status_code})"
            except Exception as e:
                api_msg = str(e)[:90]

            rows_html += _row(pname, "1. API reachability (ping)", "PASS" if api_ok else "FAIL", api_msg)
            full_log.append(f"[{pname.upper()}-API] {'PASS' if api_ok else 'FAIL'} - {api_msg}")
            _tick(f"{pname}: narrative test...")

            if not api_ok:
                rows_html += _row(pname, "2. DB index readable", "SKIP", "API unreachable")
                rows_html += _row(pname, "3. Narrative from facts", "SKIP", "API unreachable")
                step_n[0] = min(step_n[0] + 1, total_steps)
                continue

            narr_ok, narr_msg, db_ok, db_msg = False, "", False, ""
            try:
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
                        timeout=25
                    )
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
                        timeout=25
                    )
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
                        timeout=25
                    )
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
                        db_ok  = _ov >= 3
                        db_msg = (f"Model references DB content ({_ov} shared keywords)"
                                  if db_ok else f"Low keyword overlap ({_ov}) - model may not be using DB")
                    elif summary:
                        db_ok, db_msg = True, "Valid response (no DB sources to cross-check)"
                    else:
                        db_ok, db_msg = False, "JSON missing summary field"

                    narr_ok  = bool(summary) and len(summary) > 20
                    narr_msg = (f"[{verdict} | {score}/100] {summary[:130]}..."
                                if narr_ok else f"Summary missing or short: {str(_obj)[:80]}")

            except Exception as e:
                db_msg   = f"Error: {str(e)[:80]}"
                narr_msg = db_msg

            rows_html += _row(pname, "2. DB index readable by model", "PASS" if db_ok else "FAIL", db_msg)
            rows_html += _row(pname, "3. Narrative from facts", "PASS" if narr_ok else "FAIL", narr_msg)
            full_log.append(f"[{pname.upper()}-DB]   {'PASS' if db_ok else 'FAIL'} - {db_msg}")
            full_log.append(f"[{pname.upper()}-NARR] {'PASS' if narr_ok else 'FAIL'} - {narr_msg}")
            _tick(f"{pname} done.")

        bar.empty()

        st.markdown(f"""
        <div class="vg-card" style="padding:0;overflow:hidden;margin-top:1rem;">
          <table class="admin-table">
            <thead><tr>
              <th style="width:120px;">PROVIDER</th>
              <th>CHECK</th>
              <th>RESULT</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Raw diagnostic log"):
            st.code("\n".join(full_log), language="text")

        passes = rows_html.count(">PASS<")
        fails  = rows_html.count(">FAIL<")
        skips  = rows_html.count(">SKIP<")
        if fails == 0:
            st.success(f"All checks passed ({passes} PASS, {skips} SKIP)")
        else:
            st.warning(f"{fails} check(s) failed | {passes} passed | {skips} skipped")

    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: SITE TESTER
# ══════════════════════════════════════════════
def page_tester():
    st.markdown('<div class="vg-shell"><div class="vg-wrap">', unsafe_allow_html=True)
    st.markdown("""
    <div class="vg-page-head">
      <div class="vg-h1">Site <em>Tester</em></div>
      <div class="vg-sub">
        Test Ghanaian sources for scrapability. Sites that pass are
        <strong style="color:#fff;">automatically added</strong> to
        <code style="color:#60a5fa;background:rgba(37,99,235,.1);
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
                    f'<span style="color:#60a5fa;">{site["url"]}</span></div>',
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
                            <div style="color:#e2e8f0;font-size:.875rem;line-height:1.8;">
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
                            f'<div style="padding:.5rem 0;color:#94a3b8;font-size:.875rem;">'
                            f'{icon} <strong style="color:#e2e8f0;">{result["name"]}</strong>'
                            f' — {label}</div>',
                            unsafe_allow_html=True,
                        )

                refresh_counters(results_store)
                progress_bar.progress((i + 1) / len(sites_to_run))
                time.sleep(delay)

            status_text.markdown(
                '<div class="vg-mono" style="color:#4ade80;">All tests complete.</div>',
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
                    f'<div style="padding:.4rem 0;color:#94a3b8;font-size:.875rem;">'
                    f'{icon} <strong style="color:#e2e8f0;">{result["name"]}</strong>'
                    f' — {label}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown('</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  MAIN ROUTER
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
    elif p == "admin"  and admin:     page_admin()
    elif p == "tester" and admin:     page_tester()
    else:
        st.session_state.page = "verify"; st.rerun()

    st.markdown(
        '<div style="text-align:center;padding:2rem;font-size:.72rem;color:#334155;">'
        'VeriGhana © 2026 — GIMPA Computer Science Research — '
        'Combating information disorder in Ghana with AI.</div>',
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()