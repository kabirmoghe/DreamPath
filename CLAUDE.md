# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DreamPath is an AI platform that helps college students maximize their post-grad readiness with guidance that effectively prepares them for contemporary roles using insights from real market signals on phenomena like AI-induced disruption, crafting personalized recommendations for Courses and Clubs on campus. The system uses a multi-agent LangGraph architecture to provide dynamic, personalized recommendations.

## Production URLs

| Service | URL | Platform |
|---------|-----|----------|
| **Production App** | https://dreampath.live | Vercel |
| **Backend API** | https://dreampath-backend.fly.dev | Fly.io |
| **PostgreSQL** | aws-0-us-east-2.pooler.supabase.com:6543 | Supabase |
| **Weaviate** | dreampath-weaviate.internal (private) | Fly.io |

## Quick Start

```bash
uv sync                                  # Install deps (uv, not pip)
docker compose up -d                      # Start Weaviate + PostgreSQL
uv run python backend/setup_database.py   # First time only
uv run python backend/setup_weaviate.py   # Import course/activity data (if needed)
uv run python backend/run_service.py      # API at http://localhost:8080/docs
cd frontend && npm install && npm run dev  # Frontend at http://localhost:5173
```

### Other Run Modes
```bash
uv run python backend/run_agent.py                    # Direct agent (no service layer)
uv run streamlit run backend/streamlit_app.py          # Streamlit UI
uv run python backend/run_client.py                    # Client SDK demo
# Search agent test harness:
cd backend/dreampath_processing/dreampath_agent/search_agent
uv run python tui.py                                   # Course search
uv run python tui.py --domain activity                 # Activity search
```

### Environment (.env)
```bash
OPENAI_API_KEY=sk-...          # Required (Weaviate embeddings + LLM)
DATABASE_TYPE=postgres
POSTGRES_USER=kabirmoghe
POSTGRES_PASSWORD=postgres
POSTGRES_DB=dreampath
POSTGRES_HOST=localhost        # or aws-0-us-east-2.pooler.supabase.com for prod
POSTGRES_PORT=5432             # or 6543 for Supabase transaction pooler
WEAVIATE_HTTP_HOST=localhost
WEAVIATE_HTTP_PORT=8080
WEAVIATE_GRPC_HOST=localhost
WEAVIATE_GRPC_PORT=50051
```

## Project Structure

```
backend/
├── agents/dreampath_agent.py              # Service layer entry point
├── service/, client/, core/               # Agent-service-toolkit (imported OSS)
└── dreampath_processing/                  # ** Core DreamPath logic **
    ├── dreampath_agent/
    │   ├── graph.py                       # build_dreampath_graph() — single source of truth
    │   ├── dreampath_types.py             # DreamPathAgentState, BuildPlan, etc.
    │   ├── orchestrator.py                # Orchestrator node
    │   ├── context_building.py            # Context assembly (profile, CoursePath, ClubPath, build plan)
    │   ├── agent_stateless.py             # Legacy re-exports (backwards compat shim)
    │   ├── prompts/orchestrator.py        # Composable prompts: build_orchestrator_prompt(mode, name)
    │   ├── tools/
    │   │   ├── schemas.py                 # Tool input models
    │   │   ├── registry.py                # Tool→node mapping, get_openai_tools(mode)
    │   │   ├── executor.py                # Tool executor + phase guardrails
    │   │   └── nodes/                     # 13 node implementations (one file each)
    │   └── search_agent/                  # Generalized search subgraph
    │       ├── graph.py                   # orchestrator → tool_executor → [orchestrator|summarize]
    │       ├── strategy.py                # SearchStrategy protocol + get_strategy(domain)
    │       ├── strategies/                # CourseSearchStrategy, ActivitySearchStrategy
    │       ├── types/                     # Base + domain-specific (course, activity) types
    │       ├── nodes/                     # Search orchestrator, tool_executor, summarize
    │       └── tools/                     # Query generators + Weaviate search clients
    ├── courses/                           # Course path building, scheduling, CP sub-agent
    ├── clubs/modules/                     # Activity + ClubPath dataclasses
    ├── careers/                           # Career data (hardcoded JSON, SWE family only)
    ├── weaviate/                          # Weaviate services (course + activity singletons)
    └── database/                          # PostgreSQL: student_service, connection, serializers
```

**Dead code** (kept for reference in `tools/nodes/legacy/`): `plan_builder.py`, `rebuild_legacy.py`, `rebuild_static_search.py`

## Agent Architecture

