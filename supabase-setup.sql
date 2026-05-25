# AI Coach Feedback System — Supabase Schema
# Run this in Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql/new)

CREATE TABLE IF NOT EXISTS feedback (
  id BIGSERIAL PRIMARY KEY,
  overall INTEGER NOT NULL CHECK (overall >= 1 AND overall <= 5),
  difficulty TEXT DEFAULT '',
  length TEXT DEFAULT '',
  strengthen TEXT[] DEFAULT '{}',
  favorite TEXT DEFAULT '',
  best_day TEXT DEFAULT '',
  worst_day TEXT DEFAULT '',
  format TEXT[] DEFAULT '{}',
  role TEXT DEFAULT '',
  open_feedback TEXT DEFAULT '',
  submitted_at TIMESTAMPTZ DEFAULT NOW(),
  ip TEXT DEFAULT ''
);

-- Index for fast stats queries
CREATE INDEX IF NOT EXISTS idx_feedback_submitted_at ON feedback(submitted_at DESC);