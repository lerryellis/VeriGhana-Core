"""
VeriGhana Site Tester — Full Strategy Edition
===============================================
Tests every site using ALL six scraping strategies:

  Strategy 1 — HEADLINE TAGS      : h1/h2/h3/h4 with known CSS classes
  Strategy 2 — ARTICLE CONTAINERS : div/article/section wrappers with links inside
  Strategy 3 — LIST ITEMS         : li/td based news lists
  Strategy 4 — DOCUMENT LINKS     : PDF/press release link text (gov portals)
  Strategy 5 — ANCHOR SWEEP       : raw <a> tags filtered by text length + URL pattern
  Strategy 6 — JS RENDER          : headless Chromium via Playwright (last resort)

Usage:
  python site_tester.py            → test all sites
  python site_tester.py media      → only Media category
  python site_tester.py government → all Government categories
  python site_tester.py energy     → any category containing "energy"
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import sys, os, time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from scrapers.bot_identity import BROWSER_HEADERS, BOT_HEADERS, is_challenge_page

HEADERS = BROWSER_HEADERS

# ──────────────────────────────────────────────
#  STRATEGY 1 — HEADLINE TAG PATTERNS
# ──────────────────────────────────────────────
HEADLINE_PATTERNS = [
    ("h1",   None), ("h2",   None), ("h3",   None), ("h4",   None),
    ("h2",   "entry-title"),  ("h3", "entry-title"),  ("h4", "entry-title"),
    ("h2",   "post-title"),   ("h3", "post-title"),   ("h4", "post-title"),
    ("h2",   "article-title"),("h3", "article-title"),
    ("h2",   "title"),        ("h3", "title"),
    ("h2",   "node-title"),   ("h3", "node-title"),
    ("h3",   "jeg_post_title"), ("h2", "jeg_post_title"),
    ("h3",   "td-module-title"),
    ("h2",   "cb-post-title"), ("h3", "cb-post-title"),
    ("h2",   "views-field-title"), ("h3", "views-field-title"),
    ("span", "views-field-title"),
    ("div",  "field-title"),   ("h2", "field-content"), ("h3", "field-content"),
    ("a",    "story-title"),
    ("div",  "article-headline"), ("span", "headline"),
    ("div",  "news-title"),   ("div", "news-list"),
    ("p",    "title"),
    ("li",   "news-item"),
]

# ──────────────────────────────────────────────
#  STRATEGY 2 — ARTICLE CONTAINER PATTERNS
# ──────────────────────────────────────────────
CONTAINER_PATTERNS = [
    ("article", None),  ("article", "post"),    ("article", "article"),
    ("div", "article-card"), ("div", "card"),   ("div", "news-card"),
    ("div", "post-card"),    ("div", "article-item"), ("div", "news-item"),
    ("div", "post-item"),    ("div", "item"),   ("div", "entry"),
    ("div", "post"),         ("div", "article"), ("div", "story"),
    ("div", "story-card"),   ("div", "feature"), ("div", "teaser"),
    ("div", "article-wrapper"), ("div", "post-wrapper"), ("div", "news-wrapper"),
    ("div", "content-item"), ("div", "list-item"), ("div", "grid-item"),
    ("div", "media-body"),   ("div", "media"),
    ("div", "views-row"),    ("div", "node"),   ("div", "view-content"),
    ("div", "press-release"), ("div", "publication-item"), ("div", "news-entry"),
    ("div", "announcement"), ("div", "bulletin"),
    ("section", None), ("section", "article"), ("section", "post"),
    ("li", "article"),       ("li", "post"),    ("li", "item"),
]

# ──────────────────────────────────────────────
#  STRATEGY 3 — LIST ITEM PATTERNS
# ──────────────────────────────────────────────
LIST_PATTERNS = [
    ("li", None), ("li", "news-item"), ("li", "post"), ("li", "article"),
    ("li", "item"), ("li", "list-item"), ("li", "press-item"), ("li", "publication"),
    ("tr", None), ("td", "title"), ("td", "news-title"), ("td", "subject"),
]

# ──────────────────────────────────────────────
#  STRATEGY 4 — DOCUMENT LINK KEYWORDS
# ──────────────────────────────────────────────
DOCUMENT_URL_KEYWORDS = [
    "press", "release", "publication", "report", "news", "statement",
    "bulletin", "communique", "notice", "circular", "announcement",
    "update", "brief", "gazette", "decision", "policy", "budget",
    "speech", "address", ".pdf", "download",
]
DOCUMENT_TEXT_MIN = 12
HEADLINE_TEXT_MIN = 20


# ══════════════════════════════════════════════════════════════
#  SITES LIST
# ══════════════════════════════════════════════════════════════
SITES_TO_TEST = [
    # ── MEDIA ──────────────────────────────────────────────────────
    {"name": "Citi Newsroom",           "url": "https://citinewsroom.com/category/news/",            "category": "Media"},
    {"name": "Joy Online",              "url": "https://www.myjoyonline.com/news/",                  "category": "Media"},
    {"name": "Graphic Online",          "url": "https://www.graphic.com.gh/news/general-news.html",  "category": "Media"},
    {"name": "Ghana News Agency",       "url": "https://www.ghananewsagency.org/",                   "category": "Media"},
    {"name": "3News",                   "url": "https://3news.com/",                                 "category": "Media"},
    {"name": "Peacefm Online",          "url": "https://www.peacefmonline.com/",                     "category": "Media"},
    {"name": "GhanaWeb",                "url": "https://www.ghanaweb.com/",                          "category": "Media"},
    {"name": "Pulse Ghana",             "url": "https://www.pulse.com.gh/",                          "category": "Media"},

    # ── EXECUTIVE ──────────────────────────────────────────────────
    {"name": "Office of the President", "url": "https://presidency.gov.gh/",                         "category": "Government - Executive"},
    {"name": "Ghana Government Portal", "url": "https://www.ghana.gov.gh/",                          "category": "Government - Executive"},

    # ── MINISTRIES ─────────────────────────────────────────────────
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

    # ── LEGISLATURE & JUDICIARY ────────────────────────────────────
    {"name": "Parliament of Ghana",            "url": "https://www.parliament.gh/news",              "category": "Government - Legislature"},
    {"name": "Judicial Service of Ghana",      "url": "https://www.judicial.gov.gh/",               "category": "Government - Judiciary"},

    # ── REGULATORY ─────────────────────────────────────────────────
    {"name": "Bank of Ghana",                  "url": "https://www.bog.gov.gh/news-publications/press-releases/", "category": "Government - Regulatory"},
    {"name": "Electoral Commission",           "url": "https://www.ec.gov.gh/",                     "category": "Government - Regulatory"},
    {"name": "National Development Planning",  "url": "https://www.ndpc.gov.gh/",                   "category": "Government - Regulatory"},
    {"name": "Public Procurement Authority",   "url": "https://www.ppbghana.org/",                  "category": "Government - Regulatory"},
    {"name": "National Communications Auth",   "url": "https://www.nca.org.gh/",                    "category": "Government - Regulatory"},
    {"name": "Public Utilities Regulatory",    "url": "http://www.purc.com.gh/",                    "category": "Government - Regulatory"},
    {"name": "Ghana Standards Authority",      "url": "https://www.gsa.gov.gh/",                    "category": "Government - Regulatory"},
    {"name": "Food and Drugs Authority",       "url": "https://www.fdaghana.gov.gh/",               "category": "Government - Regulatory"},
    {"name": "National Commission on Culture", "url": "http://www.ghanaculture.gov.gh/",            "category": "Government - Regulatory"},

    # ── REVENUE ────────────────────────────────────────────────────
    {"name": "Ghana Revenue Authority",        "url": "https://gra.gov.gh/",                        "category": "Government - Revenue"},

    # ── SOCIAL ─────────────────────────────────────────────────────
    {"name": "SSNIT",                          "url": "https://www.ssnit.org.gh/",                  "category": "Government - Social"},
    {"name": "National Health Insurance Auth", "url": "https://www.nhis.gov.gh/",                   "category": "Government - Social"},

    # ── IDENTIFICATION ─────────────────────────────────────────────
    {"name": "National Identification Auth",   "url": "https://nia.gov.gh/",                        "category": "Government - Identification"},
    {"name": "DVLA",                           "url": "https://dvla.gov.gh/",                       "category": "Government - Identification"},

    # ── EDUCATION ──────────────────────────────────────────────────
    {"name": "Ghana Education Service",        "url": "https://ges.gov.gh/",                        "category": "Government - Education"},
    {"name": "National Teaching Council",      "url": "https://ntc.gov.gh/",                        "category": "Government - Education"},
    {"name": "National Accreditation Board",   "url": "https://nab.gov.gh/",                        "category": "Government - Education"},
    {"name": "GIMPA",                          "url": "https://www.gimpa.edu.gh/",                  "category": "Government - Education"},
    {"name": "CSIR",                           "url": "http://www.csir.org.gh/",                    "category": "Government - Education"},

    # ── STATISTICS ─────────────────────────────────────────────────
    {"name": "Ghana Statistical Service",      "url": "https://www.statsghana.gov.gh/",             "category": "Government - Statistics"},

    # ── HEALTH ─────────────────────────────────────────────────────
    {"name": "Ghana Health Service",           "url": "https://ghs.gov.gh/",                        "category": "Government - Health"},

    # ── ENERGY ─────────────────────────────────────────────────────
    {"name": "Volta River Authority",          "url": "https://www.vra.com/media/index.php",        "category": "Government - Energy"},
    {"name": "GRIDCo",                         "url": "https://www.gridcogh.com/",                  "category": "Government - Energy"},
    {"name": "Energy Commission",              "url": "https://www.energycom.gov.gh/",              "category": "Government - Energy"},

    # ── INVESTMENT & TRADE ─────────────────────────────────────────
    {"name": "Ghana Investment Promotion",     "url": "https://www.gipcghana.com/",                 "category": "Government - Investment"},
    {"name": "Ghana Export Promotion Auth",    "url": "https://www.gepaghana.org/",                 "category": "Government - Investment"},
    {"name": "Ghana Free Zones Board",         "url": "https://gfzb.gov.gh/",                      "category": "Government - Investment"},
    {"name": "Ghana Tourism Authority",        "url": "https://www.ghana.travel/",                  "category": "Government - Investment"},

    # ── SECURITY ───────────────────────────────────────────────────
    {"name": "Ghana Armed Forces",             "url": "https://gafonline.mil.gh/",                  "category": "Government - Security"},
    {"name": "Ghana Police Service",           "url": "https://www.police.gov.gh/",                 "category": "Government - Security"},

    # ── TECHNOLOGY ─────────────────────────────────────────────────
    {"name": "NITA",                           "url": "https://nita.gov.gh/",                       "category": "Government - Technology"},
    {"name": "Cyber Security Authority",       "url": "https://www.csa.gov.gh/",                   "category": "Government - Technology"},
    {"name": "Data Protection Commission",     "url": "https://dataprotection.gov.gh/",            "category": "Government - Technology"},

    # ── FINANCE & BUSINESS ─────────────────────────────────────────
    {"name": "Securities and Exchange Comm",   "url": "https://sec.gov.gh/",                       "category": "Government - Finance"},
    {"name": "National Insurance Commission",  "url": "https://nicghana.org/",                     "category": "Government - Finance"},
    {"name": "NPRA",                           "url": "https://www.npra.gov.gh/",                   "category": "Government - Finance"},
    {"name": "CAGD",                           "url": "https://cagd.gov.gh/",                       "category": "Government - Finance"},
    {"name": "Association of Ghana Industries","url": "https://www.agighana.org/",                  "category": "Government - Business"},
    {"name": "Private Enterprise Federation",  "url": "https://pef.org.gh/",                       "category": "Government - Business"},

    # ── LOCAL GOVERNMENT ───────────────────────────────────────────
    {"name": "Local Government Service",       "url": "https://lgs.gov.gh/",                       "category": "Government - Local"},
]


# ══════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════
def _resolve(href, base_url):
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return base_url.split("://")[0] + ":" + href
    if href.startswith("/"):
        return base_url + href
    return base_url + "/" + href


def _fetch(url):
    """Fetch URL, retry without SSL on certificate errors. Auto-retries with bot identity on challenge pages."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=True)
    except requests.exceptions.SSLError:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        except Exception:
            return {"_error": "ssl_error"}
    except requests.exceptions.ConnectionError:
        return {"_error": "unreachable"}
    except requests.exceptions.Timeout:
        return {"_error": "timeout"}
    except Exception as e:
        return {"_error": str(e)}

    # Detect Akamai/Cloudflare challenge → retry with honest bot identity
    if is_challenge_page(resp):
        print(f"  🤖 Challenge detected — retrying with VeriGhana-Bot identity...")
        try:
            bot_resp = requests.get(url, headers=BOT_HEADERS, timeout=15, verify=True)
        except requests.exceptions.SSLError:
            try:
                bot_resp = requests.get(url, headers=BOT_HEADERS, timeout=15, verify=False)
            except Exception:
                return resp  # return original challenge response
        except Exception:
            return resp

        if not is_challenge_page(bot_resp):
            print(f"  ✅ Bot identity bypassed the challenge successfully")
            return bot_resp
        else:
            print(f"  ⚠️  Bot identity also challenged — site has strict bot protection")

    return resp


