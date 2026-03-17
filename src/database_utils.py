import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_URL or SUPABASE_KEY not found. "
            "Check your .env file (local) or GitHub Secrets (Actions)."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_source_id(supabase: Client, source_name: str, official_url: str = "", category: str = "Media"):
    """
    Returns the ID of a trusted source by name.
    If the source is not yet in the table it is inserted automatically,
    so scrapers never skip a source just because it is missing from the DB.
    """
    response = (
        supabase.table("trusted_sources")
        .select("id")
        .eq("source_name", source_name)
        .execute()
    )
    if response.data:
        return response.data[0]["id"]

    # Auto-register the missing source
    insert = (
        supabase.table("trusted_sources")
        .insert({
            "source_name":  source_name,
            "official_url": official_url or "",
            "category":     category,
        })
        .execute()
    )
    if insert.data:
        print(f"   Auto-registered new source: '{source_name}'")
        return insert.data[0]["id"]

    return None

def save_fact_entry(supabase: Client, source_id, title, content, url, published_date):
    data = {
        "source_id":      source_id,
        "title":          title,
        "content_text":   content,
        "url_link":       url,
        "published_date": published_date
    }
    try:
        result = supabase.table("fact_entries").upsert(
            data, on_conflict="url_link"
        ).execute()
        return result
    except Exception as error:
        print(f"Error saving to database: {error}")
        return None