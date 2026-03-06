-- ============================================================================
-- CLUB PATHS
-- ============================================================================
-- Mirrors course_paths pattern: JSONB storage, is_active flag, FK to profile.

CREATE TABLE IF NOT EXISTS club_paths (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    student_profile_id INTEGER NOT NULL,
    club_path_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_profile_id) REFERENCES student_profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_club_paths_user_id ON club_paths(user_id);
CREATE INDEX IF NOT EXISTS idx_club_paths_student_profile ON club_paths(student_profile_id);
CREATE INDEX IF NOT EXISTS idx_club_paths_active ON club_paths(user_id, is_active) WHERE is_active = TRUE;