def _print_tag_debug(soup):
    print("\n  Heading/container tags found (for manual inspection):")
    for tag in ["h1", "h2", "h3", "h4", "article", "section"]:
        found = soup.find_all(tag)
        if found:
            sample = found[0].get_text(strip=True)[:60]
            print(f"    <{tag}> — {len(found)} found — e.g. \"{sample}\"")


def _print_config_block(name, url, base_url, best):
    scrape_mode   = best.get("scrape_mode", "headline")
    article_tag   = best.get("article_tag")
    article_class = best.get("article_class")
    tag_str       = f'"{article_tag}"'   if article_tag   else "None"
    class_str     = f'"{article_class}"' if article_class else "None"

    print(f"\n✅ ADD THIS TO html_scraper.py HTML_SOURCES:")
    print(f'    {{')
    print(f'        "name":          "{name}",')
    print(f'        "url":           "{url}",')
    print(f'        "scrape_mode":   "{scrape_mode}",')
    print(f'        "article_tag":   {tag_str},')
    print(f'        "article_class": {class_str},')
    print(f'        "base_url":      "{base_url}"')
    print(f'    }},')


# ══════════════════════════════════════════════════════════════
#  STRATEGY RUNNERS  (return best result dict or None)
# ══════════════════════════════════════════════════════════════

