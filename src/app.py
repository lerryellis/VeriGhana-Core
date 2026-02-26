import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from verifier import verify_claim
from database_utils import get_supabase_client
from dotenv import load_dotenv

load_dotenv()

# ─── Page Configuration ───
st.set_page_config(
    page_title='VeriGhana — National Fact Verification',
    page_icon='🇬🇭',
    layout='wide'
)

# ─── Header ───
st.title('🇬🇭 VeriGhana')
st.subheader('Ghana\'s Centralized Automated Verification Platform')
st.markdown('---')

# ─── Main Layout ───
col1, col2 = st.columns([2, 1])

with col1:
    st.header('Verify a Claim')
    user_input = st.text_area(
        'Paste a suspicious post, news card text, or rumor below:',
        height=150,
        placeholder='e.g. Government announces 30% tax on Mobile Money starting Monday...'
    )
if st.button("Check This Claim", type="primary"):
    if user_input.strip():
        with st.spinner("Searching trusted Ghanaian sources..."):
            result = verify_claim(user_input)

        score   = result.get("score", 0)
        verdict = result.get("verdict", "Unknown")
        explanation = result.get("explanation", "")
        sources = result.get("sources", [])

        # Handle each possible verdict state
        if verdict == "Verified":
            st.success(f"✅ VERDICT: Verified — Confidence: {score}/100")
        elif verdict == "False":
            st.error(f"❌ VERDICT: False — Confidence: {score}/100")
        elif verdict == "UNAVAILABLE":
            st.warning("⏳ AI Unavailable — Daily quota reached")
            st.info(explanation)
            if sources:
                st.subheader("However, these related articles were found:")
        else:
            st.warning(f"⚠️ VERDICT: {verdict} — Confidence: {score}/100")

        if verdict != "UNAVAILABLE":
            st.progress(score / 100)

        st.write(f"**Analysis:** {explanation}")

        if sources:
            st.subheader("Matching Sources:")
            for source in sources:
                if isinstance(source, dict):
                    st.write(f"- [{source.get('title', 'Article')}]({source.get('url', '#')})")
    else:
        st.warning("Please enter a claim to verify.")

with col2:
    st.header('Database Stats')
    try:
        supabase = get_supabase_client()
        count_resp = supabase.table('fact_entries').select('id', count='exact').execute()
        total = count_resp.count or 0
        st.metric('Total Facts Indexed', f'{total:,}')

        sources_resp = supabase.table('trusted_sources').select('source_name, category').execute()
        st.subheader('Trusted Sources:')
        for s in sources_resp.data:
            st.write(f'• {s["source_name"]} ({s["category"]})')
    except Exception as e:
        st.error(f'Could not connect to database: {e}')

st.markdown('---')
st.caption('VeriGhana uses Retrieval-Augmented Generation to verify claims against a curated database of trusted Ghanaian sources only.')
