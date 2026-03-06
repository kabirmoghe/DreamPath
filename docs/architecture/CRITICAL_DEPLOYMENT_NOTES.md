
# Critical Deployment Requirements

### Python Version Lock
**REQUIRED:** Python 3.12 (NOT 3.11, NOT 3.13)
- Python 3.13 causes import hangs with LangChain packages
- Python 3.11 may have compatibility issues
- Verify: `python --version` should show `3.12.x`

### Prepared Statements MUST Be Disabled
**Three locations require configuration for Supabase compatibility:**
1. `backend/dreampath_processing/database/connection.py` → `statement_cache_size=0`
2. `backend/memory/postgres.py` (saver) → `prepare_threshold=None`
3. `backend/memory/postgres.py` (store) → `prepare_threshold=None`

**Why:** Supabase transaction pooler uses pgbouncer in transaction mode, which doesn't support prepared statements.

### Supabase Connection Details
**Must use transaction pooler endpoint (NOT direct connection):**
- Hostname: `aws-0-us-east-2.pooler.supabase.com` (pooler format)
- Port: `6543` (transaction mode)
- Username: `postgres.<project-ref>` format (includes project ID)

**Direct connection does NOT work:**
- Port `5432` requires prepared statements (incompatible with pooler)

### Student Profile Architecture
**Design Pattern:** Append-only profile history
- Multiple `student_profiles` rows per `user_id` allowed (NO UNIQUE constraint)
- `is_active=TRUE` marks current profile
- Profile modifications create NEW records (not UPDATE existing)
- Enables tracking how student interests/goals evolve over time

**See `DEPLOYMENT_GUIDE.md` for complete deployment documentation including:**
- Production architecture and URLs
- CI/CD setup with GitHub Actions
- Environment variable configuration for all services
- Deployment commands and troubleshooting
- Cost breakdown (~$12/month total)

**Additional Architecture Documentation (`docs/`):**
- `EXECUTION_PERSISTENCE.md` - Execution tracking for visibility across page navigation/refresh
- `STREAMING_AND_DB_UPDATES.md` - SSE streaming architecture and database write timing
- `TERM_INDEXING.md` - Course term/scheduling index system
