-- Career Data Tables
-- NOT YET APPLIED to local.sql or supabase_schema.sql.
-- These tables will replace the hardcoded JSON once the deep-research-agent
-- is ready to populate them dynamically.
--
-- To apply: add these to local.sql (for Docker dev) and supabase_schema.sql
-- (for production), then run setup_database.py or apply via Supabase migrations.

CREATE TABLE IF NOT EXISTS career_families (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,           -- e.g. 'swe'
    name TEXT NOT NULL,                  -- e.g. 'Software Engineering'
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    career_family_id INTEGER NOT NULL REFERENCES career_families(id),
    slug TEXT UNIQUE NOT NULL,           -- e.g. 'full-stack', 'backend'
    title TEXT NOT NULL,                 -- e.g. 'Full Stack Engineer'
    keywords TEXT[] DEFAULT '{}',        -- keyword array for matching
    data JSONB NOT NULL DEFAULT '{}',    -- full role data (spec, capabilities, changes)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for keyword matching
CREATE INDEX IF NOT EXISTS idx_roles_career_family ON roles(career_family_id);
CREATE INDEX IF NOT EXISTS idx_roles_slug ON roles(slug);

-- RLS notes for Supabase:
-- These tables are read-only for authenticated users.
-- ALTER TABLE career_families ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Career families are viewable by authenticated users"
--   ON career_families FOR SELECT TO authenticated USING (true);
-- CREATE POLICY "Roles are viewable by authenticated users"
--   ON roles FOR SELECT TO authenticated USING (true);
