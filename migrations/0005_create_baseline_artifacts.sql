-- Immutable, SHA-256-addressed clean artifacts used by Checkpoint 3 recovery review.
-- Artifacts are stored in D1 (not KV); writes are insert-only by digest.
CREATE TABLE IF NOT EXISTS baseline_artifacts (
  artifact_sha256 TEXT PRIMARY KEY CHECK (length(artifact_sha256) = 64),
  artifact_text TEXT NOT NULL,
  source_receipt_id TEXT NOT NULL REFERENCES receipts(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_baseline_artifacts_source_receipt
  ON baseline_artifacts(source_receipt_id);
