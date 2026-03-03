import requests
from bs4 import BeautifulSoup
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database_utils import get_source_id, get_supabase_client
from dotenv import load_dotenv

load_dotenv()

# Each site needs its own config because every site is structured differently
HTML_SOURCES = [
    
    {
        "name": "Ministry of Finance",
        "url": "https://x.com/mocghana ",
        "article_tag": "h2",
        "article_class": "entry-title",
        "base_url": "https://x.com/mocghana "
    },
    {
        "name": "Ministry of Finance",
        "url": "https://e-services.mint.gov.gh/",
        "article_tag": "h2",
        "article_class": "entry-title",
        "base_url": "https://e-services.mint.gov.gh/"
    },
    {
        "name": "Ministry of Finance",
        "url": "  https://www.facebook.com/moc.gov.gh/",
        "article_tag": "h2",
        "article_class": "entry-title",
        "base_url": "https://www.facebook.com/moc.gov.gh/"
    },
    {
            "name": "Ministry of Finance",
            "url": "https://www.moc.gov.gh/",
            "article_tag": "h2",
            "article_class": "entry-title",
            "base_url": "https://www.moc.gov.gh/"
    },

    {
        "name": "Ministry of Finance",
        "url": "https://www.mint.gov.gh/",
        "article_tag": "h2",
        "article_class": "entry-title",
        "base_url": "https://www.mint.gov.gh/"
    },
    
    {
        "name": "Graphic Online",
        "url": "https://yen.com.gh/",
        "article_tag": "h3",
        "article_class": "article-title",  # find this by inspecting the site
        "base_url": "https://yen.com.gh/"
    },
    
     {
        "name": "Graphic Online",
        "url": "https://www.ghanaweb.com/",
        "article_tag": "h3",
        "article_class": "article-title",  # find this by inspecting the site
        "base_url": "https://www.ghanaweb.com/"
    },
    
    {
        "name": "Graphic Online",
        "url": "https://www.graphic.com.gh/news/general-news.html",
        "article_tag": "h3",
        "article_class": "article-title",  # find this by inspecting the site
        "base_url": "https://www.graphic.com.gh"
    },
    {
        "name": "Ghana News Agency",
        "url": "https://www.ghananewsagency.org/",
        "article_tag": "h2",
        "article_class": "entry-title",
        "base_url": "https://www.ghananewsagency.org"
    },
    {
        "name":          "3News",
        "url":           "https://3news.com/",
        "article_tag":   "h3",
        "article_class": "jeg_post_title",
        "base_url":      "https://3news.com"
    },
    
    {
        "name": "Judicial Service",
        "url": "https://judicial.gov.gh/index.php/publications/news-publications/js-latest-news",
        "article_tag": "h3",
        "article_class": "jeg_post_title",
        "base_url": "https://judicial.gov.gh"
    },
    {
        "name":          "Ministry of Finance",
        "url":           "https://mofep.gov.gh/",
        "article_tag":   "h2",
        "article_class": "None",
        "base_url":      "https://mofep.gov.gh"
    },
    {
        "name":          "Citinewsroom",
        "url":           "https://citinewsroom.com/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://citinewsroom.com"
    },
    {
        "name":          "Daily Graphic",
        "url":           "https://www.graphic.com.gh/",
        "article_tag":   "h4",
        "article_class": "None",
        "base_url":      "https://www.graphic.com.gh"
    },
    {
        "name":          "Ministry of Foreign Affairs",
        "url":           "https://mfa.gov.gh/",
        "article_tag":   "h4",
        "article_class": "None",
        "base_url":      "https://mfa.gov.gh"
    },
    {
        "name":          "Ministry of Health",
        "url":           "https://www.moh.gov.gh/",
        "article_tag":   "h2",
        "article_class": "None",
        "base_url":      "https://www.moh.gov.gh"
    },
    {
        "name":          "Communicatoin Authority",
        "url":           "https://nca.org.gh/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://nca.org.gh"
    },
    {
        "name":          "National Identification Authority",
        "url":           "https://nia.gov.gh",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://nia.gov.gh"
    },
    {
        "name":          "GIMPA",
        "url":           "https://www.gimpa.edu.gh",
        "article_tag":   "h2",
        "article_class": "None",
        "base_url":      "https://www.gimpa.edu.gh"
    },
    {
        "name":          "Volta River Authority (VRA)",
        "url":           "https://www.vra.com/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://www.vra.com"
    },
    {
        "name":          "Volta River Authority News",
        "url":           "https://www.vra.com/media/2022_news.php",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://www.vra.com"
    },
    {
        "name":          "Energy Commission",
        "url":           "https://www.energycom.gov.gh",
        "article_tag":   "h4",
        "article_class": "None",
        "base_url":      "https://www.energycom.gov.gh"
    },
    {
        "name":          "Energy Commission (Press Release)",
        "url":           "https://www.energycom.gov.gh/index.php/media-center/latest-news",
        "article_tag":   "h4",
        "article_class": "None",
        "base_url":      "https://www.energycom.gov.gh"
    },
    {
        "name":          "Ghana Investment Promotion Centre (GIPC)",
        "url":           "https://gipc.gov.gh/news-articles/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://gipc.gov.gh"
    },
    {
        "name":          "Ghana Tourism Authority",
        "url":           "https://ghana.travel/blog/",
        "article_tag":   "h2",
        "article_class": "None",
        "base_url":      "https://ghana.travel"
    },
    {
        "name":          "Ghana Tourism Authority",
        "url":           "https://ghana.travel/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://ghana.travel"
    },
    {
        "name":          "Securities and Exchange Comm",
        "url":           "https://sec.gov.gh",
        "article_tag":   "h2",
        "article_class": "None",
        "base_url":      "https://sec.gov.gh"
    },
    {
        "name":          "Citi Newsroom",
        "url":           "https://citinewsroom.com/category/news/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://citinewsroom.com"
    },
    {
        "name":          "Ministry of Tourism",
        "url":           "https://www.touringghana.com/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://www.touringghana.com"
    },
    {
        "name":          "Ministry of Local Government",
        "url":           "http://www.mlgrd.gov.gh/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "http://www.mlgrd.gov.gh"
    },
    {
        "name":          "Ministry of Defence",
        "url":           "https://mod.gov.gh/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://mod.gov.gh"
    },
    {
        "name":          "National Communications Auth",
        "url":           "https://www.nca.org.gh/",
        "article_tag":   "h3",
        "article_class": "None",
        "base_url":      "https://www.nca.org.gh"
    },
]

