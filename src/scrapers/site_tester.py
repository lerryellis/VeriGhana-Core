"""
VeriGhana Site Tester
Run this before adding any new source to html_scraper.py
It tests reachability, finds the correct headline tags automatically,
and tells you exactly what to put in your HTML_SOURCES config.
"""

import requests
from bs4 import BeautifulSoup
import sys
import os

# Suppress the SSL warning on older macOS
import urllib3
urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── Sites to test
# Add any site you are considering here before touching html_scraper.py
SITES_TO_TEST = [
    {
        "name": "Ministry of Finance",
        "url":  "https://www.mofep.gov.gh/news-and-events"
    },
    {
        "name": "Ministry of Finance (alternate)",
        "url":  "https://www.mofep.gov.gh/"
    },
    {
        "name": "Graphic Online",
        "url":  "https://www.graphic.com.gh/news/general-news.html"
    },
    {
        "name": "Graphic Online (alternate)",
        "url":  "https://www.graphic.com.gh"
    },
    {
        "name": "Ghana News Agency",
        "url":  "https://www.ghananewsagency.org/"
    },
    {
        "name": "Ghana News Agency (politics)",
        "url":  "https://www.ghananewsagency.org/politics"
    },
    {
        "name": "3News",
        "url":  "https://3news.com/"
    },
    {
        "name": "Peacefm Online",
        "url":  "https://www.peacefmonline.com/"
    },
    {
        "name": "GhanaWeb",
        "url":  "https://www.ghanaweb.com/"
    },
    {
        "name": "Myjoyonline (no RSS fallback)",
        "url":  "https://www.myjoyonline.com/news/"
    },
    {
        "name": "Citinewsroom (no RSS fallback)",
        "url":  "https://citinewsroom.com/category/news/"
    },
    {
        "name": "Ghana Statistical Service",
        "url":  "https://statsghana.gov.gh/"
    },
    {
        "name": "Bank of Ghana",
        "url":  "https://www.bog.gov.gh/news-publications/press-releases/"
    },
    {
        "name": "Parliament of Ghana",
        "url":  "https://www.parliament.gh/news"
    },
]

# ── All tag/class combinations to try when looking for headlines
# The tester tries every one and reports which finds the most headlines
HEADLINE_PATTERNS = [
    ("h1", None),
    ("h2", None),
    ("h3", None),
    ("h4", None),
    ("h2", "entry-title"),
    ("h3", "entry-title"),
    ("h2", "post-title"),
    ("h3", "post-title"),
    ("h3", "article-title"),
    ("h2", "article-title"),
    ("h2", "title"),
    ("h3", "title"),
    ("a",  "story-title"),
    ("h3", "td-module-title"),
    ("h3", "jeg_post_title"),
    ("h2", "jeg_post_title"),
    ("div", "article-headline"),
    ("span", "headline"),
    ("h3", "cb-post-title"),
    ("h2", "cb-post-title"),
    ("li", "news-item"),
    ("div", "news-title"),
    ("p",  "title"),
]


