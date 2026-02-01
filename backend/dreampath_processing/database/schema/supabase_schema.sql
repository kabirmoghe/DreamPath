-- ============================================================================
-- DreamPath Database Schema - Supabase PostgreSQL
-- ============================================================================
--
-- This schema creates all custom tables for the DreamPath application.
-- Uses TEXT for user_id to support Supabase UUID authentication.
--
-- IMPORTANT: This does NOT include LangGraph tables (checkpoints,
-- checkpoint_blobs, checkpoint_writes) - those are auto-created by
-- the backend when it starts up via checkpointer.setup()
--
-- Run this in Supabase SQL Editor for a fresh deployment.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. STUDENT PROFILES
-- ============================================================================
-- Stores student profile information (major, interests, goals, etc.)
-- Multiple profiles per user allowed (for tracking progression over time)

CREATE TABLE student_profiles (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,  -- Supabase auth UUID (can have multiple profiles)
    profile_name TEXT,  -- Optional nickname for profile (for tracking progression)
    name TEXT NOT NULL,
    major TEXT,
    minors TEXT[],  -- Array of minor programs
    college_interests TEXT,
    post_grad_goals TEXT,
    career_goals TEXT,
    clubs TEXT[],  -- Array of club names
    career TEXT[],  -- Array of companies/career interests
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX idx_student_profiles_user_id ON student_profiles(user_id);
CREATE INDEX idx_student_profiles_active ON student_profiles(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 2. COURSE PATHS
-- ============================================================================
-- Stores course path data (schedule of courses across terms)
-- Multiple course paths per user (for different scenarios/versions)

CREATE TABLE course_paths (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,  -- Supabase auth UUID
    student_profile_id INTEGER NOT NULL,
    course_path_data JSONB NOT NULL,  -- Full course path structure
    is_active BOOLEAN DEFAULT TRUE,
    pending_approval BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_profile_id) REFERENCES student_profiles(id) ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX idx_course_paths_user_id ON course_paths(user_id);
CREATE INDEX idx_course_paths_student_profile ON course_paths(student_profile_id);
CREATE INDEX idx_course_paths_active ON course_paths(user_id, is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 3. COURSE PATH AGENT STATE
-- ============================================================================
-- Stores state for the course path sub-agent
-- One state record per user (tracks pending operations, facts, history)

CREATE TABLE course_path_agent_state (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,  -- Supabase auth UUID
    pending_op_type TEXT,  -- Type of pending operation (add, remove, swap)
    pending_op_data JSONB,  -- Operation details
    trial_op_execution JSONB,  -- Trial execution results
    missing_fields JSONB DEFAULT '[]'::JSONB,  -- Missing fields for operation
    facts JSONB DEFAULT '{}'::JSONB,  -- Agent facts/memory
    history TEXT DEFAULT '',  -- Conversation history
    recent_messages JSONB DEFAULT '[]'::JSONB,  -- Recent messages
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX idx_agent_state_user_id ON course_path_agent_state(user_id);

-- ============================================================================
-- 4. THREADS
-- ============================================================================
-- Stores conversation thread metadata for the UI
-- The actual conversation data is in LangGraph's checkpoints table
-- Thread IDs match LangGraph's thread_id

CREATE TABLE threads (
    id TEXT PRIMARY KEY,  -- LangGraph thread ID
    user_id TEXT NOT NULL,  -- Supabase auth UUID
    name TEXT,  -- Optional custom thread name (null = auto-generated "Discussion #N")
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE
);

-- Indexes for fast lookups and sorting
CREATE INDEX idx_threads_user_id ON threads(user_id);
CREATE INDEX idx_threads_last_message_at ON threads(last_message_at DESC);
CREATE INDEX idx_threads_active ON threads(user_id, is_archived) WHERE is_archived = FALSE;

-- ============================================================================
-- 5. RLS
-- ============================================================================
-- Enable RLS on all custom tables to ensure users can only access their own data
-- Note: LangGraph tables (checkpoints, etc.) don't have user_id columns,
-- so we rely on application-level security via the threads table ownership

-- Enable RLS on all tables
ALTER TABLE student_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_path_agent_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE threads ENABLE ROW LEVEL SECURITY;

-- Student Profiles: Users can only access their own profile
CREATE POLICY "Users can only access their own profile"
  ON student_profiles FOR ALL
  USING (auth.uid()::TEXT = user_id);

-- Course Paths: Users can only access their own course paths
CREATE POLICY "Users can only access their own course paths"
  ON course_paths FOR ALL
  USING (auth.uid()::TEXT = user_id);

-- Course Path Agent State: Users can only access their own agent state
CREATE POLICY "Users can only access their own agent state"
  ON course_path_agent_state FOR ALL
  USING (auth.uid()::TEXT = user_id);

-- Threads: Users can only access their own threads
CREATE POLICY "Users can only access their own threads"
  ON threads FOR ALL
  USING (auth.uid()::TEXT = user_id);

-- ============================================================================
-- SCHEMA VERIFICATION
-- ============================================================================
-- Run this to verify all tables were created successfully

DO $$
DECLARE
    table_count INTEGER;
    rls_count INTEGER;
    policy_count INTEGER;
BEGIN
    -- Check tables created
    SELECT COUNT(*)
    INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('student_profiles', 'course_paths', 'course_path_agent_state', 'threads');

    RAISE NOTICE '✓ Created % custom tables', table_count;

    IF table_count = 4 THEN
        RAISE NOTICE '✓ All custom tables created successfully!';
        RAISE NOTICE '  - student_profiles';
        RAISE NOTICE '  - course_paths';
        RAISE NOTICE '  - course_path_agent_state';
        RAISE NOTICE '  - threads';
    ELSE
        RAISE WARNING 'Expected 4 tables, but created %', table_count;
    END IF;

    -- Check RLS enabled
    SELECT COUNT(*)
    INTO rls_count
    FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename IN ('student_profiles', 'course_paths', 'course_path_agent_state', 'threads')
    AND rowsecurity = true;

    RAISE NOTICE '';
    RAISE NOTICE '✓ RLS enabled on % tables', rls_count;

    -- Check policies created
    SELECT COUNT(*)
    INTO policy_count
    FROM pg_policies
    WHERE schemaname = 'public'
    AND tablename IN ('student_profiles', 'course_paths', 'course_path_agent_state', 'threads');

    RAISE NOTICE '✓ Created % RLS policies', policy_count;

    IF rls_count = 4 AND policy_count = 4 THEN
        RAISE NOTICE '✓ All security policies applied successfully!';
    ELSE
        RAISE WARNING 'Expected RLS on 4 tables with 4 policies';
    END IF;

    RAISE NOTICE '';
    RAISE NOTICE 'Note: LangGraph tables (checkpoints, checkpoint_blobs, checkpoint_writes)';
    RAISE NOTICE 'will be auto-created when the backend starts.';
    RAISE NOTICE 'These tables do NOT have RLS - security is enforced at application level.';
END $$;

COMMIT;

-- ============================================================================
-- NOTES FOR PROD
-- ============================================================================
--
-- 1. RLS - ALREADY APPLIED ✓
--    RLS is enabled on all 4 custom tables with policies that ensure
--    users can only access their own data via auth.uid()::TEXT = user_id
--
--    IMPORTANT: LangGraph tables (checkpoints, checkpoint_blobs, checkpoint_writes)
--    do NOT have RLS because they lack user_id columns. Security for these tables
--    is enforced at the application level through the threads table ownership check.
--
-- 2. Automatic Timestamps
--    Consider adding triggers to automatically update `updated_at`:
--
--    CREATE OR REPLACE FUNCTION update_updated_at_column()
--    RETURNS TRIGGER AS $$
--    BEGIN
--        NEW.updated_at = CURRENT_TIMESTAMP;
--        RETURN NEW;
--    END;
--    $$ language 'plpgsql';
--
--    CREATE TRIGGER update_student_profiles_updated_at
--      BEFORE UPDATE ON student_profiles
--      FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
--
--    (Repeat for other tables)
--
-- 3. Backup Strategy
--    Enable Point-in-Time Recovery in Supabase dashboard
--    Settings → Database → Backup & Recovery
--
-- 4. Connection Pooling
--    Use Supabase's connection pooler (port 6543) for production
--    to handle connection limits efficiently
--
-- ============================================================================
