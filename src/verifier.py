import os
import sys
import json
import time
sys.path.insert(0, os.path.dirname(__file__))
from database_utils import get_supabase_client
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Maximum number of times to retry a failed API call before giving up
MAX_RETRIES = 3

def call_gemini_with_retry(prompt):
    """
    Calls the Gemini API with automatic retry on rate limit errors.
    Waits progressively longer between each attempt:
    Attempt 1 fails → wait 10s → Attempt 2 fails → wait 20s → Attempt 3 fails → give up
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            return response

        except Exception as e:
            error_str = str(e)

            # Check if this is a rate limit / quota error
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < MAX_RETRIES:
                    wait_seconds = 10 * attempt  # 10s, then 20s, then 30s
                    print(f"Rate limit hit. Waiting {wait_seconds}s before retry {attempt}/{MAX_RETRIES}...")
                    time.sleep(wait_seconds)
                    continue
                else:
                    # All retries exhausted — raise a clear, readable error
                    raise RuntimeError(
                        "QUOTA_EXHAUSTED: The Gemini free tier daily limit has been reached. "
                        "Please wait until midnight (Pacific Time) for the quota to reset, "
                        "or add billing at https://ai.google.dev to increase your limit."
                    )
            else:
                # Not a rate limit error — raise immediately, no point retrying
                raise


def embed_text_with_retry(text, task_type="RETRIEVAL_QUERY"):
    """
    Generates an embedding with automatic retry on rate limit errors.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type)
            )
            return response.embeddings[0].values

        except Exception as e:
            error_str = str(e)

            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < MAX_RETRIES:
                    wait_seconds = 10 * attempt
                    print(f"Embedding rate limit hit. Waiting {wait_seconds}s before retry {attempt}/{MAX_RETRIES}...")
                    time.sleep(wait_seconds)
                    continue
                else:
                    raise RuntimeError(
                        "QUOTA_EXHAUSTED: Embedding quota reached. Please wait and try again."
                    )
            else:
                raise


def verify_claim(user_claim):
    """
    Main verification function. Returns a structured result dict in all cases —
    including when the API is unavailable — so the app never crashes.
    """
    supabase = get_supabase_client()

    # Step 1 — Embed the user's claim
    try:
        claim_embedding = embed_text_with_retry(user_claim, task_type="RETRIEVAL_QUERY")
    except RuntimeError as e:
        # Return a graceful result instead of crashing
        return {
            "verdict": "UNAVAILABLE",
            "score": 0,
            "explanation": str(e),
            "sources": []
        }

    # Step 2 — Search the database for similar trusted articles
    try:
        response = supabase.rpc("match_articles", {
            "query_embedding": claim_embedding,
            "match_threshold": 0.7,
            "match_count": 5
        }).execute()
        matched_articles = response.data
    except Exception as e:
        return {
            "verdict": "UNAVAILABLE",
            "score": 0,
            "explanation": f"Database search failed: {e}",
            "sources": []
        }

    if not matched_articles:
        return {
            "verdict": "UNCORROBORATED",
            "score": 10,
            "explanation": "No matching stories found in any trusted Ghanaian source.",
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

Reply with JSON only, no markdown, no explanation outside the JSON:
{{"verdict": "Verified|False|Uncorroborated", "score": 0-100, "explanation": "one sentence"}}"""

    # Step 4 — Call Gemini with retry logic
    try:
        result_response = call_gemini_with_retry(prompt)
        raw = result_response.text.strip().replace("```json", "").replace("```", "")
        result = json.loads(raw)
        result["sources"] = [
            {"title": a["title"], "url": a.get("url_link", "")}
            for a in matched_articles
        ]
        return result

    except RuntimeError as e:
        # Quota exhausted after all retries — return graceful message
        return {
            "verdict": "UNAVAILABLE",
            "score": 0,
            "explanation": str(e),
            "sources": [
                {"title": a["title"], "url": a.get("url_link", "")}
                for a in matched_articles
            ]
        }
    except json.JSONDecodeError:
        return {
            "verdict": "UNCORROBORATED",
            "score": 30,
            "explanation": "Could not parse the AI response. Please try again.",
            "sources": matched_articles[:3]
        }