### Graph Topology
`orchestrator → tool_executor → [target node] → orchestrator` (loop). Only exit: `finalize → END`.
Same topology for both modes — mode changes prompt, available tools, and flags, not graph structure.

### Nodes (13 total, in `tools/nodes/`)

| Node | File | Purpose |
|------|------|---------|
| orchestrator | `orchestrator.py` | Mode-aware routing via `build_orchestrator_prompt(mode)` |
| course_search | `course_search.py` | Search agent subgraph, multi-goal via `asyncio.gather()` |
| activity_search | `activity_search.py` | Same as course_search with `domain="activity"` |
| career_search | `career_search.py` | Direct JSON lookup (no LLM call) |
| course_path | `course_path.py` | CP sub-agent for add/remove/swap; normalizes confirm/reject |
| club_path | `club_path.py` | ClubPath add/remove/edit with HITL confirmation; edit validates `current_role` against `roles_exposed` |
| modify_profile | `modify_profile.py` | Deterministic Accept/Reject (no LLM); skips interrupt in build mode |
| change_mode | `change_mode.py` | Pure state mutation; summarizes results on build→advise exit |
| plan_build | `plan_build.py` | Sets per-phase guidance at build mode start |
| complete_phase | `complete_phase.py` | Marks phase complete, advances index |
| curate | `curate.py` | Writes curated course/activity lists to state |
| build_dreampath | `build_dreampath.py` | Deterministic scheduling from curated lists (no LLM) |
| finalize | `finalize.py` | Renders response to user with structured metadata |

### Dual-Modal Architecture
- **Advise mode** (default): Freeflowing brainstorming + incremental changes. 8 tools. `require_user_confirmation=True`.
- **Build mode**: Structured 9-phase plan. 12 tools (adds plan_build, curate, build_dreampath, complete_phase). `require_user_confirmation=False`.
- Phases: plan_build → update_profile → course_search → activity_search → curate → build_dreampath → reflect → refine → finish
- Phase guardrails: soft enforcement in `executor.py` via `_PHASE_TOOLS` — wrong-phase calls get developer warning, not hard block
- Build exit: finish phase calls `change_mode("advise")`; orchestrator sees build summary and presents results

For detailed node descriptions, ClubPath design, context building, legacy files, and CP sub-agent internals, see [`APP_ARCHITECTURE.md`](docs/architecture/APP_ARCHITECTURE.md). For search agent internals (strategy pattern, state types, status emission, async patterns), see [`SEARCH_AGENT.md`](docs/architecture/SEARCH_AGENT.md).

## Important Patterns

### Confirmation Flow (HITL)
Button-driven, deterministic — no LLM interprets confirmation.

**Frontend** (`ChatWindow.jsx`): Sends `"confirm"/"accept"/"reject"`, optionally `"action: <note>"`. Messages after structured cards are hidden (`hideInUI: true`).

**CP Operations** (`course_path_node`): Maps `'reject'` → `'cancel'` (sub-agent only understands CONFIRM/CANCEL). Note stays in `turn_messages` for orchestrator context.

**Profile Modification** (`modify_profile_node`): `startswith('accept')` check. Accept saves to DB; reject returns proposed changes so orchestrator knows what was rejected. Skipped entirely when `require_user_confirmation=False`.

### Student Profile
- `StudentProfile` dataclass in `modules/student_profile.py` (name, major, interests, goals, etc.)
- **Append-only history**: multiple rows per user_id, `is_active=TRUE` marks current. New records on modification (not UPDATE).

### Message Format
- `message_adapters.py` converts between DreamPath format (`{"role", "content": {"name", "result"}}`) and LangChain `BaseMessage`

### Memory/Checkpointing
- Local: SQLite (`checkpoints.db`). Production: PostgreSQL (Supabase). Set `DATABASE_TYPE` in `.env`.

## Frontend Architecture

**Stack:** React + Vite + TanStack Query + Supabase Auth. Colors: `#8A6BC1` (--dream-purple), `#6A4C93` (--dream-blue).

Key components: `Dashboard.jsx` (main UI + chat), `Courses.jsx` (course path visualization + detail modal), `Clubs.jsx` (club path visualization + redesigned detail modal), `CoursePathOperations.jsx` (CP cards with Confirm/Reject), `ClubPathOperations.jsx` (ClubPath cards with Confirm/Reject; supports add/remove/edit rendering), `ProfileUpdate.jsx` (profile cards with Accept/Reject), `InitLoadingOverlay.jsx` (onboarding loading with phase stepper), `api.js` (backend client + streaming). For full component tree, routing, auth flow, and data flow details, see [`FRONTEND_OVERVIEW.md`](docs/architecture/FRONTEND_OVERVIEW.md).

