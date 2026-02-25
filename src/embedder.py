import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from database_utils import get_supabase_client
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def generate_embedding(text):
    result = genai.embed_content(
        model='models/text-embedding-004',
        content=text
    )
    return result['embedding']

def embed_unprocessed_articles():
    supabase = get_supabase_client()
    print('Fetching articles without embeddings...')

    # Get articles that don't have embeddings yet
    response = supabase.table('fact_entries').select('id, title, content_text').is_('content_embedding', 'null').limit(50).execute()

    articles = response.data
    print(f'Found {len(articles)} articles to process')

    for article in articles:
        text_to_embed = article['title'] + ' ' + article['content_text'][:500]
        try:
            embedding = generate_embedding(text_to_embed)
            supabase.table('fact_entries').update({'content_embedding': embedding}).eq('id', article['id']).execute()
            print(f'Embedded article {article["id"]}: {article["title"][:40]}...')
        except Exception as e:
            print(f'Error embedding article {article["id"]}: {e}')

    print('Embedding complete.')

if __name__ == '__main__':
    embed_unprocessed_articles()
