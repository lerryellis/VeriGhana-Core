-- ── Live Chat Messages for Support Tickets ──────────────────
-- Enables real-time conversation between users and admin.
-- Run once in Supabase → SQL Editor.
-- Then enable Realtime on this table:
--   Supabase Dashboard → Database → Replication → ticket_messages → ON

CREATE TABLE IF NOT EXISTS ticket_messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id   UUID NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  sender_role TEXT NOT NULL CHECK (sender_role IN ('user', 'admin', 'staff')),
  sender_email TEXT NOT NULL,
  body        TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages (ticket_id, created_at);

-- RLS: users can read/write messages on their own tickets
ALTER TABLE ticket_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ticket_messages_user_read" ON ticket_messages
  FOR SELECT USING (
    sender_email = (SELECT email FROM auth.users WHERE id = auth.uid())
    OR EXISTS (
      SELECT 1 FROM support_tickets st
      WHERE st.id = ticket_messages.ticket_id
      AND st.email = (SELECT email FROM auth.users WHERE id = auth.uid())
    )
  );

CREATE POLICY "ticket_messages_user_insert" ON ticket_messages
  FOR INSERT WITH CHECK (
    sender_email = (SELECT email FROM auth.users WHERE id = auth.uid())
  );

-- Admin/staff can read and write all messages (use service key or add admin policy)
CREATE POLICY "ticket_messages_admin_all" ON ticket_messages
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_profiles up
      WHERE up.user_id = auth.uid()
      AND up.role IN ('admin', 'staff')
    )
  );
