import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from database_utils import get_supabase_client
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_embedding(text):
    response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )
    return response.embeddings[0].values

def embed_unprocessed_articles():
    supabase = get_supabase_client()
    print("Fetching articles without embeddings...")

    response = supabase.table("fact_entries") \
        .select("id, title, content_text") \
        .is_("content_embedding", "null") \
        .limit(1000) \
        .execute()

    articles = response.data
    print(f"Found {len(articles)} articles to process")

    for article in articles:
        text_to_embed = article["title"] + " " + article["content_text"][:500]
        try:
            embedding = generate_embedding(text_to_embed)
            supabase.table("fact_entries") \
                .update({"content_embedding": embedding}) \
                .eq("id", article["id"]) \
                .execute()
            print(f"Embedded article {article['id']}: {article['title'][:40]}...")
        except Exception as e:
            print(f"Error embedding article {article['id']}: {e}")

    print("Embedding complete.")

if __name__ == "__main__":
    embed_unprocessed_articles()