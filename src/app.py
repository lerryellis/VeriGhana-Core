import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from verifier import verify_claim, FREE_MODELS, DEFAULT_MODEL
from database_utils import get_supabase_client
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="VeriGhana — National Fact Verification",
    page_icon="🇬🇭",
    layout="wide"
)

# ── Login state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🇬🇭 VeriGhana")
    st.subheader("Please log in to access the verification platform")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        email    = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            try:
                supabase = get_supabase_client()
                supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.logged_in = True
                st.rerun()
            except Exception:
                st.error("Login failed. Check your email and password.")

    with tab2:
        new_email = st.text_input("Email Address", key="reg_email")
        new_pass  = st.text_input("Password (minimum 6 characters)", type="password", key="reg_pass")
        if st.button("Create Account"):
            try:
                supabase = get_supabase_client()
                supabase.auth.sign_up({"email": new_email, "password": new_pass})
                st.success("Account created! Check your email to confirm, then log in.")
            except Exception as e:
                st.error(f"Registration failed: {e}")

else:
    # ── Header
    st.title("🇬🇭 VeriGhana")
    st.subheader("Ghana's Centralized Automated Verification Platform")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("Verify a Claim")

        # ── Model selector dropdown
        st.markdown("**Select AI Model**")
        selected_model_name = st.selectbox(
            label="AI Model",
            options=list(FREE_MODELS.keys()),
            index=list(FREE_MODELS.keys()).index("Gemini 2.0 Flash Lite"),
            help="If one model has reached its daily limit, switch to another.",
            label_visibility="collapsed"
        )
        selected_model_id = FREE_MODELS[selected_model_name]
        st.caption(f"Using: `{selected_model_id}` — All models are free tier. Switch if you see a quota error.")

        # ── Claim input
        user_input = st.text_area(
            "Paste a suspicious post, news card text, or rumour below:",
            height=150,
            placeholder="e.g. Government announces 30% tax on Mobile Money starting Monday..."
        )

        if st.button("Check This Claim", type="primary"):
            if user_input.strip():
                with st.spinner(f"Searching trusted sources using {selected_model_name}..."):
                    result = verify_claim(user_input, model_id=selected_model_id)

                verdict     = result.get("verdict", "Unknown")
                score       = result.get("score", 0)
                explanation = result.get("explanation", "")
                sources     = result.get("sources", [])
                model_used  = result.get("model_used", selected_model_id)

                # ── Display verdict
                if verdict == "Verified":
                    st.success(f"✅ VERDICT: Verified — Confidence: {score}/100")
                    st.progress(score / 100)
                elif verdict == "False":
                    st.error(f"❌ VERDICT: False — Confidence: {score}/100")
                    st.progress(score / 100)
                elif verdict == "UNAVAILABLE":
                    st.warning("⏳ AI Model Unavailable")
                    st.info(
                        f"{explanation}\n\n"
                        f"**Try selecting a different model from the dropdown above.**"
                    )
                else:
                    st.warning(f"⚠️ VERDICT: Uncorroborated — Confidence: {score}/100")
                    st.progress(score / 100)

                st.write(f"**Analysis:** {explanation}")
                st.caption(f"Checked using: `{model_used}`")

                # ── Sources
                if sources:
                    st.subheader("Matching Sources Found:")
                    for source in sources:
                        if isinstance(source, dict):
                            title = source.get("title", "Article")
                            url   = source.get("url", "#")
                            st.write(f"- [{title}]({url})")
            else:
                st.warning("Please enter a claim to verify.")

    with col2:
        st.header("Database Stats")
        try:
            supabase   = get_supabase_client()
            count_resp = supabase.table("fact_entries").select("id", count="exact").execute()
            total      = count_resp.count or 0
            st.metric("Total Facts Indexed", f"{total:,}")

            sources_resp = supabase.table("trusted_sources").select("source_name, category").execute()
            st.subheader("Trusted Sources:")
            for s in sources_resp.data:
                st.write(f"• {s['source_name']} ({s['category']})")
        except Exception as e:
            st.error(f"Could not connect to database: {e}")

        st.markdown("---")
        st.subheader("Available AI Models")
        for name, model_id in FREE_MODELS.items():
            st.write(f"• **{name}** `{model_id}`")
        st.caption("Switch models in the dropdown if one hits its daily limit.")

    st.markdown("---")
    st.caption(
        "VeriGhana uses Retrieval-Augmented Generation to verify claims against "
        "a curated database of trusted Ghanaian sources only."
    )