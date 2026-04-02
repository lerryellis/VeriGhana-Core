"""
VeriGhana Bot Identity
======================
Shared HTTP headers for all scrapers and the site tester.

Two modes:
  BROWSER_HEADERS  — impersonates Chrome (works for most sites)
  BOT_HEADERS      — honest VeriGhana bot (bypasses Akamai/Cloudflare challenges)

The challenge detector checks if a response is a bot challenge page
and signals the caller to retry with BOT_HEADERS.
"""

# Honest bot identity — identifies VeriGhana, links to the site
BOT_HEADERS = {
    "User-Agent":      "VeriGhana-Bot/1.0 (+https://verighana.com; fact-checking research)",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Browser impersonation — works for most sites but triggers Akamai/Cloudflare
BROWSER_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def is_challenge_page(response) -> bool:
    """
    Detect if the response is a bot challenge page (Akamai, Cloudflare, etc.)
    rather than real content. These typically return HTTP 200 but with a tiny
    HTML page containing a JS challenge.
    """
    if response is None or not hasattr(response, 'text'):
        return False

    text = response.text
    content_length = len(text)

    # Akamai Bot Manager: returns ~1800-2000 byte challenge page
    if content_length < 3000:
        akamai_signals = [
            'sec_cpt' in (response.headers.get('set-cookie', '')),
            'challenge' in text.lower(),
            'ak_bmsc' in (response.headers.get('set-cookie', '')),
            'akamai' in response.headers.get('server-timing', '').lower(),
        ]
        if sum(akamai_signals) >= 2:
            return True

    # Cloudflare challenge: "Just a moment..." or "Checking your browser"
    if content_length < 10000:
        cf_signals = [
            'cf-ray' in {k.lower() for k in response.headers},
            'just a moment' in text.lower(),
            'checking your browser' in text.lower(),
            'cf-chl-bypass' in text.lower(),
            '_cf_chl_opt' in text,
        ]
        if sum(cf_signals) >= 2:
            return True

    # Generic: very small page with "challenge" or "verify" in title
    if content_length < 5000:
        lower = text.lower()
        if '<title>' in lower:
            title_start = lower.index('<title>') + 7
            title_end = lower.index('</title>', title_start) if '</title>' in lower[title_start:] else title_start + 100
            title = lower[title_start:title_end]
            if any(word in title for word in ['challenge', 'verification', 'security check', 'please wait']):
                return True

    return False
