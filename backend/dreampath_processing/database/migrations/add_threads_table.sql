-- Migration: Add threads table for conversation thread metadata
-- This table stores UI-friendly metadata for LangGraph threads
-- The actual conversation data is in the checkpoints table

BEGIN;

CREATE TABLE threads (
    id TEXT PRIMARY KEY,  -- Thread ID from LangGraph (matches checkpoints.thread_id)
    user_id TEXT NOT NULL,  -- FK to student_profiles.user_id (Supabase UUID)
    name TEXT,  -- Optional custom thread name (null = use auto-generated label)
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE
);

-- Index for fast lookups by user_id
CREATE INDEX idx_threads_user_id ON threads(user_id);

-- Index for sorting by last_message_at
CREATE INDEX idx_threads_last_message_at ON threads(last_message_at DESC);

COMMIT;
