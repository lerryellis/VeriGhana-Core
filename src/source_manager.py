"""
source_manager.py
Handles reading and auto-writing verified sites into html_scraper.py's HTML_SOURCES list.
"""

import re
import os

# ── Path to html_scraper.py (adjust if your file is in a subdirectory)
HTML_SCRAPER_PATH = os.path.join(os.path.dirname(__file__), "html_scraper.py")


def get_existing_urls() -> set:
    """Parse html_scraper.py and return a set of all URLs already in HTML_SOURCES."""
    if not os.path.exists(HTML_SCRAPER_PATH):
        return set()

    with open(HTML_SCRAPER_PATH, "r") as f:
        content = f.read()

    return set(re.findall(r'"url"\s*:\s*"(https?://[^"]+)"', content))


def build_source_entry(result: dict) -> str:
    """Build a formatted dict entry string for one verified site."""
    return (
        f'    {{\n'
        f'        "name":          "{result["name"]}",\n'
        f'        "url":           "{result["url"]}",\n'
        f'        "article_tag":   "{result["article_tag"]}",\n'
        f'        "article_class": "{result["article_class"]}",\n'
        f'        "base_url":      "{result["base_url"]}"\n'
        f'    }}'
    )


def add_source_to_scraper(result: dict) -> dict:
    """
    Append a verified site to HTML_SOURCES in html_scraper.py.
    Returns {"success": bool, "message": str, "skipped": bool}
    """
    if not os.path.exists(HTML_SCRAPER_PATH):
        return {
            "success": False,
            "skipped": False,
            "message": f"html_scraper.py not found at: {HTML_SCRAPER_PATH}"
        }

    # Skip if already present
    existing_urls = get_existing_urls()
    if result["url"] in existing_urls:
        return {
            "success": True,
            "skipped": True,
            "message": f"Already exists in HTML_SOURCES: {result['url']}"
        }

    with open(HTML_SCRAPER_PATH, "r") as f:
        content = f.read()

    # Find HTML_SOURCES = [ ... ] and insert before the closing ]
    # Strategy: find the last occurrence of a `},` or `}` just before the `]`
    # that closes HTML_SOURCES, and insert after it.
    pattern = r'(HTML_SOURCES\s*=\s*\[)(.*?)(\])'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return {
            "success": False,
            "skipped": False,
            "message": "Could not find HTML_SOURCES = [...] in html_scraper.py. "
                       "Make sure your list is named exactly HTML_SOURCES."
        }

    new_entry = build_source_entry(result)
    original_list_body = match.group(2)

    # Ensure the last real entry ends with a comma before we append
    stripped_body = original_list_body.rstrip()
    if stripped_body and not stripped_body.endswith(","):
        # Add trailing comma to last entry
        original_list_body = original_list_body.rstrip() + ",\n"

    new_list_body = original_list_body + new_entry + ",\n"

    new_content = (
        content[:match.start()] +
        match.group(1) +
        new_list_body +
        match.group(3) +
        content[match.end():]
    )

    with open(HTML_SCRAPER_PATH, "w") as f:
        f.write(new_content)

    return {
        "success": True,
        "skipped": False,
        "message": f"✅ Added '{result['name']}' to HTML_SOURCES in html_scraper.py"
    }


def get_scraper_source_count() -> int:
    """Return how many entries are currently in HTML_SOURCES."""
    if not os.path.exists(HTML_SCRAPER_PATH):
        return 0
    with open(HTML_SCRAPER_PATH, "r") as f:
        content = f.read()
    return len(re.findall(r'"url"\s*:\s*"https?://[^"]+"', content))