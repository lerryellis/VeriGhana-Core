import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load secret keys from the .env file
load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError('Keys not found. Check your .env file.')
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_source_id(source_name):
    supabase = get_supabase_client()
    response = supabase.table('trusted_sources').select('id').eq('source_name', source_name).execute()
    if response.data:
        return response.data[0]['id']
    return None

def save_fact_entry(source_id, title, content, url, published_date):
    supabase = get_supabase_client()
    data = {
        'source_id': source_id,
        'title': title,
        'content_text': content,
        'url_link': url,
        'published_date': published_date
    }
    try:
        result = supabase.table('fact_entries').upsert(data, on_conflict='url_link').execute()
        return result
    except Exception as error:
        print(f'Error saving to database: {error}')
        return None
