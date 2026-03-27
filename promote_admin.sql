-- Promote admin@verighana.com to admin role
-- Run this once in the Supabase SQL Editor

UPDATE user_profiles
SET role = 'admin'
WHERE user_id = (
  SELECT id FROM auth.users WHERE email = 'admin@verighana.com'
);

-- Verify it worked:
SELECT up.user_id, au.email, up.role, up.tier
FROM user_profiles up
JOIN auth.users au ON au.id = up.user_id
WHERE au.email = 'admin@verighana.com';
