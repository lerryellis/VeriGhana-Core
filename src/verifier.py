import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from database_utils import get_supabase_client
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def verify_claim(user_claim):
    supabase = get_supabase_client()

    # Step 1: Convert the user's claim into an embedding
    claim_embedding = genai.embed_content(
        model='models/text-embedding-004',
        content=user_claim
    )['embedding']

    # Step 2: Search the database for similar articles
    response = supabase.rpc('match_articles', {
        'query_embedding': claim_embedding,
        'match_threshold': 0.7,
        'match_count': 5
    }).execute()

    matched_articles = response.data

    if not matched_articles:
        return {
            'verdict': 'UNCORROBORATED',
            'score': 10,
            'explanation': 'No matching stories found in trusted sources.',
            'sources': []
        }

    # Step 3: Ask Gemini to compare the claim against the matched articles
    context = '\n\n'.join([f"Source: {a['title']}\n{a['content_text'][:300]}" for a in matched_articles])

    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""You are a fact-checker for Ghana. 
A user submitted this claim: '{user_claim}'

Here are the top matching stories from trusted Ghanaian sources:
{context}

Based ONLY on the sources above, determine:
1. Does any source CONFIRM the claim? (Verified)
2. Does any source CONTRADICT the claim? (False)
3. No clear match? (Uncorroborated)

Reply with JSON only:
{{"verdict": "Verified|False|Uncorroborated", "score": 0-100, "explanation": "one sentence"}}
"""

    response = model.generate_content(prompt)
    import json
    try:
        result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
        result['sources'] = [{'title': a['title'], 'url': a.get('url_link', '')} for a in matched_articles]
        return result
    except:
        return {
            'verdict': 'UNCORROBORATED',
            'score': 30,
            'explanation': 'Unable to determine verdict from available sources.',
            'sources': matched_articles[:3]
        }
