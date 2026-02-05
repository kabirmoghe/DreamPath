-- ============================================================================
-- DreamPath Database Schema - Local Development (Docker PostgreSQL)
-- ============================================================================
--
-- This is the local-dev version of supabase_schema.sql.
-- Same tables and indexes, but WITHOUT Supabase-specific RLS policies
-- (which reference auth.uid() and don't exist in vanilla PostgreSQL).
--
-- For production (Supabase), use supabase_schema.sql instead.
--
-- LangGraph tables (checkpoints, checkpoint_blobs, checkpoint_writes)
-- are auto-created by the backend on startup via checkpointer.setup().
-- ============================================================================

-- ============================================================================
-- 1. STUDENT PROFILES
-- ============================================================================

CREATE TABLE IF NOT EXISTS student_profiles (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    profile_name TEXT,
    name TEXT NOT NULL,
    major TEXT,
    minors TEXT[],
    college_interests TEXT,
    post_grad_goals TEXT,
    career_goals TEXT,
    clubs TEXT[],
    career TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_student_profiles_user_id ON student_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_student_profiles_active ON student_profiles(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 2. COURSE PATHS
-- ============================================================================

CREATE TABLE IF NOT EXISTS course_paths (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    student_profile_id INTEGER NOT NULL,
    course_path_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    pending_approval BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_profile_id) REFERENCES student_profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_course_paths_user_id ON course_paths(user_id);
CREATE INDEX IF NOT EXISTS idx_course_paths_student_profile ON course_paths(student_profile_id);
CREATE INDEX IF NOT EXISTS idx_course_paths_active ON course_paths(user_id, is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 3. COURSE PATH AGENT STATE
-- ============================================================================

CREATE TABLE IF NOT EXISTS course_path_agent_state (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    pending_op_type TEXT,
    pending_op_data JSONB,
    trial_op_execution JSONB,
    missing_fields JSONB DEFAULT '[]'::JSONB,
    facts JSONB DEFAULT '{}'::JSONB,
    history TEXT DEFAULT '',
    recent_messages JSONB DEFAULT '[]'::JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_state_user_id ON course_path_agent_state(user_id);

-- ============================================================================
-- 4. THREADS
-- ============================================================================

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_threads_user_id ON threads(user_id);
CREATE INDEX IF NOT EXISTS idx_threads_last_message_at ON threads(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_threads_active ON threads(user_id, is_archived) WHERE is_archived = FALSE;
