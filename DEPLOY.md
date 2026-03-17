# Deployment Guide

## FastAPI → Railway

1. Push this repo to GitHub (if not already).
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Select this repo (root directory — Railway auto-detects `Procfile`).
4. Add environment variables in Railway dashboard:
   - Copy all keys from `.env.example`
   - Generate a real `ADMIN_API_KEY`: `python3 -c "import secrets; print(secrets.token_urlsafe(40))"`
   - Set `ALLOWED_ORIGINS=https://app.verighana.com` (your Vercel domain)
5. Railway will deploy at e.g. `https://verighana-api.up.railway.app`
6. Note this URL — you need it as `NEXT_PUBLIC_API_URL` in Vercel.

## Next.js → Vercel

1. Go to [vercel.com](https://vercel.com) → New Project → Import from GitHub.
2. Set **Root Directory** to `verighana-web`.
3. Framework: Next.js (auto-detected).
4. Add environment variables:
   ```
   NEXT_PUBLIC_SUPABASE_URL        = <from Supabase Dashboard>
   NEXT_PUBLIC_SUPABASE_ANON_KEY   = <anon key from Supabase>
   NEXT_PUBLIC_API_URL             = <your Railway URL>
   SUPABASE_SERVICE_KEY            = <service_role key from Supabase>
   ADMIN_API_KEY                   = <same token as Railway ADMIN_API_KEY>
   ```
5. Deploy. Vercel gives you a URL like `https://verighana-web.vercel.app`.

## Post-Deploy Checklist

- [ ] Update `ALLOWED_ORIGINS` in Railway to include your Vercel domain
- [ ] Update `index.html` URLs if your domains differ from `app.verighana.com` / `api.verighana.com`
- [ ] Set a custom domain in Vercel (e.g. `app.verighana.com`)
- [ ] Set a custom domain in Railway (e.g. `api.verighana.com`)
- [ ] Supabase: add your Vercel domain to **Authentication → URL Configuration → Site URL** and **Redirect URLs**
- [ ] Supabase: enable Row Level Security policies on `user_profiles`, `verification_log`, `support_tickets`, `payments`
- [ ] Generate a real `ADMIN_API_KEY` and update both Railway + Vercel env vars
- [ ] Test: register an account → verify a claim → check history → account page
- [ ] Test: admin user → `/admin` dashboard → pipeline triggers

## GitHub Actions (Scraper — already configured)

The scraper runs every 6 hours via `.github/workflows/automated_scraper.yml`.
Ensure `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY` are set in **GitHub Secrets**.
