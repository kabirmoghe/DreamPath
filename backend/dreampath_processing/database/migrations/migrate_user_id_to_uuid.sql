-- Migration: Convert user_id from INTEGER to TEXT for UUID support
-- Run this before switching to Supabase auth

BEGIN;

-- 1. student_profiles
ALTER TABLE student_profiles ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;

-- 2. course_paths
ALTER TABLE course_paths ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;

-- 3. course_path_agent_state
ALTER TABLE course_path_agent_state ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;

COMMIT;

-- Verify the changes
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name = 'user_id' AND table_schema = 'public';
