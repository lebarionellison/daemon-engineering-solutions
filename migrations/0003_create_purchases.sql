CREATE TABLE IF NOT EXISTS purchases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  stripe_event_id TEXT NOT NULL UNIQUE,
  checkout_session_id TEXT NOT NULL UNIQUE,
  payment_intent_id TEXT,
  product_code TEXT NOT NULL CHECK (product_code IN ('ACE-HARDENED-9','ACE-PRO-TERRAFORM-19')),
  amount_total INTEGER NOT NULL,
  currency TEXT NOT NULL CHECK (currency = 'usd'),
  customer_email TEXT NOT NULL DEFAULT '',
  payment_status TEXT NOT NULL CHECK (payment_status IN ('paid')),
  fulfillment_status TEXT NOT NULL DEFAULT 'pending_secure_fulfillment'
    CHECK (fulfillment_status IN ('pending_secure_fulfillment','fulfilled','refunded','revoked')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  fulfilled_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_purchases_created_at ON purchases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_purchases_fulfillment_status ON purchases(fulfillment_status);
