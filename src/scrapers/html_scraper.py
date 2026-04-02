"""
VeriGhana HTML Scraper — Full Strategy Edition
================================================
Scrapes Ghanaian news and government sites that have no RSS feed.

Six scraping strategies, tried in order until one works:
  1. headline     — h2/h3/h4 with known CSS class names
  2. container    — repeating div/article wrappers containing a link
  3. list         — li/tr/td list items with links inside
  4. document     — gov portals listing PDFs / press releases
  5. anchor_sweep — filtered sweep of all <a> tags (nav/footer stripped)
  6. js_render    — headless Chromium via Playwright (last resort)

FIXED ISSUES FROM PREVIOUS VERSION:
  - article_class="None" (string) now treated as None — was breaking all class lookups
  - Duplicate source names (multiple "Ministry of Finance" for different ministries)
  - Facebook/Twitter URLs removed — they block scraping entirely
  - STRATEGY_MAP now defined BEFORE extract_js_rendered references it
  - if __name__ block was accidentally indented inside extract_js_rendered — fixed
  - run_html_ingestion now uses all 6 strategies instead of just headline
  - scrape_article_content now tries 20+ content containers
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import sys, os, time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database_utils import get_source_id, get_supabase_client
from dotenv import load_dotenv
load_dotenv()

from scrapers.bot_identity import BROWSER_HEADERS, BOT_HEADERS, is_challenge_page

HEADERS = BROWSER_HEADERS

MIN_LENGTH = {
    "headline":     20,
    "container":    20,
    "list":         15,
    "document":     12,
    "anchor_sweep": 25,
}

DOCUMENT_URL_KEYWORDS = [
    "press", "release", "publication", "report", "news", "statement",
    "bulletin", "communique", "notice", "circular", "announcement",
    "update", "brief", "gazette", "decision", "policy", "budget",
    "speech", "address", ".pdf", "download",
]

HTML_SOURCES = [

    # ── MEDIA ──────────────────────────────────────────────────
    {
        "name":          "Graphic Online",
        "url":           "https://www.graphic.com.gh/news/general-news.html",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": "article-title",
        "base_url":      "https://www.graphic.com.gh"
    },
    {
        "name":          "Daily Graphic",
        "url":           "https://www.graphic.com.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h4",
        "article_class": None,
        "base_url":      "https://www.graphic.com.gh"
    },
    {
        "name":          "GhanaWeb",
        "url":           "https://www.ghanaweb.com/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://www.ghanaweb.com"
    },
    {
        "name":          "Yen Ghana",
        "url":           "https://yen.com.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://yen.com.gh"
    },
    {
        "name":          "Ghana News Agency",
        "url":           "https://www.ghananewsagency.org/",
        "scrape_mode":   "headline",
        "article_tag":   "h2",
        "article_class": "entry-title",
        "base_url":      "https://www.ghananewsagency.org"
    },
    {
        "name":          "3News",
        "url":           "https://3news.com/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": "jeg_post_title",
        "base_url":      "https://3news.com"
    },
    {
        "name":          "Citi Newsroom",
        "url":           "https://citinewsroom.com/category/news/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://citinewsroom.com"
    },
    {
        "name":          "Citinewsroom",
        "url":           "https://citinewsroom.com/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://citinewsroom.com"
    },

    # ── GOVERNMENT — MINISTRIES ────────────────────────────────
    {
        "name":          "Ministry of Finance",
        "url":           "https://mofep.gov.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h2",
        "article_class": None,
        "base_url":      "https://mofep.gov.gh"
    },
    {
        "name":          "Ministry of Foreign Affairs",
        "url":           "https://mfa.gov.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h4",
        "article_class": None,
        "base_url":      "https://mfa.gov.gh"
    },
    {
        "name":          "Ministry of Health",
        "url":           "https://www.moh.gov.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h2",
        "article_class": None,
        "base_url":      "https://www.moh.gov.gh"
    },
    {
        "name":          "Ministry of Communication",
        "url":           "https://www.moc.gov.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h2",
        "article_class": "entry-title",
        "base_url":      "https://www.moc.gov.gh"
    },
    {
        "name":          "Ministry of the Interior",
        "url":           "https://www.mint.gov.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://www.mint.gov.gh"
    },
    {
        "name":          "Ministry of Tourism",
        "url":           "https://www.touringghana.com/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://www.touringghana.com"
    },
    {
        "name":          "Ministry of Local Government",
        "url":           "http://www.mlgrd.gov.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "http://www.mlgrd.gov.gh"
    },
    {
        "name":          "Ministry of Defence",
        "url":           "https://mod.gov.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://mod.gov.gh"
    },

    # ── GOVERNMENT — REGULATORY ────────────────────────────────
    {
        "name":          "Judicial Service",
        "url":           "https://judicial.gov.gh/index.php/publications/news-publications/js-latest-news",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": "jeg_post_title",
        "base_url":      "https://judicial.gov.gh"
    },
    {
        "name":          "Communication Authority",
        "url":           "https://nca.org.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://nca.org.gh"
    },
    {
        "name":          "National Communications Auth",
        "url":           "https://www.nca.org.gh/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://www.nca.org.gh"
    },
    {
        "name":          "National Identification Authority",
        "url":           "https://nia.gov.gh",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://nia.gov.gh"
    },
    {
        "name":          "Securities and Exchange Comm",
        "url":           "https://sec.gov.gh",
        "scrape_mode":   "headline",
        "article_tag":   "h2",
        "article_class": None,
        "base_url":      "https://sec.gov.gh"
    },

    # ── GOVERNMENT — ENERGY ────────────────────────────────────
    {
        "name":          "Volta River Authority (VRA)",
        "url":           "https://www.vra.com/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://www.vra.com"
    },
    {
        "name":          "Volta River Authority News",
        "url":           "https://www.vra.com/media/2022_news.php",
        "scrape_mode":   "list",
        "article_tag":   "li",
        "article_class": None,
        "base_url":      "https://www.vra.com"
    },
    {
        "name":          "Energy Commission",
        "url":           "https://www.energycom.gov.gh/index.php/media-center/latest-news",
        "scrape_mode":   "headline",
        "article_tag":   "h4",
        "article_class": None,
        "base_url":      "https://www.energycom.gov.gh"
    },

    # ── GOVERNMENT — INVESTMENT & TOURISM ─────────────────────
    {
        "name":          "Ghana Investment Promotion Centre (GIPC)",
        "url":           "https://gipc.gov.gh/news-articles/",
        "scrape_mode":   "headline",
        "article_tag":   "h3",
        "article_class": None,
        "base_url":      "https://gipc.gov.gh"
    },
    {
        "name":          "Ghana Tourism Authority",
        "url":           "https://ghana.travel/blog/",
        "scrape_mode":   "headline",
        "article_tag":   "h2",
        "article_class": None,
        "base_url":      "https://ghana.travel"
    },

    # ── EDUCATION ──────────────────────────────────────────────
    {
        "name":          "GIMPA",
        "url":           "https://www.gimpa.edu.gh",
        "scrape_mode":   "headline",
        "article_tag":   "h2",
        "article_class": None,
        "base_url":      "https://www.gimpa.edu.gh"
    },

    # NOTE: Facebook and Twitter/X URLs removed.
    # These sites actively block all scraping.
    # Use their official APIs if social media content is needed.
]


# ══════════════════════════════════════════════════════════════
#  FETCH
# ══════════════════════════════════════════════════════════════
def fetch_page(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=True)
    except requests.exceptions.SSLError:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        except Exception as e:
            print(f"  SSL error: {e}")
            return None
    except Exception as e:
        print(f"  Could not fetch {url}: {e}")
        return None

    # If we got a challenge page, retry with honest bot identity
    if is_challenge_page(resp):
        print(f"  Challenge detected — retrying with VeriGhana-Bot identity...")
        try:
            resp = requests.get(url, headers=BOT_HEADERS, timeout=15, verify=True)
        except requests.exceptions.SSLError:
            try:
                resp = requests.get(url, headers=BOT_HEADERS, timeout=15, verify=False)
            except Exception:
                pass
        except Exception:
            pass

    return resp


# ══════════════════════════════════════════════════════════════
#  ARTICLE BODY EXTRACTOR
# ══════════════════════════════════════════════════════════════
def scrape_article_content(article_url: str) -> str:
    response = fetch_page(article_url)
    if not response or response.status_code != 200:
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "form", "figure", "iframe", "noscript"]):
        tag.decompose()

    content_selectors = [
        ("article",  None),
        ("div",      "article-content"),
        ("div",      "article-body"),
        ("div",      "article__body"),
        ("div",      "post-content"),
        ("div",      "post-body"),
        ("div",      "entry-content"),
        ("div",      "entry-body"),
        ("div",      "content-body"),
        ("div",      "story-body"),
        ("div",      "story-content"),
        ("div",      "news-content"),
        ("div",      "main-content"),
        ("div",      "page-content"),
        ("div",      "body-content"),
        ("div",      "text-content"),
        ("div",      "field-body"),
        ("div",      "field-items"),
        ("div",      "node-body"),
        ("div",      "press-content"),
        ("div",      "publication-body"),
        ("div",      "content"),
        ("main",     None),
        ("section",  "content"),
    ]

    for tag, css_class in content_selectors:
        el = soup.find(tag, class_=css_class) if css_class else soup.find(tag)
        if el:
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 100:
                return text[:3000]

    paragraphs = soup.find_all("p")
    all_text = " ".join(
        p.get_text(strip=True) for p in paragraphs
        if len(p.get_text(strip=True)) > 40
    )
    return all_text[:3000] if len(all_text) > 100 else ""


# ══════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════
def _resolve(href: str, base_url: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        scheme = base_url.split("://")[0]
        return scheme + ":" + href
    if href.startswith("/"):
        return base_url + href
    return base_url + "/" + href


# ══════════════════════════════════════════════════════════════
#  STRATEGY 1 — HEADLINE TAGS
# ══════════════════════════════════════════════════════════════
def extract_headline(soup, source: dict) -> list:
    tag       = source.get("article_tag", "h3")
    css_class = source.get("article_class")
    if css_class == "None":   # Fix common config mistake
        css_class = None
    base_url  = source["base_url"]

    elements = soup.find_all(tag, class_=css_class) if css_class else soup.find_all(tag)
    results, seen = [], set()
    for el in elements:
        link = el.find("a")
        text = el.get_text(strip=True)
        if not link or len(text) < MIN_LENGTH["headline"]:
            continue
        href = _resolve(link.get("href", ""), base_url)
        if href and href not in seen:
            seen.add(href)
            results.append({"title": text[:200], "url": href})
    return results


# ══════════════════════════════════════════════════════════════
#  STRATEGY 2 — ARTICLE CONTAINERS
# ══════════════════════════════════════════════════════════════
def extract_container(soup, source: dict) -> list:
    CONTAINER_PATTERNS = [
        ("article", None), ("article", "post"), ("article", "article"),
        ("div", "article-card"), ("div", "card"), ("div", "news-card"),
        ("div", "post-card"), ("div", "article-item"), ("div", "news-item"),
        ("div", "post-item"), ("div", "item"), ("div", "entry"),
        ("div", "post"), ("div", "article"), ("div", "story"),
        ("div", "story-card"), ("div", "feature"), ("div", "teaser"),
        ("div", "article-wrapper"), ("div", "post-wrapper"),
        ("div", "news-wrapper"), ("div", "content-item"),
        ("div", "list-item"), ("div", "grid-item"), ("div", "media-body"),
        ("div", "views-row"), ("div", "node"), ("div", "press-release"),
        ("div", "publication-item"), ("div", "news-entry"),
        ("div", "announcement"), ("div", "bulletin"),
        ("section", None), ("li", "article"), ("li", "post"),
    ]
    base_url = source["base_url"]
    best_count, best_results = 0, []

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
            text = link.get_text(strip=True) or el.get_text(strip=True)[:200]
            href = _resolve(link.get("href", ""), base_url)
            if len(text) >= MIN_LENGTH["container"] and href and href not in seen and href != base_url:
                seen.add(href)
                found.append({"title": text[:200], "url": href})
        if len(found) > best_count:
            best_count, best_results = len(found), found

    return best_results if best_count >= 2 else []


# ══════════════════════════════════════════════════════════════
#  STRATEGY 3 — LIST ITEMS
# ══════════════════════════════════════════════════════════════
def extract_list(soup, source: dict) -> list:
    tag       = source.get("article_tag", "li")
    css_class = source.get("article_class")
    if css_class == "None":
        css_class = None
    base_url  = source["base_url"]

    elements = soup.find_all(tag, class_=css_class) if css_class else soup.find_all(tag)
    results, seen = [], set()
    for el in elements:
        link = el.find("a")
        text = el.get_text(strip=True)
        if not link or len(text) < MIN_LENGTH["list"]:
            continue
        href = _resolve(link.get("href", ""), base_url)
        if href and href not in seen and href != base_url:
            seen.add(href)
            results.append({"title": text[:200], "url": href})
    return results


# ══════════════════════════════════════════════════════════════
#  STRATEGY 4 — DOCUMENT LINKS
# ══════════════════════════════════════════════════════════════
def extract_document(soup, source: dict) -> list:
    base_url = source["base_url"]
    results, seen = [], set()
    for link in soup.find_all("a", href=True):
        href     = link.get("href", "")
        text     = link.get_text(strip=True)
        href_low = href.lower()
        text_low = text.lower()
        if len(text) < MIN_LENGTH["document"]:
            continue
        is_doc_url  = any(kw in href_low for kw in DOCUMENT_URL_KEYWORDS)
        is_doc_text = any(kw in text_low for kw in [
            "press release", "statement", "report", "bulletin",
            "notice", "circular", "gazette", "announcement",
            "publication", "budget", "speech", "release", "update",
        ])
        if is_doc_url or is_doc_text:
            full_href = _resolve(href, base_url)
            if full_href and full_href not in seen and full_href != base_url:
                seen.add(full_href)
                results.append({"title": text[:200], "url": full_href})
    return results


# ══════════════════════════════════════════════════════════════
#  STRATEGY 5 — ANCHOR SWEEP
# ══════════════════════════════════════════════════════════════
def extract_anchor_sweep(soup, source: dict) -> list:
    base_url = source["base_url"]
    for el in soup(["nav", "footer", "header", "aside", "script", "style"]):
        el.decompose()
    for el in soup.find_all(class_=lambda c: c and any(
            w in str(c).lower() for w in
            ["menu", "nav", "sidebar", "footer", "header", "breadcrumb", "social", "cookie"])):
        el.decompose()

    results, seen = [], set()
    skip_words = {"#", "javascript", "mailto", "tel:", "login", "register",
                  "subscribe", "contact", "about", "privacy", "terms", "cookie"}
    for link in soup.find_all("a", href=True):
        text = link.get_text(strip=True)
        href = link.get("href", "")
        if len(text) < MIN_LENGTH["anchor_sweep"]:
            continue
        if any(skip in href.lower() for skip in skip_words):
            continue
        full_href = _resolve(href, base_url)
        if full_href and full_href not in seen and full_href != base_url:
            seen.add(full_href)
            results.append({"title": text[:200], "url": full_href})
    return results if len(results) >= 5 else []


# ══════════════════════════════════════════════════════════════
#  STRATEGY MAP  (must be defined before extract_js_rendered)
# ══════════════════════════════════════════════════════════════
STRATEGY_MAP = {
    "headline":     extract_headline,
    "container":    extract_container,
    "list":         extract_list,
    "document":     extract_document,
    "anchor_sweep": extract_anchor_sweep,
}


# ══════════════════════════════════════════════════════════════
#  STRATEGY 6 — JAVASCRIPT RENDERING (Playwright)
# ══════════════════════════════════════════════════════════════
def extract_js_rendered(source: dict) -> list:
    """
    Last resort for JavaScript-heavy sites.
    Setup: pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed.")
        print("  Run: pip install playwright && playwright install chromium")
        return []

    url      = source["url"]
    base_url = source["base_url"]
    print(f"  Trying JS render for {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            })
            page.goto(url, timeout=20000, wait_until="domcontentloaded")

            for selector in ["article", "h2", "h3",
                              "[class*='article']", "[class*='post']",
                              "[class*='news']",    "[class*='card']"]:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    break
                except Exception:
                    continue

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        for mode_name, fn in STRATEGY_MAP.items():
            temp_source = dict(source)
            temp_source["scrape_mode"] = mode_name
            found = fn(soup, temp_source)
            if found:
                print(f"  JS render succeeded — {len(found)} items via [{mode_name}]")
                return found

    except Exception as e:
        print(f"  JS render failed: {e}")

    return []


# ══════════════════════════════════════════════════════════════
#  STRATEGY DISPATCHER  (this is where the fallback_order lives)
# ══════════════════════════════════════════════════════════════
def extract_articles(soup, source: dict) -> list:
    """
    1. Try the source's configured scrape_mode first.
    2. If that returns nothing, fall back through all other static strategies.
    3. If all static strategies fail, fire the JS renderer.
    """
    primary_mode = source.get("scrape_mode", "headline")

    # Try primary
    fn = STRATEGY_MAP.get(primary_mode)
    if fn:
        results = fn(soup, source)
        if results:
            return results

    # Fallback order through remaining static strategies
    fallback_order = ["headline", "container", "list", "document", "anchor_sweep"]
    for mode in fallback_order:
        if mode == primary_mode:
            continue
        results = STRATEGY_MAP[mode](soup, source)
        if results:
            print(f"  '{primary_mode}' found nothing. "
                  f"Fell back to '{mode}' — found {len(results)} items.")
            return results

    # Last resort: JS rendering
    print(f"  All static strategies failed. Attempting JS render...")
    return extract_js_rendered(source)


# ══════════════════════════════════════════════════════════════
#  MAIN INGESTION PIPELINE
# ══════════════════════════════════════════════════════════════
def _load_db_sources() -> list:
    """
    Load any trusted_sources rows that have a scrape_url set.
    These are sites confirmed scrapeable via the admin site tester.
    Returned entries use scrape_url as the URL and auto-detect scrape mode at runtime.
    """
    try:
        supabase = get_supabase_client()
        rows = (supabase.table("trusted_sources")
                        .select("source_name,official_url,scrape_url,category")
                        .not_.is_("scrape_url", "null")
                        .execute().data or [])
        db_sources = []
        for row in rows:
            url = row.get("scrape_url") or row.get("official_url", "")
            if not url:
                continue
            parsed   = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            db_sources.append({
                "name":          row["source_name"],
                "url":           url,
                "scrape_mode":   "auto",
                "article_tag":   None,
                "article_class": None,
                "base_url":      base_url,
            })
        return db_sources
    except Exception as e:
        print(f"[html_scraper] Could not load DB sources: {e}")
        return []


def run_html_ingestion(sources=None, max_per_source=15):
    supabase        = get_supabase_client()
    total_processed = 0

    if sources is not None:
        sources_to_run = sources
    else:
        # Merge hardcoded list with DB-confirmed sources (scrape_url overrides same-name entries)
        hardcoded_urls = {s["url"] for s in HTML_SOURCES}
        hardcoded_names = {s["name"] for s in HTML_SOURCES}
        db_extras = [
            s for s in _load_db_sources()
            if s["url"] not in hardcoded_urls and s["name"] not in hardcoded_names
        ]
        if db_extras:
            print(f"[html_scraper] Loaded {len(db_extras)} additional source(s) from trusted_sources DB")
        sources_to_run = HTML_SOURCES + db_extras

    # ── GhanaWeb special case: use sitemap scraper (Akamai-protected) ────
    ghanaweb_names = {"ghanaweb"}
    remaining_sources = []
    for source in sources_to_run:
        if source["name"].lower().replace(" ", "") in ghanaweb_names:
            print(f"\n── Scraping: {source['name']}  [sitemap via Playwright]")
            base_url = source.get("base_url", "https://www.ghanaweb.com")
            category = source.get("category", "Media")
            source_id = get_source_id(supabase, source["name"], official_url=base_url, category=category)
            if not source_id:
                print(f"   Could not register '{source['name']}' in trusted_sources. Skipping.")
                continue
            try:
                from scrapers.ghanaweb_sitemap import fetch_ghanaweb_articles
                gw_articles = fetch_ghanaweb_articles()
                print(f"   Found {len(gw_articles)} items from sitemap — processing up to {max_per_source}")
                for item in gw_articles[:max_per_source]:
                    content = scrape_article_content(item["url_link"])
                    if not content or len(content) < 80:
                        content = item["title"]
                    try:
                        supabase.table('fact_entries').upsert({
                            'title':          item["title"],
                            'url_link':       item["url_link"],
                            'content_text':   content[:5000],
                            'source_id':      source_id,
                            'published_date': item.get("published_date") or None,
                        }, on_conflict='url_link').execute()
                        total_processed += 1
                    except Exception as e:
                        print(f"   DB error: {e}")
            except ImportError:
                print(f"   ghanaweb_sitemap module not available. Skipping.")
            except Exception as e:
                print(f"   GhanaWeb sitemap error: {e}")
        else:
            remaining_sources.append(source)

    for source in remaining_sources:
        name = source["name"]
        url  = source["url"]
        mode = source.get("scrape_mode", "headline")

        print(f"\n── Scraping: {name}  [{mode}]")
        print(f"   URL: {url}")

        parsed   = urlparse(url)
        base_url = source.get("base_url", f"{parsed.scheme}://{parsed.netloc}")
        category = source.get("category", "Media")
        source_id = get_source_id(supabase, name, official_url=base_url, category=category)
        if not source_id:
            print(f"   Could not register '{name}' in trusted_sources. Skipping.")
            continue

        response = fetch_page(url)
        if not response or response.status_code not in [200, 301, 302]:
            status = response.status_code if response else "no response"
            print(f"   Could not fetch listing page (status: {status})")
            continue

        soup     = BeautifulSoup(response.text, "html.parser")
        articles = extract_articles(soup, source)

        if not articles:
            print(f"   No articles found. Site structure may have changed.")
            continue

        print(f"   Found {len(articles)} items — processing up to {max_per_source}")

        for item in articles[:max_per_source]:
            title       = item["title"]
            article_url = item["url"]

            if not article_url or article_url == url:
                continue

            if article_url.lower().endswith(".pdf"):
                content = f"[PDF document] {title}"
            else:
                content = scrape_article_content(article_url)
                if not content:
                    content = title

            try:
                supabase.table("fact_entries").upsert({
                    "title":          title,
                    "url_link":       article_url,
                    "content_text":   content,
                    "source_id":      source_id,
                    "published_date": None,
                }, on_conflict="url_link").execute()

                print(f"   Saved: {title[:70]}...")
                total_processed += 1

            except Exception as e:
                print(f"   Error saving '{title[:50]}': {e}")

            time.sleep(0.5)

    print(f"\n── HTML ingestion complete. Total processed: {total_processed}")
    return total_processed


if __name__ == "__main__":
    run_html_ingestion()