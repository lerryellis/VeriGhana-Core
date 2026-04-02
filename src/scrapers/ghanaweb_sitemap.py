"""
GhanaWeb Sitemap Scraper
========================
GhanaWeb uses Akamai Bot Manager on their entire domain, including sitemaps.
This module uses Playwright to solve the challenge once, captures the session
cookie, then fetches the news sitemap XML with plain requests.

Usage:
    from scrapers.ghanaweb_sitemap import fetch_ghanaweb_articles
    articles = fetch_ghanaweb_articles()
    # Returns: [{"title": "...", "url": "...", "published_date": "..."}, ...]
"""

import re
import time
import requests
from typing import Optional

SITEMAP_URL = "https://www.ghanaweb.com/sitemaps/news.xml"
CHALLENGE_WAIT = 20  # seconds to wait for Akamai challenge to auto-solve


def _solve_challenge_and_get_cookies() -> Optional[dict]:
    """
    Use Playwright to navigate to GhanaWeb, wait for the Akamai
    challenge to solve, then return the session cookies.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ghanaweb] Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    print(f"[ghanaweb] Solving Akamai challenge via Playwright...")
    cookies = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Navigate to the sitemap — triggers the challenge
            page.goto(SITEMAP_URL, timeout=30000, wait_until="domcontentloaded")

            # Wait for challenge to solve (the page reloads after solving)
            print(f"[ghanaweb] Waiting up to {CHALLENGE_WAIT}s for challenge to resolve...")
            start = time.time()
            solved = False

            while time.time() - start < CHALLENGE_WAIT:
                content = page.content()
                # If we see XML content or the page is large, challenge is solved
                if '<urlset' in content or '<sitemapindex' in content or len(content) > 5000:
                    solved = True
                    break
                time.sleep(2)

            if solved:
                # Extract cookies for reuse with requests
                browser_cookies = context.cookies()
                cookies = {c["name"]: c["value"] for c in browser_cookies if "ghanaweb" in c.get("domain", "")}
                print(f"[ghanaweb] Challenge solved — captured {len(cookies)} cookies")
            else:
                # Try extracting whatever content we have
                final_content = page.content()
                if len(final_content) > 5000:
                    cookies = {c["name"]: c["value"] for c in context.cookies() if "ghanaweb" in c.get("domain", "")}
                    print(f"[ghanaweb] Got content after wait — {len(final_content):,} chars")
                else:
                    print(f"[ghanaweb] Challenge not solved within {CHALLENGE_WAIT}s")

            browser.close()

    except Exception as e:
        print(f"[ghanaweb] Playwright error: {e}")

    return cookies


def _fetch_sitemap_with_cookies(cookies: dict) -> Optional[str]:
    """Fetch the news sitemap XML using cookies from the solved challenge."""
    try:
        resp = requests.get(
            SITEMAP_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/xml,text/xml,*/*",
            },
            cookies=cookies,
            timeout=15,
        )
        if resp.status_code == 200 and '<urlset' in resp.text:
            print(f"[ghanaweb] Sitemap fetched — {len(resp.text):,} chars")
            return resp.text
        elif resp.status_code == 200 and len(resp.text) < 3000:
            print(f"[ghanaweb] Got challenge page again — cookies may have expired")
            return None
        else:
            print(f"[ghanaweb] Unexpected response: {resp.status_code}, {len(resp.text)} chars")
            return None
    except Exception as e:
        print(f"[ghanaweb] Fetch error: {e}")
        return None


def _fetch_sitemap_via_playwright() -> Optional[str]:
    """Fallback: read sitemap XML directly from Playwright page content."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    print(f"[ghanaweb] Fetching sitemap directly via Playwright...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"
            )
            page.goto(SITEMAP_URL, timeout=30000, wait_until="networkidle")

            # Wait for content
            start = time.time()
            while time.time() - start < CHALLENGE_WAIT:
                content = page.content()
                if '<loc>' in content or '<urlset' in content:
                    # Extract the raw XML from the pre tag (browsers wrap XML in HTML)
                    text = page.evaluate("() => document.body?.innerText || document.documentElement?.textContent || ''")
                    browser.close()
                    if '<urlset' in text:
                        print(f"[ghanaweb] Got sitemap via Playwright — {len(text):,} chars")
                        return text
                    return None
                time.sleep(2)

            browser.close()
    except Exception as e:
        print(f"[ghanaweb] Direct Playwright fetch error: {e}")

    return None


def _parse_news_sitemap(xml_text: str) -> list[dict]:
    """Parse Google News Sitemap XML into article dicts."""
    articles = []

    # Extract <url> blocks
    url_blocks = re.findall(r'<url>(.*?)</url>', xml_text, re.DOTALL)

    for block in url_blocks:
        loc_match = re.search(r'<loc>(.*?)</loc>', block)
        title_match = re.search(r'<news:title>(.*?)</news:title>', block)
        date_match = re.search(r'<news:publication_date>(.*?)</news:publication_date>', block)

        if loc_match:
            url = loc_match.group(1).strip()
            title = title_match.group(1).strip() if title_match else ""
            pub_date = date_match.group(1).strip() if date_match else ""

            if title and len(title) > 10:
                articles.append({
                    "title": title,
                    "url_link": url,
                    "published_date": pub_date,
                    "source_name": "GhanaWeb",
                })

    return articles


def fetch_ghanaweb_articles() -> list[dict]:
    """
    Main entry point. Tries:
    1. Solve challenge → fetch sitemap with cookies
    2. Read sitemap directly from Playwright
    Returns list of article dicts ready for fact_entries insertion.
    """
    print(f"\n[ghanaweb] Starting GhanaWeb sitemap scrape...")

    # Strategy 1: solve challenge, reuse cookies
    cookies = _solve_challenge_and_get_cookies()
    if cookies:
        xml = _fetch_sitemap_with_cookies(cookies)
        if xml:
            articles = _parse_news_sitemap(xml)
            if articles:
                print(f"[ghanaweb] Parsed {len(articles)} articles from sitemap")
                return articles

    # Strategy 2: read XML directly from Playwright
    xml = _fetch_sitemap_via_playwright()
    if xml:
        articles = _parse_news_sitemap(xml)
        if articles:
            print(f"[ghanaweb] Parsed {len(articles)} articles via direct Playwright")
            return articles

    print(f"[ghanaweb] Could not retrieve any articles")
    return []


if __name__ == "__main__":
    articles = fetch_ghanaweb_articles()
    print(f"\n{'='*60}")
    print(f"Total articles: {len(articles)}")
    for i, a in enumerate(articles[:10], 1):
        print(f"  {i}. {a['title'][:70]}")
        print(f"     {a['url_link']}")
        print(f"     {a['published_date']}")
