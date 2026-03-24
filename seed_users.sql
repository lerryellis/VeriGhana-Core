-- ═══════════════════════════════════════════════════════════════
--  Seed 20 random users on the free (basic) plan
--  Run in Supabase → SQL Editor
--
--  Strategy: insert into auth.users first, then user_profiles.
--  Passwords are set to a placeholder hash — these are test accounts.
-- ═══════════════════════════════════════════════════════════════

DO $$
DECLARE
    users TEXT[][] := ARRAY[
        ARRAY['Abena Mensah',       'abena.mensah@gmail.com',       'GH'],
        ARRAY['Kwame Asante',       'kwame.asante@yahoo.com',       'GH'],
        ARRAY['Ama Boateng',        'ama.boateng@outlook.com',      'GH'],
        ARRAY['Kofi Adjei',         'kofi.adjei@gmail.com',         'GH'],
        ARRAY['Akua Owusu',         'akua.owusu@hotmail.com',       'GH'],
        ARRAY['Yaw Darko',          'yaw.darko@gmail.com',          'GH'],
        ARRAY['Efua Tetteh',        'efua.tetteh@yahoo.com',        'GH'],
        ARRAY['Nana Appiah',        'nana.appiah@gmail.com',        'GH'],
        ARRAY['Adwoa Frimpong',     'adwoa.frimpong@outlook.com',   'GH'],
        ARRAY['Kweku Bonsu',        'kweku.bonsu@gmail.com',        'GH'],
        ARRAY['Serwaa Amoah',       'serwaa.amoah@gmail.com',       'GH'],
        ARRAY['Fiifi Asare',        'fiifi.asare@hotmail.com',      'GH'],
        ARRAY['Maame Acheampong',   'maame.acheampong@gmail.com',   'GH'],
        ARRAY['Yaa Dankwa',         'yaa.dankwa@yahoo.com',         'GH'],
        ARRAY['Kojo Ntim',          'kojo.ntim@gmail.com',          'GH'],
        ARRAY['Abina Ofori',        'abina.ofori@outlook.com',      'GH'],
        ARRAY['Kobbina Quansah',    'kobbina.quansah@gmail.com',    'GH'],
        ARRAY['Akosua Agyei',       'akosua.agyei@yahoo.com',       'GH'],
        ARRAY['Ekow Ankrah',        'ekow.ankrah@gmail.com',        'GH'],
        ARRAY['Nana Yaa Gyamfi',    'nana.yaa.gyamfi@gmail.com',    'GH']
    ];
    u TEXT[];
    new_uid UUID;
    created_offset INTERVAL;
BEGIN
    FOREACH u SLICE 1 IN ARRAY users LOOP
        -- Generate a stable UUID from the email so re-runs are idempotent
        new_uid := gen_random_uuid();

        -- Vary created_at across the last 90 days
        created_offset := (random() * 90 || ' days')::INTERVAL;

        -- Insert into Supabase Auth
        INSERT INTO auth.users (
            id,
            email,
            encrypted_password,
            email_confirmed_at,
            raw_app_meta_data,
            raw_user_meta_data,
            created_at,
            updated_at,
            role,
            aud
        ) VALUES (
            new_uid,
            u[2],
            crypt('TestPass123!', gen_salt('bf')),
            NOW() - created_offset,
            '{"provider":"email","providers":["email"]}'::jsonb,
            jsonb_build_object('full_name', u[1]),
            NOW() - created_offset,
            NOW() - created_offset,
            'authenticated',
            'authenticated'
        )
        ON CONFLICT (email) DO NOTHING;

        -- Fetch the actual id (in case of conflict the UUID above was unused)
        SELECT id INTO new_uid FROM auth.users WHERE email = u[2];

        -- Insert matching user_profiles row
        INSERT INTO user_profiles (
            user_id,
            email,
            full_name,
            country,
            tier,
            role,
            subscription_status,
            daily_queries_used,
            created_at
        ) VALUES (
            new_uid,
            u[2],
            u[1],
            u[3],
            'free',
            'client',
            'active',
            0,
            NOW() - created_offset
        )
        ON CONFLICT (user_id) DO NOTHING;
    END LOOP;
END $$;

-- Verify
SELECT user_id, email, full_name, tier, created_at
FROM user_profiles
ORDER BY created_at DESC
LIMIT 25;