HEADERS = {
    # This makes your scraper look like a normal browser visit
    # Some sites block requests that do not send this
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def scrape_article_content(article_url):
    """
    Visits an individual article page and extracts the body text.
    """
    try:
        response = requests.get(article_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Most news sites wrap article body in <article> or a div with class
        # containing 'content', 'body', or 'entry'. Try these in order.
        body = (
            soup.find("article") or
            soup.find("div", class_="article-content") or
            soup.find("div", class_="entry-content") or
            soup.find("div", class_="post-content")
        )

        if body:
            # Remove any script or style tags inside the article
            for tag in body(["script", "style"]):
                tag.decompose()
            return body.get_text(separator=" ", strip=True)

        return ""
    except Exception as e:
        print(f"  Could not fetch article content: {e}")
        return ""


def run_html_ingestion():
    supabase = get_supabase_client()
    total_processed = 0

    for source in HTML_SOURCES:
        print(f"\nScraping: {source['name']}")

        source_id = get_source_id(supabase, source["name"])
        if not source_id:
            print(f"  WARNING: {source['name']} not in trusted_sources table. Skipping.")
            continue

        try:
            response = requests.get(source["url"], headers=HEADERS, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all headline elements using the tag and class for this site
            headlines = soup.find_all(source["article_tag"], class_=source["article_class"])
            print(f"  Found {len(headlines)} headlines")

            for item in headlines[:10]:  # Limit to 10 per run to be respectful
                link_tag = item.find("a")
                if not link_tag:
                    continue

                title = link_tag.get_text(strip=True)
                href  = link_tag.get("href", "")

                # Some sites use relative URLs (/news/story) not full URLs
                if href.startswith("http"):
                    full_url = href
                else:
                    full_url = source["base_url"] + href

                # Fetch the full article text from the article page
                content = scrape_article_content(full_url)

                try:
                    supabase.table("fact_entries").upsert({
                        "title":          title,
                        "url_link":       full_url,
                        "content_text":   content,
                        "source_id":      source_id,
                        "published_date": None  # HTML pages rarely show dates cleanly
                    }, on_conflict="url_link").execute()

                    print(f"  Saved: {title[:60]}...")
                    total_processed += 1

                except Exception as e:
                    print(f"  Error saving: {e}")

        except Exception as e:
            print(f"  Could not reach {source['url']}: {e}")

    print(f"\nHTML ingestion complete. Total processed: {total_processed}")


if __name__ == "__main__":
    run_html_ingestion()