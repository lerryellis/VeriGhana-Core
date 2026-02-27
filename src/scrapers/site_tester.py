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
import time

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

# ── All sites to test, grouped by category
SITES_TO_TEST = [

    # ── EXISTING MEDIA SOURCES ──────────────────────────────────────────
    {"name": "Citi Newsroom",           "url": "https://citinewsroom.com/category/news/",           "category": "Media"},
    {"name": "Joy Online",              "url": "https://www.myjoyonline.com/news/",                 "category": "Media"},
    {"name": "Graphic Online",          "url": "https://www.graphic.com.gh/news/general-news.html", "category": "Media"},
    {"name": "Ghana News Agency",       "url": "https://www.ghananewsagency.org/",                  "category": "Media"},
    {"name": "3News",                   "url": "https://3news.com/",                                "category": "Media"},
    {"name": "Peacefm Online",          "url": "https://www.peacefmonline.com/",                    "category": "Media"},
    {"name": "GhanaWeb",                "url": "https://www.ghanaweb.com/",                         "category": "Media"},
    {"name": "Pulse Ghana",             "url": "https://www.pulse.com.gh/",                         "category": "Media"},

    # ── EXECUTIVE BRANCH ────────────────────────────────────────────────
    {"name": "Office of the President",         "url": "https://presidency.gov.gh/",        "category": "Government - Executive"},
    {"name": "Ghana Government Portal",         "url": "https://www.ghana.gov.gh/",         "category": "Government - Executive"},

    # ── MINISTRIES ──────────────────────────────────────────────────────
    {"name": "Ministry of Foreign Affairs",     "url": "https://mfa.gov.gh/",               "category": "Government - Ministry"},
    {"name": "Ministry of Finance",             "url": "https://mofep.gov.gh/",             "category": "Government - Ministry"},
    {"name": "Ministry of Education",           "url": "https://moe.gov.gh/",               "category": "Government - Ministry"},
    {"name": "Ministry of Energy",              "url": "https://www.energymin.gov.gh/",     "category": "Government - Ministry"},
    {"name": "Ministry of Health",              "url": "https://www.moh.gov.gh/",           "category": "Government - Ministry"},
    {"name": "Ministry of Roads and Highways",  "url": "https://www.mrh.gov.gh/",           "category": "Government - Ministry"},
    {"name": "Ministry of Trade and Industry",  "url": "http://www.moti.gov.gh/",           "category": "Government - Ministry"},
    {"name": "Ministry of Communication",       "url": "https://moc.gov.gh/",               "category": "Government - Ministry"},
    {"name": "Ministry of the Interior",        "url": "https://www.mint.gov.gh/",          "category": "Government - Ministry"},
    {"name": "Ministry of Tourism",             "url": "https://www.touringghana.com/",     "category": "Government - Ministry"},
    {"name": "Ministry of Local Government",    "url": "http://www.mlgrd.gov.gh/",          "category": "Government - Ministry"},
    {"name": "Ministry of Justice",             "url": "https://mojag.gov.gh/",             "category": "Government - Ministry"},
    {"name": "Ministry of Defence",             "url": "https://mod.gov.gh/",               "category": "Government - Ministry"},

    # ── LEGISLATURE & JUDICIARY ─────────────────────────────────────────
    {"name": "Parliament of Ghana",             "url": "https://www.parliament.gh/news",    "category": "Government - Legislature"},
    {"name": "Judicial Service of Ghana",       "url": "https://www.judicial.gov.gh/",      "category": "Government - Judiciary"},

    # ── REGULATORY & STATUTORY BODIES ───────────────────────────────────
    {"name": "Bank of Ghana",                   "url": "https://www.bog.gov.gh/news-publications/press-releases/", "category": "Government - Regulatory"},
    {"name": "Electoral Commission",            "url": "https://www.ec.gov.gh/",            "category": "Government - Regulatory"},
    {"name": "National Development Planning",   "url": "https://www.ndpc.gov.gh/",          "category": "Government - Regulatory"},
    {"name": "Public Procurement Authority",    "url": "https://www.ppbghana.org/",         "category": "Government - Regulatory"},
    {"name": "National Communications Auth",    "url": "https://www.nca.org.gh/",           "category": "Government - Regulatory"},
    {"name": "Public Utilities Regulatory",     "url": "http://www.purc.com.gh/",           "category": "Government - Regulatory"},
    {"name": "Ghana Standards Authority",       "url": "https://www.gsa.gov.gh/",           "category": "Government - Regulatory"},
    {"name": "Food and Drugs Authority",        "url": "https://www.fdaghana.gov.gh/",      "category": "Government - Regulatory"},
    {"name": "National Commission on Culture",  "url": "http://www.ghanaculture.gov.gh/",   "category": "Government - Regulatory"},

    # ── REVENUE & TAX ───────────────────────────────────────────────────
    {"name": "Ghana Revenue Authority",         "url": "https://gra.gov.gh/",               "category": "Government - Revenue"},

    # ── SOCIAL SECURITY & INSURANCE ─────────────────────────────────────
    {"name": "SSNIT",                           "url": "https://www.ssnit.org.gh/",         "category": "Government - Social"},
    {"name": "National Health Insurance Auth",  "url": "https://www.nhis.gov.gh/",          "category": "Government - Social"},

    # ── IDENTIFICATION & LICENSING ───────────────────────────────────────
    {"name": "National Identification Auth",    "url": "https://nia.gov.gh/",               "category": "Government - Identification"},
    {"name": "DVLA",                            "url": "https://dvla.gov.gh/",              "category": "Government - Identification"},

    # ── EDUCATION & RESEARCH ─────────────────────────────────────────────
    {"name": "Ghana Education Service",         "url": "https://ges.gov.gh/",               "category": "Government - Education"},
    {"name": "National Teaching Council",       "url": "https://ntc.gov.gh/",               "category": "Government - Education"},
    {"name": "National Accreditation Board",    "url": "https://nab.gov.gh/",               "category": "Government - Education"},
    {"name": "GIMPA",                           "url": "https://www.gimpa.edu.gh/",         "category": "Government - Education"},
    {"name": "CSIR",                            "url": "http://www.csir.org.gh/",           "category": "Government - Education"},

    # ── STATISTICS & DATA ────────────────────────────────────────────────
    {"name": "Ghana Statistical Service",       "url": "https://www.statsghana.gov.gh/",    "category": "Government - Statistics"},

    # ── HEALTH SERVICES ──────────────────────────────────────────────────
    {"name": "Ghana Health Service",            "url": "https://ghs.gov.gh/",               "category": "Government - Health"},

    # ── ENERGY SECTOR ────────────────────────────────────────────────────
    {"name": "Volta River Authority",           "url": "https://www.vra.com/",              "category": "Government - Energy"},
    {"name": "GRIDCo",                          "url": "https://www.gridcogh.com/",         "category": "Government - Energy"},
    {"name": "Energy Commission",               "url": "https://www.energycom.gov.gh/",     "category": "Government - Energy"},

    # ── INVESTMENT & TRADE ────────────────────────────────────────────────
    {"name": "Ghana Investment Promotion",      "url": "https://www.gipcghana.com/",        "category": "Government - Investment"},
    {"name": "Ghana Export Promotion Auth",     "url": "https://www.gepaghana.org/",        "category": "Government - Investment"},
    {"name": "Ghana Free Zones Board",          "url": "https://gfzb.gov.gh/",              "category": "Government - Investment"},
    {"name": "Ghana Tourism Authority",         "url": "https://www.ghana.travel/",         "category": "Government - Investment"},

    # ── SECURITY SERVICES ────────────────────────────────────────────────
    {"name": "Ghana Armed Forces",              "url": "https://gafonline.mil.gh/",         "category": "Government - Security"},
    {"name": "Ghana Police Service",            "url": "https://www.police.gov.gh/",        "category": "Government - Security"},

    # ── INFORMATION TECHNOLOGY ───────────────────────────────────────────
    {"name": "NITA",                            "url": "https://nita.gov.gh/",              "category": "Government - Technology"},
    {"name": "Cyber Security Authority",        "url": "https://www.csa.gov.gh/",           "category": "Government - Technology"},
    {"name": "Data Protection Commission",      "url": "https://dataprotection.gov.gh/",    "category": "Government - Technology"},

    # ── FINANCE & BUSINESS ───────────────────────────────────────────────
    {"name": "Securities and Exchange Comm",    "url": "https://sec.gov.gh/",               "category": "Government - Finance"},
    {"name": "National Insurance Commission",   "url": "https://nicghana.org/",             "category": "Government - Finance"},
    {"name": "NPRA",                            "url": "https://www.npra.gov.gh/",          "category": "Government - Finance"},
    {"name": "CAGD",                            "url": "https://cagd.gov.gh/",              "category": "Government - Finance"},
    {"name": "Association of Ghana Industries", "url": "https://www.agighana.org/",         "category": "Government - Business"},
    {"name": "Private Enterprise Federation",   "url": "https://pef.org.gh/",               "category": "Government - Business"},

    # ── LOCAL GOVERNMENT ─────────────────────────────────────────────────
    {"name": "Local Government Service",        "url": "https://lgs.gov.gh/",              "category": "Government - Local"},
]