def test_site(name, url):
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print(f"URL:     {url}")
    print(f"{'='*60}")

    # ── Step 1: Can we reach it?
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status:  {response.status_code}")

        if response.status_code == 403:
            print("RESULT:  ❌ BLOCKED — Site is actively rejecting scrapers (403 Forbidden)")
            print("ACTION:  Skip this site. Look for their RSS feed instead.")
            return None

        if response.status_code == 404:
            print("RESULT:  ❌ PAGE NOT FOUND — The URL does not exist")
            print("ACTION:  Try a different URL for this site")
            return None

        if response.status_code != 200:
            print(f"RESULT:  ❌ UNEXPECTED STATUS {response.status_code}")
            return None

        print(f"Size:    {len(response.text):,} characters received")

    except requests.exceptions.SSLError:
        print("RESULT:  ❌ SSL ERROR — Site has an SSL certificate problem")
        print("ACTION:  Try adding verify=False to requests.get() or skip this site")
        return None
    except requests.exceptions.ConnectionError:
        print("RESULT:  ❌ CONNECTION FAILED — Site is unreachable or domain does not exist")
        return None
    except requests.exceptions.Timeout:
        print("RESULT:  ❌ TIMEOUT — Site took too long to respond (>15 seconds)")
        return None

    # ── Step 2: Parse the HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # ── Step 3: Try every headline pattern and find the best one
    best_tag      = None
    best_class    = None
    best_count    = 0
    best_samples  = []
    all_results   = []

    for tag, css_class in HEADLINE_PATTERNS:
        if css_class:
            elements = soup.find_all(tag, class_=css_class)
        else:
            elements = soup.find_all(tag)

        # Only count elements that actually contain a link (real headlines)
        headlines_with_links = []
        for el in elements:
            link = el.find("a")
            text = el.get_text(strip=True)
            if link and len(text) > 20:
                headlines_with_links.append({
                    "text": text[:80],
                    "href": link.get("href", "")
                })

        count = len(headlines_with_links)
        if count > 0:
            all_results.append((count, tag, css_class, headlines_with_links[:3]))
            if count > best_count:
                best_count   = count
                best_tag     = tag
                best_class   = css_class
                best_samples = headlines_with_links[:3]

    # ── Step 4: Report findings
    if best_count == 0:
        print("RESULT:  ⚠️  REACHABLE but NO HEADLINES FOUND")
        print("         The site loaded but no recognisable headline pattern was found.")
        print("         This usually means:")
        print("         1. The site loads content via JavaScript (cannot be scraped this way)")
        print("         2. The site uses unusual custom CSS class names")
        print("         3. Content is behind a login wall")
        print("\nACTION:  Open the site in Chrome, right-click a headline,")
        print("         click Inspect, and look for the tag and class manually.")
        print("         Then add a custom entry to HEADLINE_PATTERNS and re-run.")

        # Show what tags DO exist, to help with manual inspection
        print("\nTags found on this page (to help you inspect manually):")
        for tag in ["h1", "h2", "h3", "h4", "h5"]:
            found = soup.find_all(tag)
            if found:
                sample = found[0].get_text(strip=True)[:60]
                print(f"  <{tag}> — {len(found)} found — first: \"{sample}\"")
        return None

    # ── Show all working patterns ranked by headline count
    all_results.sort(reverse=True)
    print(f"\nRESULT:  ✅ SCRAPEABLE — Found headlines using {len(all_results)} different patterns")
    print(f"\nBEST PATTERN: tag='{best_tag}', class='{best_class}' — {best_count} headlines found")
    print("\nSample headlines found:")
    for i, sample in enumerate(best_samples, 1):
        href = sample['href']
        # Detect relative vs absolute URLs
        if href and not href.startswith("http"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base   = f"{parsed.scheme}://{parsed.netloc}"
            href   = base + href
        print(f"  {i}. {sample['text']}")
        print(f"     URL: {href}")

    # ── Print the exact config block to copy into html_scraper.py
    from urllib.parse import urlparse
    parsed  = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    print(f"\n✅ COPY THIS INTO html_scraper.py HTML_SOURCES list:")
    print(f"""
    {{
        "name":          "{name}",
        "url":           "{url}",
        "article_tag":   "{best_tag}",
        "article_class": "{best_class}",
        "base_url":      "{base_url}"
    }},""")

    return {
        "name":          name,
        "url":           url,
        "article_tag":   best_tag,
        "article_class": best_class,
        "base_url":      base_url,
        "count":         best_count
    }


def main():
    print("VeriGhana Site Tester")
    print("Testing all candidate sources...\n")

    working   = []
    blocked   = []
    no_result = []

    for site in SITES_TO_TEST:
        result = test_site(site["name"], site["url"])
        if result:
            working.append(result)
        else:
            status = "blocked/unreachable"
            no_result.append(site["name"])

    # ── Final summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Scrapeable:      {len(working)} sites")
    print(f"❌ Not scrapeable:  {len(no_result)} sites")

    if working:
        print("\nSITES READY TO ADD TO html_scraper.py:")
        for s in working:
            print(f"  • {s['name']} — {s['count']} headlines found")

    if no_result:
        print("\nSITES TO SKIP OR INVESTIGATE MANUALLY:")
        for name in no_result:
            print(f"  • {name}")

    print("\nFor any site marked scrapeable above,")
    print("copy the config block printed during its test into HTML_SOURCES in html_scraper.py")


if __name__ == "__main__":
    main()