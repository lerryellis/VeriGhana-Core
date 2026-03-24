-- ═══════════════════════════════════════════════════════════════
--  Auto-create user_profiles on new Supabase Auth signup
--  Covers BOTH email/password AND Google OAuth (and any future provider)
--  Run once in Supabase → SQL Editor
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  INSERT INTO public.user_profiles (
    user_id,
    email,
    full_name,
    tier,
    role,
    subscription_status,
    daily_queries_used,
    created_at
  )
  VALUES (
    NEW.id,
    NEW.email,
    -- Google puts the display name in raw_user_meta_data->>'full_name'
    -- Email signup may store it there too via options.data
    COALESCE(
      NEW.raw_user_meta_data->>'full_name',
      NEW.raw_user_meta_data->>'name',
      split_part(NEW.email, '@', 1)   -- fallback: use email prefix
    ),
    'free',
    'client',
    'active',
    0,
    NOW()
  )
  ON CONFLICT (user_id) DO NOTHING;  -- safe to re-run; won't overwrite existing profiles

  RETURN NEW;
END;
$$;

-- Attach trigger to auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_auth_user();

-- Verify: check the function exists
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public' AND routine_name = 'handle_new_auth_user';