# ── All tag/class combinations to try when looking for headlines
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
    ("h2", "views-field-title"),
    ("span", "views-field-title"),
    ("h3", "views-field-title"),
    ("div", "field-title"),
    ("h2", "node-title"),
    ("h3", "node-title"),
    ("a",  "node-title"),
    ("h2", "field-content"),
    ("h3", "field-content"),
    ("div", "news-list"),
    ("h4", "entry-title"),
    ("h4", "post-title"),
]


def test_site(site):
    name     = site["name"]
    url      = site["url"]
    category = site.get("category", "Uncategorized")

    print(f"\n{'='*60}")
    print(f"TESTING:  {name}")
    print(f"CATEGORY: {category}")
    print(f"URL:      {url}")
    print(f"{'='*60}")

    # ── Step 1: Can we reach it?
    try:
        response = requests.get(url, headers=HEADERS, timeout=15, verify=True)
        print(f"Status:   {response.status_code}")

        if response.status_code == 403:
            print("RESULT:   ❌ BLOCKED (403) — Site is rejecting scrapers")
            print("ACTION:   Skip. Look for an RSS feed or press release PDF instead.")
            return {"name": name, "url": url, "category": category, "status": "blocked"}

        if response.status_code == 404:
            print("RESULT:   ❌ PAGE NOT FOUND (404)")
            print("ACTION:   Try the homepage URL instead of a sub-page.")
            return {"name": name, "url": url, "category": category, "status": "not_found"}

        if response.status_code in [301, 302]:
            print(f"INFO:     Site redirected — following redirect automatically")

        if response.status_code not in [200, 301, 302]:
            print(f"RESULT:   ❌ UNEXPECTED STATUS {response.status_code}")
            return {"name": name, "url": url, "category": category, "status": "error"}

        print(f"Size:     {len(response.text):,} characters received")

    except requests.exceptions.SSLError:
        # Try again without SSL verification for government sites with old certs
        try:
            response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            print(f"Status:   {response.status_code} (SSL verification disabled)")
        except Exception:
            print("RESULT:   ❌ SSL ERROR — Cannot connect even without SSL verification")
            return {"name": name, "url": url, "category": category, "status": "ssl_error"}

    except requests.exceptions.ConnectionError:
        print("RESULT:   ❌ CONNECTION FAILED — Site unreachable or domain does not exist")
        return {"name": name, "url": url, "category": category, "status": "unreachable"}

    except requests.exceptions.Timeout:
        print("RESULT:   ❌ TIMEOUT — Site took longer than 15 seconds to respond")
        return {"name": name, "url": url, "category": category, "status": "timeout"}

    # ── Step 2: Parse the HTML and try every headline pattern
    soup       = BeautifulSoup(response.text, "html.parser")
    best_tag   = None
    best_class = None
    best_count = 0
    best_samples = []

    for tag, css_class in HEADLINE_PATTERNS:
        if css_class:
            elements = soup.find_all(tag, class_=css_class)
        else:
            elements = soup.find_all(tag)

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
        if count > best_count:
            best_count   = count
            best_tag     = tag
            best_class   = css_class
            best_samples = headlines_with_links[:3]

    # ── Step 3: Report findings
    if best_count == 0:
        print("RESULT:   ⚠️  REACHABLE but NO HEADLINES FOUND")
        print("          Site likely loads content via JavaScript,")
        print("          uses unusual CSS classes, or has no news section.")

        # Show what heading tags DO exist to help with manual inspection
        print("\n  Heading tags found on page (for manual inspection):")
        for tag in ["h1", "h2", "h3", "h4"]:
            found = soup.find_all(tag)
            if found:
                sample = found[0].get_text(strip=True)[:60]
                print(f"    <{tag}> — {len(found)} found — e.g. \"{sample}\"")

        return {"name": name, "url": url, "category": category, "status": "no_headlines"}

    # ── Step 4: Build the base URL for relative links
    from urllib.parse import urlparse
    parsed   = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    print(f"RESULT:   ✅ SCRAPEABLE — {best_count} headlines found")
    print(f"PATTERN:  tag='{best_tag}', class='{best_class}'")
    print(f"\nSample headlines:")
    for i, sample in enumerate(best_samples, 1):
        href = sample["href"]
        if href and not href.startswith("http"):
            href = base_url + href
        print(f"  {i}. {sample['text']}")
        print(f"     → {href}")

    # ── Print the exact config block to copy
    print(f"\n✅ ADD THIS TO html_scraper.py HTML_SOURCES:")
    print(f"""    {{
        "name":          "{name}",
        "url":           "{url}",
        "article_tag":   "{best_tag}",
        "article_class": "{best_class}",
        "base_url":      "{base_url}"
    }},""")

    return {
        "name":          name,
        "url":           url,
        "category":      category,
        "status":        "scrapeable",
        "article_tag":   best_tag,
        "article_class": best_class,
        "base_url":      base_url,
        "count":         best_count
    }


