import feedparser
import os
from supabase import create_client, Client
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# FIX 1: load_dotenv() reads your .env file so Python can find your keys locally.
# On GitHub Actions, keys are injected automatically — this line is harmless there.
load_dotenv()

# Define the trusted RSS feeds for the National Fact Database
TRUSTED_FEEDS = [
    {'name': 'Citi Newsroom', 'url': 'https://citinewsroom.com/rss/topstories.rss'},
    {'name': 'Joy Online',    'url': 'https://www.myjoyonline.com/feed'},
    {'name': 'Pulse Ghana',   'url': 'https://www.pulse.com.gh/rss'},
]

# FIX 2: Client is created inside a function, not at module level.
# This prevents the script from crashing at import time if keys are missing.
def get_supabase_client() -> Client:
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    if not supabase_url or not supabase_key:
        raise ValueError('Keys not found. Check your .env file or GitHub Secrets.')
    return create_client(supabase_url, supabase_key)

def get_source_id(supabase: Client, source_name: str):
    response = supabase.table('trusted_sources').select('id').eq('source_name', source_name).execute()
    if response.data:
        return response.data[0]['id']
    return None

def run_ingestion_pipeline():
    supabase_client = get_supabase_client()
    total_processed = 0

    for source in TRUSTED_FEEDS:
        source_name = source['name']
        feed_url    = source['url']
        print(f'Beginning ingestion from: {source_name}')

        source_id = get_source_id(supabase_client, source_name)
        if not source_id:
            print(f'WARNING: {source_name} not found in trusted_sources. Skipping.')
            continue

        parsed_feed = feedparser.parse(feed_url)
        print(f'Found {len(parsed_feed.entries)} articles.')

        for entry in parsed_feed.entries:
            title     = entry.get('title',     'No Title Available')
            link      = entry.get('link',      '')
            summary   = entry.get('summary',   '')
            published = entry.get('published', None)
            clean_text = BeautifulSoup(summary, 'html.parser').get_text()

            try:
                # FIX 3: source_id is now included — links article to its trusted source.
                # FIX 4: published_date is now included — no longer thrown away.
                # upsert with on_conflict='url_link' safely skips duplicates.
                supabase_client.table('fact_entries').upsert({
                    'title':          title,
                    'url_link':       link,
                    'content_text':   clean_text,
                    'source_id':      source_id,
                    'published_date': published,
                }, on_conflict='url_link').execute()
                print(f'  Processed: {title[:60]}...')
                total_processed += 1
            except Exception as error:
                print(f'  Error inserting record: {error}')

    print(f'Ingestion complete. Total articles processed: {total_processed}')

if __name__ == '__main__':
    run_ingestion_pipeline()
