import feedparser
import os
from supabase import create_client, Client
from bs4 import BeautifulSoup

# Define the trusted Really Simple Syndication feeds for the National Fact Database
TRUSTED_FEEDS = [
    "https://citinewsroom.com/rss/topstories.rss",
    "https://www.myjoyonline.com/feed",
    "https://www.pulse.com.gh/rss"
]

# Initialize the Supabase client using Application Programming Interface credentials
# Note: Ensure these are set in your environment or GitHub Secrets
SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_ingestion_pipeline():
    """
    Parses each trusted feed and inserts new records into the Central Database.
    """
    for feed_url in TRUSTED_FEEDS:
        print(f"Beginning ingestion from: {feed_url}")
        parsed_feed = feedparser.parse(feed_url)
        
        for entry in parsed_feed.entries:
            # Extract basic metadata for the fact repository
            title = entry.get("title", "No Title Available")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            
            # Use BeautifulSoup to clean any HyperText Markup Language tags from the summary
            clean_text = BeautifulSoup(summary, "html.parser").get_text()

            try:
                # Attempt to insert the data into the 'fact_entries' table
                # The 'upsert' logic prevents duplicate entries based on the Uniform Resource Locator
                data = supabase_client.table("fact_entries").upsert({
                    "title": title,
                    "url_link": link,
                    "content_text": clean_text,
                    # Source attribution is mapped in the next iteration
                }, on_conflict="url_link").execute()
                print(f"Successfully processed: {title[:50]}...")
            except Exception as error:
                print(f"Error inserting record: {error}")

if __name__ == "__main__":
    run_ingestion_pipeline()