def _strategy_headlines(soup, base_url):
    best_tag, best_class, best_count, best_samples = None, None, 0, []
    for tag, css_class in HEADLINE_PATTERNS:
        elements = soup.find_all(tag, class_=css_class) if css_class else soup.find_all(tag)
        found = []
        for el in elements:
            link = el.find("a")
            text = el.get_text(strip=True)
            if link and len(text) >= HEADLINE_TEXT_MIN:
                found.append({"text": text[:100], "href": _resolve(link.get("href",""), base_url)})
        if len(found) > best_count:
            best_count, best_tag, best_class, best_samples = len(found), tag, css_class, found[:3]
    if best_count == 0:
        return None
    return {"scrape_mode": "headline", "article_tag": best_tag,
            "article_class": best_class, "count": best_count, "samples": best_samples}


def _strategy_containers(soup, base_url):
    best_tag, best_class, best_count, best_samples = None, None, 0, []
    for tag, css_class in CONTAINER_PATTERNS:
        elements = soup.find_all(tag, class_=css_class) if css_class else soup.find_all(tag)
        found, seen = [], set()
        for el in elements:
            link = (
                el.find("a", class_=lambda c: c and any(
                    w in str(c).lower() for w in ["title","heading","headline","name"]))
                or el.find("a")
            )
            if not link:
                continue
            text = link.get_text(strip=True) or el.get_text(strip=True)[:100]
            href = _resolve(link.get("href",""), base_url)
            if len(text) >= HEADLINE_TEXT_MIN and href and href not in seen and href != base_url:
                seen.add(href)
                found.append({"text": text[:100], "href": href})
        if len(found) > best_count:
            best_count, best_tag, best_class, best_samples = len(found), tag, css_class, found[:3]
    if best_count < 2:
        return None
    return {"scrape_mode": "container", "article_tag": best_tag,
            "article_class": best_class, "count": best_count, "samples": best_samples}


