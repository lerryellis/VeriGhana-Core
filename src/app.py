import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from verifier import verify_claim, FREE_MODELS, DEFAULT_MODEL
from database_utils import get_supabase_client
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import time
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# ── Admin email (set ADMIN_EMAIL=you@example.com in your .env file)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

st.set_page_config(
    page_title="VeriGhana — National Fact Verification",
    page_icon="🇬🇭",
    layout="wide"
)

# ─────────────────────────────────────────────
#  SESSION STATE DEFAULTS
# ─────────────────────────────────────────────
for key, default in {
    "logged_in":    False,
    "user_email":   "",
    "test_results": [],
    "testing":      False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ─────────────────────────────────────────────
#  SITE TESTER CONSTANTS
# ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
    {"name": "Citi Newsroom",           "url": "https://citinewsroom.com/category/news/",            "category": "Media"},
    {"name": "Joy Online",              "url": "https://www.myjoyonline.com/news/",                  "category": "Media"},
    {"name": "Graphic Online",          "url": "https://www.graphic.com.gh/news/general-news.html",  "category": "Media"},
    {"name": "Ghana News Agency",       "url": "https://www.ghananewsagency.org/",                   "category": "Media"},
    {"name": "3News",                   "url": "https://3news.com/",                                 "category": "Media"},
    {"name": "Peacefm Online",          "url": "https://www.peacefmonline.com/",                     "category": "Media"},
    {"name": "GhanaWeb",                "url": "https://www.ghanaweb.com/",                          "category": "Media"},
    {"name": "Pulse Ghana",             "url": "https://www.pulse.com.gh/",                          "category": "Media"},
    {"name": "Office of the President", "url": "https://presidency.gov.gh/",                         "category": "Government - Executive"},
    {"name": "Ghana Government Portal", "url": "https://www.ghana.gov.gh/",                          "category": "Government - Executive"},
    {"name": "Ministry of Foreign Affairs",    "url": "https://mfa.gov.gh/",                         "category": "Government - Ministry"},
    {"name": "Ministry of Finance",            "url": "https://mofep.gov.gh/",                       "category": "Government - Ministry"},
    {"name": "Ministry of Education",          "url": "https://moe.gov.gh/",                         "category": "Government - Ministry"},
    {"name": "Ministry of Energy",             "url": "https://www.energymin.gov.gh/",               "category": "Government - Ministry"},
    {"name": "Ministry of Health",             "url": "https://www.moh.gov.gh/",                     "category": "Government - Ministry"},
    {"name": "Ministry of Roads and Highways", "url": "https://www.mrh.gov.gh/",                     "category": "Government - Ministry"},
    {"name": "Ministry of Trade and Industry", "url": "http://www.moti.gov.gh/",                     "category": "Government - Ministry"},
    {"name": "Ministry of Communication",      "url": "https://moc.gov.gh/",                         "category": "Government - Ministry"},
    {"name": "Ministry of the Interior",       "url": "https://www.mint.gov.gh/",                    "category": "Government - Ministry"},
    {"name": "Ministry of Tourism",            "url": "https://www.touringghana.com/",               "category": "Government - Ministry"},
    {"name": "Ministry of Local Government",   "url": "http://www.mlgrd.gov.gh/",                   "category": "Government - Ministry"},
    {"name": "Ministry of Justice",            "url": "https://mojag.gov.gh/",                       "category": "Government - Ministry"},
    {"name": "Ministry of Defence",            "url": "https://mod.gov.gh/",                         "category": "Government - Ministry"},
    {"name": "Parliament of Ghana",            "url": "https://www.parliament.gh/news",              "category": "Government - Legislature"},
    {"name": "Judicial Service of Ghana",      "url": "https://www.judicial.gov.gh/",               "category": "Government - Judiciary"},
    {"name": "Bank of Ghana",                  "url": "https://www.bog.gov.gh/news-publications/press-releases/", "category": "Government - Regulatory"},
    {"name": "Electoral Commission",           "url": "https://www.ec.gov.gh/",                     "category": "Government - Regulatory"},
    {"name": "National Development Planning",  "url": "https://www.ndpc.gov.gh/",                   "category": "Government - Regulatory"},
    {"name": "Public Procurement Authority",   "url": "https://www.ppbghana.org/",                  "category": "Government - Regulatory"},
    {"name": "National Communications Auth",   "url": "https://www.nca.org.gh/",                    "category": "Government - Regulatory"},
    {"name": "Public Utilities Regulatory",    "url": "http://www.purc.com.gh/",                    "category": "Government - Regulatory"},
    {"name": "Ghana Standards Authority",      "url": "https://www.gsa.gov.gh/",                    "category": "Government - Regulatory"},
    {"name": "Food and Drugs Authority",       "url": "https://www.fdaghana.gov.gh/",               "category": "Government - Regulatory"},
    {"name": "National Commission on Culture", "url": "http://www.ghanaculture.gov.gh/",            "category": "Government - Regulatory"},
    {"name": "Ghana Revenue Authority",        "url": "https://gra.gov.gh/",                        "category": "Government - Revenue"},
    {"name": "SSNIT",                          "url": "https://www.ssnit.org.gh/",                  "category": "Government - Social"},
    {"name": "National Health Insurance Auth", "url": "https://www.nhis.gov.gh/",                   "category": "Government - Social"},
    {"name": "National Identification Auth",   "url": "https://nia.gov.gh/",                        "category": "Government - Identification"},
    {"name": "DVLA",                           "url": "https://dvla.gov.gh/",                       "category": "Government - Identification"},
    {"name": "Ghana Education Service",        "url": "https://ges.gov.gh/",                        "category": "Government - Education"},
    {"name": "National Teaching Council",      "url": "https://ntc.gov.gh/",                        "category": "Government - Education"},
    {"name": "National Accreditation Board",   "url": "https://nab.gov.gh/",                        "category": "Government - Education"},
    {"name": "GIMPA",                          "url": "https://www.gimpa.edu.gh/",                  "category": "Government - Education"},
    {"name": "CSIR",                           "url": "http://www.csir.org.gh/",                    "category": "Government - Education"},
    {"name": "Ghana Statistical Service",      "url": "https://www.statsghana.gov.gh/",             "category": "Government - Statistics"},
    {"name": "Ghana Health Service",           "url": "https://ghs.gov.gh/",                        "category": "Government - Health"},
    {"name": "Volta River Authority",          "url": "https://www.vra.com/",                       "category": "Government - Energy"},
    {"name": "GRIDCo",                         "url": "https://www.gridcogh.com/",                  "category": "Government - Energy"},
    {"name": "Energy Commission",              "url": "https://www.energycom.gov.gh/",              "category": "Government - Energy"},
    {"name": "Ghana Investment Promotion",     "url": "https://www.gipcghana.com/",                 "category": "Government - Investment"},
    {"name": "Ghana Export Promotion Auth",    "url": "https://www.gepaghana.org/",                 "category": "Government - Investment"},
    {"name": "Ghana Free Zones Board",         "url": "https://gfzb.gov.gh/",                      "category": "Government - Investment"},
    {"name": "Ghana Tourism Authority",        "url": "https://www.ghana.travel/",                  "category": "Government - Investment"},
    {"name": "Ghana Armed Forces",             "url": "https://gafonline.mil.gh/",                  "category": "Government - Security"},
    {"name": "Ghana Police Service",           "url": "https://www.police.gov.gh/",                 "category": "Government - Security"},
    {"name": "NITA",                           "url": "https://nita.gov.gh/",                       "category": "Government - Technology"},
    {"name": "Cyber Security Authority",       "url": "https://www.csa.gov.gh/",                   "category": "Government - Technology"},
    {"name": "Data Protection Commission",     "url": "https://dataprotection.gov.gh/",            "category": "Government - Technology"},
    {"name": "Securities and Exchange Comm",   "url": "https://sec.gov.gh/",                       "category": "Government - Finance"},
    {"name": "National Insurance Commission",  "url": "https://nicghana.org/",                     "category": "Government - Finance"},
    {"name": "NPRA",                           "url": "https://www.npra.gov.gh/",                   "category": "Government - Finance"},
    {"name": "CAGD",                           "url": "https://cagd.gov.gh/",                       "category": "Government - Finance"},
    {"name": "Association of Ghana Industries","url": "https://www.agighana.org/",                  "category": "Government - Business"},
    {"name": "Private Enterprise Federation",  "url": "https://pef.org.gh/",                       "category": "Government - Business"},
    {"name": "Local Government Service",       "url": "https://lgs.gov.gh/",                       "category": "Government - Local"},
]


