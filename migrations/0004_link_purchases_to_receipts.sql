ALTER TABLE purchases ADD COLUMN receipt_id TEXT;
CREATE INDEX IF NOT EXISTS idx_purchases_receipt_id ON purchases(receipt_id);
