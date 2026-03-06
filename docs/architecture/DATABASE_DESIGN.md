
# Database Architecture

**PostgreSQL Schema** (`dreampath_processing/database/schema/`)
- Student profiles with major/minor/interests
- Course paths and scheduled courses
- Club paths (JSONB serialized ClubPath)
- Relationship tracking via foreign keys

**Services** (`dreampath_processing/database/`)
- `student_service.py` - CRUD operations for student data
- `connection.py` - Async connection pooling via `asyncpg` (with prepared statements disabled for Supabase)
- `serializers.py` - Convert between DB rows and Pydantic models

**Connection Architecture:**
- **Custom DB Connection** - Uses `asyncpg` for student profiles and course paths
- **LangGraph Checkpointing** - Uses `psycopg` for conversation persistence
- Both require `prepared statements disabled` for Supabase transaction pooler compatibility

### Course and Activity (Club) Data Pipeline

**Weaviate Vector Database**
- Stores course embeddings for semantic search
- Hybrid search combines BM25 and vector similarity
- Local dev: Configured via `compose.yml` with OpenAI embeddings
- Production: Deployed on Fly.io with private networking (`.internal` addresses)

**Weaviate Services** (`dreampath_processing/weaviate/`)
- `course_service.py` - `WeaviateCourseService` singleton for course hybrid search (BM25 + vector)
- `activity_service.py` - `WeaviateActivityService` singleton for activity hybrid search; `get_activity_by_slug()` fetches all metadata including `roles_exposed`
- `connection.py` - `connect_local_with_openai()` connection helper
- Supports filtering by department, course level, activity domain, selectivity, etc.
- Configurable alpha parameter for BM25/vector weighting

**Course Building** (`courses/build_major_course_path.py`)
- `build_course_path()` - Constructs valid course sequences
- Respects prerequisites and scheduling constraints
- Uses `CoursePath` data structure from `schedule_modules/`

### Career Data

**Career Data Module** (`dreampath_processing/careers/`)
- Hardcoded JSON data simulating future deep-research-agent output
- Currently covers 1 career family: **Software Engineering** with 4 roles (Full Stack, Backend, AI Engineer, FDE)
- Each role includes: spec (description), ~10 capabilities, and industry changes/trends
- `career_data.py` provides `get_swe_data()`, `get_role_by_slug()`, `match_query_to_roles()`
- `career_search_node` uses direct data lookup (no LLM call) — keyword matching against query
- DB schema defined in `database/schema/career_tables.sql` but **NOT yet applied** (tables not in local.sql or supabase_schema.sql)