def _strategy_list_items(soup, base_url):
    best_tag, best_class, best_count, best_samples = None, None, 0, []
    for tag, css_class in LIST_PATTERNS:
        elements = soup.find_all(tag, class_=css_class) if css_class else soup.find_all(tag)
        found, seen = [], set()
        for el in elements:
            link = el.find("a")
            text = el.get_text(strip=True)
            if link and len(text) >= HEADLINE_TEXT_MIN:
                href = _resolve(link.get("href",""), base_url)
                if href and href not in seen and href != base_url:
                    seen.add(href)
                    found.append({"text": text[:100], "href": href})
        if len(found) > best_count:
            best_count, best_tag, best_class, best_samples = len(found), tag, css_class, found[:3]
    if best_count < 3:
        return None
    return {"scrape_mode": "list", "article_tag": best_tag,
            "article_class": best_class, "count": best_count, "samples": best_samples}


def _strategy_document_links(soup, base_url):
    found, seen = [], set()
    for link in soup.find_all("a", href=True):
        href     = link.get("href", "")
        text     = link.get_text(strip=True)
        href_low = href.lower()
        text_low = text.lower()
        if len(text) < DOCUMENT_TEXT_MIN:
            continue
        is_doc_url  = any(kw in href_low for kw in DOCUMENT_URL_KEYWORDS)
        is_doc_text = any(kw in text_low for kw in [
            "press release","statement","report","bulletin","communiqué",
            "notice","circular","gazette","announcement","publication",
            "budget","speech","address","release","update",
        ])
        if is_doc_url or is_doc_text:
            full_href = _resolve(href, base_url)
            if full_href and full_href not in seen and full_href != base_url:
                seen.add(full_href)
                found.append({"text": text[:100], "href": full_href})
    if len(found) < 2:
        return None
    return {"scrape_mode": "document", "article_tag": "a",
            "article_class": None, "count": len(found), "samples": found[:3]}