# ─────────────────────────────────────────────
#  SITE TESTER CORE LOGIC
# ─────────────────────────────────────────────
def test_single_site(site: dict) -> dict:
    """Test one site and return a result dict."""
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

    from urllib.parse import urlparse
    parsed   = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Resolve relative hrefs in samples
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
    """Write a verified site into html_scraper.py's HTML_SOURCES."""
    try:
        from source_manager import add_source_to_scraper
        return add_source_to_scraper(result)
    except ImportError:
        return {"success": False, "skipped": False, "message": "source_manager.py not found."}


# ─────────────────────────────────────────────
#  STATUS HELPERS
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
#  LOGIN SCREEN
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    st.title("🇬🇭 VeriGhana")
    st.subheader("Please log in to access the verification platform")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        email    = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            try:
                supabase = get_supabase_client()
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.logged_in  = True
                st.session_state.user_email = email
                st.rerun()
            except Exception:
                st.error("Login failed. Check your email and password.")

    with tab2:
        new_email = st.text_input("Email Address", key="reg_email")
        new_pass  = st.text_input("Password (minimum 6 characters)", type="password", key="reg_pass")
        if st.button("Create Account"):
            try:
                supabase = get_supabase_client()
                supabase.auth.sign_up({"email": new_email, "password": new_pass})
                st.success("Account created! Check your email to confirm, then log in.")
            except Exception as e:
                st.error(f"Registration failed: {e}")

