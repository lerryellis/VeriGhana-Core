-- Add tax columns to payments table
-- Ghana GRA levies (Jan 2026): VAT 15% + NHIL 2.5% + GETFund 2.5% = 20% combined
ALTER TABLE payments
  ADD COLUMN IF NOT EXISTS tax_rate    NUMERIC(5,2)  DEFAULT 20,
  ADD COLUMN IF NOT EXISTS tax_amount  NUMERIC(10,2) DEFAULT 0;

-- Backfill existing rows: tax_amount = amount * 0.20 (amount is pre-tax subtotal)
UPDATE payments
SET tax_rate   = 20,
    tax_amount = ROUND(amount * 0.20, 2)
WHERE tax_amount = 0;
