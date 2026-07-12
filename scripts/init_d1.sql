-- Lumen D1 schema (database id: f7c44f86-9b4c-4e5e-9033-00fb12c44587)
-- Applied automatically by backend.d1.ensure_schema() on first query.
-- Manual: wrangler d1 execute <name> --remote --file=scripts/init_d1.sql

CREATE TABLE IF NOT EXISTS waitlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL COLLATE NOCASE,
  name TEXT,
  source TEXT DEFAULT 'composer',
  ip TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(email)
);
CREATE INDEX IF NOT EXISTS idx_waitlist_created ON waitlist(created_at);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE,
  created_at TEXT NOT NULL,
  UNIQUE(email)
);

CREATE TABLE IF NOT EXISTS render_jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  template TEXT NOT NULL,
  params_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  r2_prefix TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status);
