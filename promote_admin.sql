-- ── Rename legacy 'client' role to 'user' (end-users) ────────────────────
UPDATE user_profiles SET role = 'user' WHERE role = 'client';
-- ── Rename legacy 'staff' role (if any were set before this migration) ────
-- Staff should be explicitly assigned; leave existing 'staff' rows as-is

-- ── Promote accounts to admin ─────────────────────────────────────────────
UPDATE user_profiles
SET role = 'admin'
WHERE user_id IN (
  SELECT id FROM auth.users
  WHERE email IN ('admin@verighana.com', 'lerryellis@gmail.com')
);

-- ── Verify ────────────────────────────────────────────────────────────────
SELECT up.user_id, au.email, up.role, up.tier
FROM user_profiles up
JOIN auth.users au ON au.id = up.user_id
WHERE au.email IN ('admin@verighana.com', 'lerryellis@gmail.com')
ORDER BY au.email;
