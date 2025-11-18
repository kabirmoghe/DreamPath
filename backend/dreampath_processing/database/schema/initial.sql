-- Database schema for dreampath student profiles and course paths

-- User accounts (authentication layer)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    active_profile_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Student profiles (one user can have multiple profiles)
CREATE TABLE student_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,  -- FK to users
    profile_name VARCHAR(255),  -- e.g., "Fall 2024 Plan", "CS Track"
    name VARCHAR(255),  -- Student name
    major VARCHAR(255),
    college_interests TEXT,
    post_grad_goals TEXT,
    career_goals TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Course paths (multiple per user)
CREATE TABLE course_paths (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    student_profile_id INTEGER NOT NULL,
    course_path_data JSONB,
    is_active BOOLEAN DEFAULT true,
    pending_approval BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (student_profile_id) REFERENCES student_profiles(id) ON DELETE CASCADE
);

CREATE TABLE course_path_agent_state (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pending_op_type VARCHAR(255),
    pending_op_data JSONB,
    trial_op_execution JSONB,
    missing_fields JSONB DEFAULT '[]',
    facts JSONB DEFAULT '{}',
    history TEXT DEFAULT '',
    recent_messages JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id)
);

-- Add foreign key constraints
ALTER TABLE users
ADD CONSTRAINT fk_active_profile
FOREIGN KEY (active_profile_id) REFERENCES student_profiles(id) ON DELETE SET NULL;

-- Create index on course_paths(user_id, student_profile_id)
CREATE INDEX idx_agent_state_user_id ON course_path_agent_state(user_id);