import os
import sys
import json
sys.path.insert(0, os.path.dirname(__file__))
from database_utils import get_supabase_client
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def verify_claim(user_claim):
    supabase = get_supabase_client()

    # Step 1 — Embed the user's claim for vector search
    embedding_response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=user_claim,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
    )
    claim_embedding = embedding_response.embeddings[0].values

    # Step 2 — Search the database for similar trusted articles
    response = supabase.rpc("match_articles", {
        "query_embedding": claim_embedding,
        "match_threshold": 0.7,
        "match_count": 5
    }).execute()

    matched_articles = response.data

    if not matched_articles:
        return {
            "verdict": "UNCORROBORATED",
            "score": 10,
            "explanation": "No matching stories found in trusted sources.",
            "sources": []
        }

    # Step 3 — Ask Gemini to compare the claim against matched articles
    context = "\n\n".join([
        f"Source: {a['title']}\n{a['content_text'][:300]}"
        for a in matched_articles
    ])

    prompt = f"""You are a fact-checker for Ghana.
A user submitted this claim: '{user_claim}'

Here are the top matching stories from trusted Ghanaian sources:
{context}

Based ONLY on the sources above, determine:
1. Does any source CONFIRM the claim? (Verified)
2. Does any source CONTRADICT the claim? (False)
3. No clear match? (Uncorroborated)

Reply with JSON only, no markdown:
{{"verdict": "Verified|False|Uncorroborated", "score": 0-100, "explanation": "one sentence"}}"""

    # Step 4 — Call Gemini using the new client style
    result_response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    try:
        raw = result_response.text.strip().replace("```json", "").replace("```", "")
        result = json.loads(raw)
        result["sources"] = [
            {"title": a["title"], "url": a.get("url_link", "")}
            for a in matched_articles
        ]
        return result
    except Exception:
        return {
            "verdict": "UNCORROBORATED",
            "score": 30,
            "explanation": "Unable to determine verdict from available sources.",
            "sources": matched_articles[:3]
        }