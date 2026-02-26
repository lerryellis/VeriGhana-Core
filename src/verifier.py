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

MAX_RETRIES = 3

# ── All free tier models available in the new google-genai SDK
# Listed from most capable to lightest
FREE_MODELS = {
    "Gemini 2.0 Flash":      "gemini-2.0-flash",
    "Gemini 2.0 Flash Lite": "gemini-2.0-flash-lite",
    "Gemini 1.5 Flash":      "gemini-1.5-flash",
    "Gemini 1.5 Flash 8B":   "gemini-1.5-flash-8b",
}

# Default model used if none is selected
DEFAULT_MODEL = "gemini-2.0-flash-lite"


def call_gemini_with_retry(prompt, model_id):
    """
    Calls the Gemini API with automatic retry on rate limit errors.
    Waits progressively longer between each attempt.
    Raises RuntimeError with a clear message if all retries fail.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt
            )
            return response

        except Exception as e:
            error_str = str(e)

            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < MAX_RETRIES:
                    wait_seconds = 10 * attempt
                    print(f"Rate limit hit on {model_id}. Waiting {wait_seconds}s (attempt {attempt}/{MAX_RETRIES})...")
                    time.sleep(wait_seconds)
                    continue
                else:
                    raise RuntimeError(
                        f"QUOTA_EXHAUSTED: Daily limit reached for {model_id}. "
                        f"Please select a different model from the dropdown and try again."
                    )

            elif "404" in error_str or "NOT_FOUND" in error_str:
                raise RuntimeError(
                    f"MODEL_NOT_FOUND: '{model_id}' is not available on your API key. "
                    f"Please select a different model from the dropdown."
                )

            else:
                raise


def embed_text_with_retry(text, task_type="RETRIEVAL_QUERY"):
    """
    Generates a vector embedding with automatic retry on rate limit errors.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type)
            )
            return response.embeddings[0].values

        except Exception as e:
            error_str = str(e)

            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < MAX_RETRIES:
                    wait_seconds = 10 * attempt
                    print(f"Embedding rate limit. Waiting {wait_seconds}s (attempt {attempt}/{MAX_RETRIES})...")
                    time.sleep(wait_seconds)
                    continue
                else:
                    raise RuntimeError(
                        "QUOTA_EXHAUSTED: Embedding quota reached. Please wait and try again."
                    )
            else:
                raise


def verify_claim(user_claim, model_id=DEFAULT_MODEL):
    """
    Main verification function.
    Accepts model_id so the user can switch models from the app dropdown.
    Always returns a structured dict — never crashes the app.
    """
    supabase = get_supabase_client()

    # Step 1 — Embed the user's claim for vector search
    try:
        claim_embedding = embed_text_with_retry(user_claim, task_type="RETRIEVAL_QUERY")
    except RuntimeError as e:
        return {
            "verdict": "UNAVAILABLE",
            "score": 0,
            "explanation": str(e),
            "sources": [],
            "model_used": model_id
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
            "sources": [],
            "model_used": model_id
        }

    if not matched_articles:
        return {
            "verdict": "UNCORROBORATED",
            "score": 10,
            "explanation": "No matching stories found in any trusted Ghanaian source.",
            "sources": [],
            "model_used": model_id
        }

    # Step 3 — Build the prompt with matched context
    context = "\n\n".join([
        f"Source: {a['title']}\n{a['content_text'][:300]}"
        for a in matched_articles
    ])

    prompt = f"""You are a fact-checker for Ghana.
A user submitted this claim: '{user_claim}'

Here are the top matching stories from trusted Ghanaian sources:
{context}

Based ONLY on the sources above, determine:
1. Does any source CONFIRM the claim? Reply verdict: Verified
2. Does any source CONTRADICT the claim? Reply verdict: False
3. No clear match found? Reply verdict: Uncorroborated

Reply with JSON only. No markdown. No text outside the JSON object:
{{"verdict": "Verified|False|Uncorroborated", "score": 0-100, "explanation": "one sentence summary"}}"""

    # Step 4 — Call the selected model with retry logic
    try:
        result_response = call_gemini_with_retry(prompt, model_id)
        raw = result_response.text.strip().replace("```json", "").replace("```", "")
        result = json.loads(raw)
        result["sources"] = [
            {"title": a["title"], "url": a.get("url_link", "")}
            for a in matched_articles
        ]
        result["model_used"] = model_id
        return result

    except RuntimeError as e:
        return {
            "verdict": "UNAVAILABLE",
            "score": 0,
            "explanation": str(e),
            "sources": [
                {"title": a["title"], "url": a.get("url_link", "")}
                for a in matched_articles
            ],
            "model_used": model_id
        }
    except json.JSONDecodeError:
        return {
            "verdict": "UNCORROBORATED",
            "score": 30,
            "explanation": "Could not parse AI response. Please try again.",
            "sources": matched_articles[:3],
            "model_used": model_id
        }