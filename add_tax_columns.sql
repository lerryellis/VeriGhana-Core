-- Add tax columns to payments table
ALTER TABLE payments
  ADD COLUMN IF NOT EXISTS tax_rate    NUMERIC(5,2)  DEFAULT 15,
  ADD COLUMN IF NOT EXISTS tax_amount  NUMERIC(10,2) DEFAULT 0;

-- Backfill existing rows: tax_amount = amount * 0.15 (amount was pre-tax)
UPDATE payments
SET tax_rate   = 15,
    tax_amount = ROUND(amount * 0.15, 2)
WHERE tax_amount = 0;