def print_category_header(category):
    print(f"\n\n{'#'*60}")
    print(f"  {category.upper()}")
    print(f"{'#'*60}")


def main():
    # ── Allow filtering by category from command line
    # Usage: python site_tester.py media
    # Usage: python site_tester.py government
    # Usage: python site_tester.py all   (default)
    filter_arg = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    sites_to_run = []
    for site in SITES_TO_TEST:
        cat = site.get("category", "").lower()
        if filter_arg == "all":
            sites_to_run.append(site)
        elif filter_arg == "media" and "media" in cat:
            sites_to_run.append(site)
        elif filter_arg == "government" and "government" in cat:
            sites_to_run.append(site)
        elif filter_arg in cat:
            sites_to_run.append(site)

    print("=" * 60)
    print("  VeriGhana Site Tester")
    print(f"  Testing {len(sites_to_run)} sites (filter: '{filter_arg}')")
    print("=" * 60)

    results       = []
    current_cat   = None

    for site in sites_to_run:
        # Print a category header when the category changes
        cat = site.get("category", "Other")
        if cat != current_cat:
            print_category_header(cat)
            current_cat = cat

        result = test_site(site)
        results.append(result)

        # Small delay between requests — be polite to government servers
        time.sleep(1)

    # ── Final summary grouped by status
    scrapeable   = [r for r in results if r.get("status") == "scrapeable"]
    no_headlines = [r for r in results if r.get("status") == "no_headlines"]
    blocked      = [r for r in results if r.get("status") == "blocked"]
    unreachable  = [r for r in results if r.get("status") in ["unreachable", "timeout", "ssl_error", "not_found", "error"]]

    print(f"\n\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Scrapeable:          {len(scrapeable)} sites")
    print(f"⚠️  Reachable/no data:   {len(no_headlines)} sites")
    print(f"❌ Blocked (403):        {len(blocked)} sites")
    print(f"❌ Unreachable/error:    {len(unreachable)} sites")

    if scrapeable:
        print(f"\n── READY TO ADD TO html_scraper.py ──")
        for r in scrapeable:
            print(f"  ✅ {r['name']} ({r['category']}) — {r.get('count', 0)} headlines")

    if no_headlines:
        print(f"\n── REACHABLE BUT NEEDS MANUAL INSPECTION ──")
        for r in no_headlines:
            print(f"  ⚠️  {r['name']} — open in Chrome and inspect headline tags")

    if blocked:
        print(f"\n── BLOCKED — SKIP THESE ──")
        for r in blocked:
            print(f"  ❌ {r['name']} — look for RSS feed instead")

    if unreachable:
        print(f"\n── UNREACHABLE — CHECK URL OR SKIP ──")
        for r in unreachable:
            print(f"  ❌ {r['name']}")

    # ── Also add to trusted_sources SQL
    if scrapeable:
        print(f"\n── RUN THIS SQL IN SUPABASE TO ADD SCRAPEABLE SITES ──")
        print("INSERT INTO trusted_sources (source_name, official_url, category)")
        print("VALUES")
        values = []
        for r in scrapeable:
            cat_clean = r["category"].replace("Government - ", "").replace("'", "")
            values.append(f"  ('{r['name']}', '{r['base_url']}', '{cat_clean}')")
        print(",\n".join(values))
        print("ON CONFLICT (official_url) DO NOTHING;")


if __name__ == "__main__":
    main()