## Database

- **PostgreSQL schema** in `database/schema/` — student profiles, course paths, club paths (JSONB), careers (schema defined but NOT applied)
- **Services** in `database/` — `student_service.py` (CRUD), `connection.py` (asyncpg), `serializers.py`
- **Weaviate** — hybrid search (BM25 + vector) for courses and activities. Services in `weaviate/` (singletons).

## Code Quality
```bash
uv run ruff check --fix .    # Lint
uv run mypy backend/         # Type check (streamlit_app.py excluded)
uv run pytest --cov          # Test
```

## Deployment

Auto-deploy: push to `dev` branch → GitHub Actions deploys backend to Fly.io, Vercel deploys frontend.
Manual: `flyctl deploy -a dreampath-backend`. See `DEPLOYMENT_GUIDE.md` for details.

## Critical Requirements

### Python 3.12 Only
Python 3.13 causes import hangs with LangChain. Python 3.11 has compat issues.

### Prepared Statements Disabled (Supabase)
Supabase transaction pooler (pgbouncer) doesn't support prepared statements. Three locations:
1. `database/connection.py` → `statement_cache_size=0`
2. `memory/postgres.py` (saver) → `prepare_threshold=None`
3. `memory/postgres.py` (store) → `prepare_threshold=None`

### Supabase Connection
Must use transaction pooler: hostname `aws-0-us-east-2.pooler.supabase.com`, port `6543`, username `postgres.<project-ref>`. Direct connection (port 5432) does NOT work.

## Known Issues

**Profile interrupt text fallback** — If `extract_profile_update_metadata()` returns `{}`, fallback text may leak as user-facing message. Low risk since Accept/Reject buttons send clean strings. Monitor for recurrence.

**Empty slots in scheduling** — When no complementary courses available, scheduling leaves empty slots instead of adjusting term load. Likely in `courses/scheduling_helpers.py` or `schedule_modules/`. Low priority.

## What's Next

- **Frontend for dual-modal agent** — Build mode UI largely complete: mode pill, `change_mode` SSE events, ClubPath display (`Clubs.jsx`), club_path confirmation flow (`ClubPathOperations.jsx`), phase stepper in ChatWindow + InitLoadingOverlay (Onboarding) all implemented.
- **Execution persistence** — Track status across page navigation (see `docs/EXECUTION_PERSISTENCE.md`)
- **Ops** — Monitoring/alerts, security hardening, staging environment, performance optimization

## Post-Implementation Documentation
After completing a Plan Mode implementation, run `/update-docs` to review and update CLAUDE.md, deep-dive docs, and memory for consistency.

## Deep Dive Documentation

Modular deep dives live in `docs/architecture/`. Reference these for detailed context beyond what this file covers:

| Doc | What it covers |
|-----|----------------|
| [`APP_ARCHITECTURE.md`](docs/architecture/APP_ARCHITECTURE.md) | Full node descriptions (all 13), dual-modal design, ClubPath, context building, legacy files, CP sub-agent |
| [`SEARCH_AGENT.md`](docs/architecture/SEARCH_AGENT.md) | Search agent internals: strategy pattern, directory structure, state types, status emission, async patterns |
| [`FRONTEND_OVERVIEW.md`](docs/architecture/FRONTEND_OVERVIEW.md) | React component tree, routing, auth flow, API client, styling/colors, data flow |
| [`DATABASE_DESIGN.md`](docs/architecture/DATABASE_DESIGN.md) | PostgreSQL schema, services, connection architecture, Weaviate pipeline, career data |
| [`CRITICAL_DEPLOYMENT_NOTES.md`](docs/architecture/CRITICAL_DEPLOYMENT_NOTES.md) | Python 3.12 lock, prepared statements config, Supabase connection, profile append-only pattern |
| [`CURRENT_CONTEXT.md`](docs/architecture/CURRENT_CONTEXT.md) | Historical context: technical achievements, architectural decisions, completed milestones |

## Additional Docs
- `docs/DEPLOYMENT_GUIDE.md` — Full deployment docs, CI/CD, env vars, costs (~$12/mo)
- `docs/EXECUTION_PERSISTENCE.md` — Execution tracking design
- `docs/STREAMING_AND_DB_UPDATES.md` — SSE streaming + DB write timing
- `docs/TERM_INDEXING.md` — Course term/scheduling index system