def _strategy_anchor_sweep(soup, base_url):
    # Work on a copy so we don't destroy the original soup for debug output
    import copy
    soup2 = copy.copy(soup)
    for el in soup2(["nav","footer","header","aside","script","style"]):
        el.decompose()
    for el in soup2.find_all(class_=lambda c: c and any(
            w in str(c).lower() for w in
            ["menu","nav","sidebar","footer","header","breadcrumb","social","cookie"])):
        el.decompose()

    found, seen = [], set()
    skip_words = {"#","javascript","mailto","tel:","login","register",
                  "subscribe","contact","about","privacy","terms","cookie"}
    for link in soup2.find_all("a", href=True):
        text = link.get_text(strip=True)
        href = link.get("href","")
        if len(text) < 25:
            continue
        if any(skip in href.lower() for skip in skip_words):
            continue
        full_href = _resolve(href, base_url)
        if full_href and full_href not in seen and full_href != base_url:
            seen.add(full_href)
            found.append({"text": text[:100], "href": full_href})
    if len(found) < 5:
        return None
    return {"scrape_mode": "anchor_sweep", "article_tag": "a",
            "article_class": None, "count": len(found), "samples": found[:3]}


def _strategy_js_render(url, base_url):
    """Strategy 6: Launch headless Chromium to render JavaScript content."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed — skipping JS test.")
        print("  To enable: pip install playwright && playwright install chromium")
        return None

    print(f"  🌐 Trying JS render...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()
            page.set_extra_http_headers({"User-Agent": HEADERS["User-Agent"]})
            page.goto(url, timeout=20000, wait_until="domcontentloaded")

            for selector in ["article","h2","h3",
                             "[class*='article']","[class*='post']",
                             "[class*='news']","[class*='card']"]:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    break
                except Exception:
                    continue

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        # Try all static strategies on the JS-rendered HTML
        for fn in [_strategy_headlines, _strategy_containers,
                   _strategy_list_items, _strategy_document_links,
                   _strategy_anchor_sweep]:
            result = fn(soup, base_url)
            if result:
                result["scrape_mode"] = "js"   # Mark as JS so config says "js"
                print(f"  ✅ JS render worked — {result['count']} items "
                      f"via [{result.get('_inner_mode', 'static')}]")
                return result

    except Exception as e:
        print(f"  ❌ JS render failed: {e}")

    return None


# ══════════════════════════════════════════════════════════════
#  DATABASE UPDATE — save confirmed scrape URL
# ══════════════════════════════════════════════════════════════

def _update_trusted_source(name: str, tested_url: str, base_url: str, category: str) -> dict:
    """
    After a successful test, persist the confirmed scrape URL to trusted_sources.

    Logic:
      - If an existing row shares the same domain (official_url netloc == tested netloc):
          UPDATE that row's scrape_url  (subpath of known source — no duplicate created)
      - Otherwise:
          INSERT a new row with official_url = base domain, scrape_url = tested URL
    """
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from database_utils import get_supabase_client
        supabase = get_supabase_client()
    except Exception as e:
        print(f"  ⚠️  DB update skipped (no Supabase client): {e}")
        return {"action": "skipped", "reason": str(e)}

    tested_domain = urlparse(tested_url).netloc  # e.g. "www.vra.com"

    try:
        rows = (supabase.table("trusted_sources")
                        .select("id,source_name,official_url,scrape_url")
                        .execute().data or [])

        existing = next(
            (r for r in rows if urlparse(r.get("official_url", "")).netloc == tested_domain),
            None
        )

        if existing:
            # Same domain — update scrape_url only, keep official_url intact
            supabase.table("trusted_sources").update({
                "scrape_url": tested_url,
            }).eq("id", existing["id"]).execute()
            print(f"  ✅ DB: updated '{existing['source_name']}' scrape_url → {tested_url}")
            return {"action": "updated", "id": existing["id"], "source_name": existing["source_name"]}
        else:
            # New domain — insert fresh entry
            ins = supabase.table("trusted_sources").insert({
                "source_name": name,
                "official_url": base_url,
                "scrape_url":   tested_url,
                "category":     category.replace("Government - ", "") if category else "Media",
            }).execute()
            if ins.data:
                print(f"  ✅ DB: inserted new source '{name}' scrape_url={tested_url}")
                return {"action": "inserted", "source_name": name}

    except Exception as e:
        print(f"  ⚠️  DB update failed: {e}")
        return {"action": "error", "reason": str(e)}

    return {"action": "none"}


# ══════════════════════════════════════════════════════════════
#  CORE TEST FUNCTION
# ══════════════════════════════════════════════════════════════
def test_site(site, update_db: bool = False):
    name     = site["name"]
    url      = site["url"]
    category = site.get("category", "Uncategorized")

    print(f"\n{'='*60}")
    print(f"TESTING:  {name}")
    print(f"CATEGORY: {category}")
    print(f"URL:      {url}")
    print(f"{'='*60}")

    # ── Fetch
    response = _fetch(url)
    if isinstance(response, dict) and "_error" in response:
        err = response["_error"]
        status_map = {
            "ssl_error":   "❌ SSL ERROR",
            "unreachable": "❌ CONNECTION FAILED",
            "timeout":     "❌ TIMEOUT (>15s)",
        }
        print(f"RESULT:   {status_map.get(err, f'❌ ERROR: {err}')}")
        return {"name": name, "url": url, "category": category, "status": err, "samples": []}

    code = response.status_code
    size = len(response.text)
    print(f"Status:   {code}  |  Size: {size:,} chars")

    # Check if we still got a challenge page after retry
    if is_challenge_page(response):
        print("RESULT:   🛡️  BOT CHALLENGE — site uses Akamai/Cloudflare protection")
        print("          Both browser and bot identities were challenged.")
        print("ACTION:   Try using the site's RSS feed or sitemap instead.")
        return {"name": name, "url": url, "category": category,
                "status": "challenge_blocked", "samples": [],
                "challenge_detected": True}

    if code == 403:
        print("RESULT:   ❌ BLOCKED (403) — rejecting scrapers")
        print("ACTION:   Look for an RSS feed or press release PDF instead.")
        return {"name": name, "url": url, "category": category, "status": "blocked", "samples": []}

    if code == 404:
        print("RESULT:   ❌ PAGE NOT FOUND (404)")
        return {"name": name, "url": url, "category": category, "status": "not_found", "samples": []}

    if code not in [200, 301, 302]:
        print(f"RESULT:   ❌ UNEXPECTED STATUS {code}")
        return {"name": name, "url": url, "category": category, "status": "error", "samples": []}

    parsed   = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    soup     = BeautifulSoup(response.text, "html.parser")

    # ── Try all static strategies, pick the best
    candidates = []
    for fn in [_strategy_headlines, _strategy_containers,
               _strategy_list_items, _strategy_document_links,
               _strategy_anchor_sweep]:
        r = fn(soup, base_url)
        if r:
            candidates.append(r)

    if candidates:
        best = max(candidates, key=lambda x: x["count"])
    else:
        # Static strategies all failed — try JS render
        print("  All static strategies found nothing. Trying JS render...")
        best = _strategy_js_render(url, base_url)

    if not best:
        print("RESULT:   ⚠️  REACHABLE but NO CONTENT FOUND via any strategy")
        print("          Site may require login, or uses a framework not yet supported.")
        _print_tag_debug(soup)
        return {"name": name, "url": url, "category": category,
                "status": "no_headlines", "samples": []}

    mode = best.get("scrape_mode", "headline")
    print(f"\nRESULT:   ✅ SCRAPEABLE  ({best['count']} items via {mode.upper()})")
    if best.get("article_tag"):
        print(f"PATTERN:  tag='{best['article_tag']}' | class='{best['article_class']}'")

    print("\nSample content:")
    for i, s in enumerate(best["samples"], 1):
        print(f"  {i}. {s['text'][:80]}")
        print(f"     → {s['href']}")

    _print_config_block(name, url, base_url, best)

    db_result = {}
    if update_db:
        print(f"\n  Saving confirmed scrape URL to trusted_sources...")
        db_result = _update_trusted_source(name, url, base_url, category)

    return {
        "name":          name,
        "url":           url,
        "category":      category,
        "status":        "scrapeable",
        "scrape_mode":   mode,
        "article_tag":   best.get("article_tag"),
        "article_class": best.get("article_class"),
        "base_url":      base_url,
        "count":         best["count"],
        "samples":       best["samples"],
        "db_update":     db_result,
    }


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    filter_arg = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    sites_to_run = [
        s for s in SITES_TO_TEST
        if filter_arg == "all" or filter_arg in s.get("category","").lower()
    ]

    print("=" * 60)
    print("  VeriGhana Site Tester — Full Strategy Edition")
    print(f"  Testing {len(sites_to_run)} sites  (filter: '{filter_arg}')")
    print("  Strategies: headline | container | list | document | anchor_sweep | js_render")
    print("=" * 60)

    results, current_cat = [], None

    for site in sites_to_run:
        cat = site.get("category","Other")
        if cat != current_cat:
            print(f"\n\n{'#'*60}\n  {cat.upper()}\n{'#'*60}")
            current_cat = cat
        result = test_site(site)
        results.append(result)
        time.sleep(1)

    # ── Summary
    scrapeable   = [r for r in results if r.get("status") == "scrapeable"]
    no_headlines = [r for r in results if r.get("status") == "no_headlines"]
    blocked      = [r for r in results if r.get("status") == "blocked"]
    unreachable  = [r for r in results if r.get("status") not in
                    ["scrapeable","no_headlines","blocked"]]

    by_mode = {}
    for r in scrapeable:
        m = r.get("scrape_mode","unknown")
        by_mode.setdefault(m, []).append(r)

    print(f"\n\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Scrapeable:          {len(scrapeable)} sites")
    print(f"⚠️  Reachable/no data:   {len(no_headlines)} sites")
    print(f"❌ Blocked (403):        {len(blocked)} sites")
    print(f"❌ Unreachable/error:    {len(unreachable)} sites")

    if by_mode:
        print(f"\n── BY STRATEGY ──")
        for mode, items in sorted(by_mode.items()):
            print(f"  {mode.upper()}: {len(items)} sites")
            for r in items:
                print(f"    ✅ {r['name']} ({r.get('count',0)} items)")

    if no_headlines:
        print(f"\n── NEEDS MANUAL INSPECTION ──")
        for r in no_headlines:
            print(f"  ⚠️  {r['name']}")

    if blocked:
        print(f"\n── BLOCKED — look for RSS feed ──")
        for r in blocked:
            print(f"  ❌ {r['name']}")

    if unreachable:
        print(f"\n── UNREACHABLE ──")
        for r in unreachable:
            print(f"  ❌ {r['name']}")

    if scrapeable:
        print(f"\n── SQL: ADD ALL SCRAPEABLE SITES TO trusted_sources ──")
        print("INSERT INTO trusted_sources (source_name, official_url, category)")
        print("VALUES")
        vals = []
        for r in scrapeable:
            cat_clean = r["category"].replace("Government - ","").replace("'","")
            vals.append(f"  ('{r['name']}', '{r['base_url']}', '{cat_clean}')")
        print(",\n".join(vals))
        print("ON CONFLICT (official_url) DO NOTHING;")


if __name__ == "__main__":
    main()