# ─────────────────────────────────────────────
#  MAIN APP (logged in)
# ─────────────────────────────────────────────
else:
    is_admin = (
        ADMIN_EMAIL != "" and
        st.session_state.user_email.lower().strip() == ADMIN_EMAIL.lower().strip()
    )

    # Header
    col_title, col_logout = st.columns([5, 1])
    with col_title:
        st.title("🇬🇭 VeriGhana")
        st.subheader("Ghana's Centralized Automated Verification Platform")
    with col_logout:
        st.write("")
        st.write("")
        if st.button("Logout"):
            st.session_state.logged_in  = False
            st.session_state.user_email = ""
            st.rerun()

    st.markdown("---")

    # ── Tab bar — admins get an extra "Admin" tab
    if is_admin:
        tab_verify, tab_admin = st.tabs(["🔎 Verify a Claim", "⚙️ Admin — Site Tester"])
    else:
        tab_verify, = st.tabs(["🔎 Verify a Claim"])

    # ─────────────────────────────────────────────
    #  VERIFY TAB
    # ─────────────────────────────────────────────
    with tab_verify:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.header("Verify a Claim")

            st.markdown("**Select AI Model**")
            selected_model_name = st.selectbox(
                label="AI Model",
                options=list(FREE_MODELS.keys()),
                index=list(FREE_MODELS.keys()).index("Gemini 2.0 Flash Lite"),
                help="If one model has reached its daily limit, switch to another.",
                label_visibility="collapsed"
            )
            selected_model_id = FREE_MODELS[selected_model_name]
            st.caption(f"Using: `{selected_model_id}` — All models are free tier. Switch if you see a quota error.")

            user_input = st.text_area(
                "Paste a suspicious post, news card text, or rumour below:",
                height=150,
                placeholder="e.g. Government announces 30% tax on Mobile Money starting Monday..."
            )

            if st.button("Check This Claim", type="primary"):
                if user_input.strip():
                    with st.spinner(f"Searching trusted sources using {selected_model_name}..."):
                        result = verify_claim(user_input, model_id=selected_model_id)

                    verdict     = result.get("verdict", "Unknown")
                    score       = result.get("score", 0)
                    explanation = result.get("explanation", "")
                    sources     = result.get("sources", [])
                    model_used  = result.get("model_used", selected_model_id)

                    if verdict == "Verified":
                        st.success(f"✅ VERDICT: Verified — Confidence: {score}/100")
                        st.progress(score / 100)
                    elif verdict == "False":
                        st.error(f"❌ VERDICT: False — Confidence: {score}/100")
                        st.progress(score / 100)
                    elif verdict == "UNAVAILABLE":
                        st.warning("⏳ AI Model Unavailable")
                        st.info(f"{explanation}\n\n**Try selecting a different model from the dropdown above.**")
                    else:
                        st.warning(f"⚠️ VERDICT: Uncorroborated — Confidence: {score}/100")
                        st.progress(score / 100)

                    st.write(f"**Analysis:** {explanation}")
                    st.caption(f"Checked using: `{model_used}`")

                    if sources:
                        st.subheader("Matching Sources Found:")
                        for source in sources:
                            if isinstance(source, dict):
                                title = source.get("title", "Article")
                                url   = source.get("url", "#")
                                st.write(f"- [{title}]({url})")
                else:
                    st.warning("Please enter a claim to verify.")

        with col2:
            st.header("Database Stats")
            try:
                supabase     = get_supabase_client()
                count_resp   = supabase.table("fact_entries").select("id", count="exact").execute()
                total        = count_resp.count or 0
                st.metric("Total Facts Indexed", f"{total:,}")

                sources_resp = supabase.table("trusted_sources").select("source_name, category").execute()
                st.subheader("Trusted Sources:")
                for s in sources_resp.data:
                    st.write(f"• {s['source_name']} ({s['category']})")
            except Exception as e:
                st.error(f"Could not connect to database: {e}")

            st.markdown("---")
            st.subheader("Available AI Models")
            for name, model_id in FREE_MODELS.items():
                st.write(f"• **{name}** `{model_id}`")
            st.caption("Switch models in the dropdown if one hits its daily limit.")

    # ─────────────────────────────────────────────
    #  ADMIN TAB — only shown to admin
    # ─────────────────────────────────────────────
    if is_admin:
        with tab_admin:
            st.header("⚙️ Site Tester & Source Manager")
            st.markdown(
                "Test any site's scrapability. Sites that pass are **automatically added** to "
                "`html_scraper.py`'s `HTML_SOURCES`."
            )

            # ── Stats bar
            try:
                from source_manager import get_scraper_source_count, get_existing_urls
                current_count    = get_scraper_source_count()
                existing_urls    = get_existing_urls()
            except ImportError:
                current_count    = 0
                existing_urls    = set()

            m1, m2, m3, m4 = st.columns(4)
            total_sites  = len(SITES_TO_TEST)
            already_added = sum(1 for s in SITES_TO_TEST if s["url"] in existing_urls)
            m1.metric("Sites in Test List",        total_sites)
            m2.metric("Already in html_scraper",   already_added)
            m3.metric("Remaining to Test",         total_sites - already_added)
            m4.metric("HTML_SOURCES Total Entries", current_count)

            st.markdown("---")

            # ── Controls
            ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])

            with ctrl1:
                all_categories = sorted(set(s["category"] for s in SITES_TO_TEST))
                selected_cats  = st.multiselect(
                    "Filter by Category",
                    options=["All"] + all_categories,
                    default=["All"]
                )

            with ctrl2:
                skip_existing = st.checkbox(
                    "Skip sites already in html_scraper.py", value=True
                )
                delay = st.slider("Delay between requests (seconds)", 0.5, 3.0, 1.0, 0.5)

            with ctrl3:
                st.write("")
                st.write("")
                run_button = st.button("▶️ Run Tests", type="primary", use_container_width=True)

            # ── Custom URL tester
            with st.expander("➕ Test a Custom URL"):
                c1, c2, c3 = st.columns([2, 2, 1])
                custom_name = c1.text_input("Site Name", placeholder="e.g. My News Site")
                custom_url  = c2.text_input("URL", placeholder="https://example.com/news/")
                custom_cat  = c3.text_input("Category", placeholder="Media")
                if st.button("Test Custom URL"):
                    if custom_url.strip():
                        with st.spinner(f"Testing {custom_url}..."):
                            result = test_single_site({
                                "name":     custom_name or custom_url,
                                "url":      custom_url.strip(),
                                "category": custom_cat or "Custom"
                            })
                        if result["status"] == "scrapeable":
                            st.success(f"✅ Scrapeable — {result['count']} headlines found using `{result['article_tag']}` / `{result['article_class']}`")
                            add_res = auto_add_to_scraper(result)
                            if add_res["skipped"]:
                                st.info(add_res["message"])
                            elif add_res["success"]:
                                st.success(add_res["message"])
                            else:
                                st.error(add_res["message"])
                            for s in result["samples"]:
                                st.write(f"  • [{s['text']}]({s['href']})")
                        else:
                            icon = STATUS_ICON.get(result["status"], "❓")
                            st.warning(f"{icon} {STATUS_LABEL.get(result['status'], result['status'])}")
                    else:
                        st.warning("Please enter a URL.")

            st.markdown("---")

            # ── Run tests
            if run_button:
                # Build list to test
                sites_to_run = []
                for site in SITES_TO_TEST:
                    cat = site.get("category", "")
                    if "All" not in selected_cats and cat not in selected_cats:
                        continue
                    if skip_existing and site["url"] in existing_urls:
                        continue
                    sites_to_run.append(site)

                if not sites_to_run:
                    st.info("No sites to test with current filters.")
                else:
                    st.info(f"Testing **{len(sites_to_run)}** sites — results appear as each completes...")

                    # Live results containers
                    progress_bar  = st.progress(0)
                    status_text   = st.empty()
                    results_store = []

                    # Summary counters (updated live)
                    sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
                    cnt_scrapeable    = sum_col1.empty()
                    cnt_no_headlines  = sum_col2.empty()
                    cnt_blocked       = sum_col3.empty()
                    cnt_unreachable   = sum_col4.empty()

                    results_container = st.container()

                    def refresh_counters(results):
                        sc = sum(1 for r in results if r["status"] == "scrapeable")
                        nh = sum(1 for r in results if r["status"] == "no_headlines")
                        bl = sum(1 for r in results if r["status"] == "blocked")
                        un = sum(1 for r in results if r["status"] not in ["scrapeable", "no_headlines", "blocked"])
                        cnt_scrapeable.metric("✅ Scrapeable",    sc)
                        cnt_no_headlines.metric("⚠️ No Headlines", nh)
                        cnt_blocked.metric("🚫 Blocked",           bl)
                        cnt_unreachable.metric("❌ Unreachable",    un)

                    refresh_counters([])

                    for i, site in enumerate(sites_to_run):
                        status_text.markdown(f"**Testing ({i+1}/{len(sites_to_run)}):** {site['name']} — `{site['url']}`")
                        result = test_single_site(site)
                        results_store.append(result)

                        # Auto-add if scrapeable
                        add_msg = ""
                        if result["status"] == "scrapeable":
                            add_res = auto_add_to_scraper(result)
                            if add_res["skipped"]:
                                add_msg = "_(already in html_scraper.py)_"
                            elif add_res["success"]:
                                add_msg = "🆕 **Auto-added to html_scraper.py**"
                            else:
                                add_msg = f"⚠️ Could not auto-add: {add_res['message']}"

                        # Show result card
                        with results_container:
                            icon  = STATUS_ICON.get(result["status"], "❓")
                            label = STATUS_LABEL.get(result["status"], result["status"])

                            if result["status"] == "scrapeable":
                                with st.expander(
                                    f"{icon} {result['name']} — {result['count']} headlines  |  "
                                    f"`{result['article_tag']}` / `{result['article_class']}`  {add_msg}",
                                    expanded=False
                                ):
                                    st.write(f"**URL:** {result['url']}")
                                    st.write(f"**Base URL:** {result['base_url']}")
                                    st.write(f"**Category:** {result['category']}")
                                    st.write("**Sample Headlines:**")
                                    for s in result["samples"]:
                                        st.write(f"  • [{s['text']}]({s['href']})")
                                    st.code(
                                        f'{{\n'
                                        f'    "name":          "{result["name"]}",\n'
                                        f'    "url":           "{result["url"]}",\n'
                                        f'    "article_tag":   "{result["article_tag"]}",\n'
                                        f'    "article_class": "{result["article_class"]}",\n'
                                        f'    "base_url":      "{result["base_url"]}"\n'
                                        f'}},',
                                        language="python"
                                    )
                            else:
                                st.write(f"{icon} **{result['name']}** — {label} — `{result['url']}`")

                        refresh_counters(results_store)
                        progress_bar.progress((i + 1) / len(sites_to_run))
                        time.sleep(delay)

                    status_text.markdown("✅ **All tests complete.**")
                    st.session_state.test_results = results_store

            # ── Previous results (if any)
            elif st.session_state.test_results:
                st.subheader("Last Test Run Results")
                results = st.session_state.test_results
                sc = [r for r in results if r["status"] == "scrapeable"]
                nh = [r for r in results if r["status"] == "no_headlines"]
                bl = [r for r in results if r["status"] == "blocked"]
                un = [r for r in results if r["status"] not in ["scrapeable", "no_headlines", "blocked"]]

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("✅ Scrapeable",    len(sc))
                m2.metric("⚠️ No Headlines",  len(nh))
                m3.metric("🚫 Blocked",        len(bl))
                m4.metric("❌ Unreachable",    len(un))

                for result in results:
                    icon  = STATUS_ICON.get(result["status"], "❓")
                    label = STATUS_LABEL.get(result["status"], result["status"])
                    if result["status"] == "scrapeable":
                        with st.expander(f"{icon} {result['name']} — {result['count']} headlines  |  `{result['article_tag']}` / `{result['article_class']}`"):
                            for s in result["samples"]:
                                st.write(f"  • [{s['text']}]({s['href']})")
                    else:
                        st.write(f"{icon} **{result['name']}** — {label}")

    st.markdown("---")
    st.caption(
        "VeriGhana uses Retrieval-Augmented Generation to verify claims against "
        "a curated database of trusted Ghanaian sources only."
    )