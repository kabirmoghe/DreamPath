# Backend

FastAPI service with LangGraph-based agent for DreamPath backend processing.

## Quick Start

```bash
# 1. Start infrastructure (from project root)
docker compose up -d

# 2. Setup PostgreSQL schema (first time only)
uv run python backend/setup_database.py

# 3. Setup Weaviate data (see "Weaviate Data Setup" below)
uv run python backend/setup_weaviate.py

# 4. Run server
uv run python backend/run_service.py
# API at http://localhost:8080/docs
```

## Weaviate Data Setup

The course search functionality requires course data in Weaviate.

### Prerequisites

- Docker running (`docker compose up -d`)
- OpenAI API key in `.env` (required for `text2vec-openai` embeddings)

### Local Development

```bash
# Create Course + Major collections and ingest from CSVs
uv run python backend/setup_weaviate.py

# To drop and recreate collections from scratch
uv run python backend/setup_weaviate.py --recreate
```

This reads from the CSV data files in `dreampath_processing/courses/data/` and generates
embeddings via OpenAI. Safe to re-run — skips ingestion if collections already have data.

### Required Data Files

| File | Location | Purpose | How to Get |
|------|----------|---------|------------|
| `all_courses_with_reviews.csv` | `courses/data/` | Course catalog + review data | Request from maintainer |
| `dartmouth_majors.csv` | `courses/data/` | Major definitions | In repo |

### Advanced: Individual Ingestion

The underlying ingest scripts can be run individually if needed:

```bash
# Courses only
uv run python backend/dreampath_processing/courses/data_retrieval/ingest_weaviate_courses_v4.py \
  backend/dreampath_processing/courses/data/all_courses_with_reviews.csv --recreate

# Majors only
uv run python backend/dreampath_processing/courses/data_retrieval/ingest_weaviate_majors_v4.py \
  backend/dreampath_processing/courses/data/dartmouth_majors.csv --recreate
```

### Verify Weaviate Data

```bash
# Check Weaviate is ready
curl http://localhost:8080/v1/.well-known/ready

# Check collection counts
uv run python -c "
import weaviate
client = weaviate.connect_to_local()
print('Courses:', client.collections.get('Course').aggregate.over_all(total_count=True))
print('Majors:', client.collections.get('Major').aggregate.over_all(total_count=True))
client.close()
"
```

## Structure

```
backend/
├── run_service.py              # Entry point - starts FastAPI server
├── run_agent.py                # Direct agent execution (testing)
├── setup_database.py           # PostgreSQL schema setup (local dev)
├── setup_weaviate.py           # Weaviate collection + data setup (local dev)
├── import_weaviate_data.py     # (Legacy) Cloud Weaviate import from JSON exports
├── export_weaviate_data.py     # (Legacy) Export Weaviate data to JSON
│
├── agents/                     # Agent registry and loading
│   └── dreampath_agent.py      # Service layer entry point
│
├── service/                    # FastAPI routes and middleware
│   ├── service.py              # Main API routes
│   └── coursepath_routes.py    # Course path endpoints
│
├── dreampath_processing/       # Core domain logic
│   ├── dreampath_agent/        # Main agent implementation
│   │   ├── graph.py            # LangGraph state graph builder
│   │   ├── dreampath_types.py  # State and type definitions
│   │   ├── nodes/              # Node implementations
│   │   │   ├── orchestrator.py
│   │   │   ├── course_search.py
│   │   │   ├── plan_builder.py
│   │   │   ├── course_path.py
│   │   │   ├── modify_profile.py
│   │   │   ├── rebuild.py
│   │   │   ├── finalize.py
│   │   │   └── prompts/        # Prompt templates
│   │   └── search_agent/       # Course search subagent
│   │       ├── graph.py
│   │       ├── nodes/
│   │       └── tools/
│   │
│   ├── courses/                # Course scheduling logic
│   │   ├── schedule_modules/   # CoursePath, Course classes
│   │   ├── coursepath_agent/   # Course operation sub-agent
│   │   └── data_retrieval/     # Weaviate ingestion & search
│   │       ├── ingest_weaviate_courses_v4.py
│   │       ├── ingest_weaviate_majors_v4.py
│   │       └── weaviate_course_service.py
│   │
│   ├── database/               # PostgreSQL integration
│   │   ├── connection.py       # Connection pooling
│   │   ├── student_service.py  # Profile CRUD
│   │   └── serializers.py      # DB ↔ Pydantic conversion
│   │
│   ├── clubs/                  # Club matching (future)
│   └── modules/                # Shared utilities
│
├── core/                       # Settings and LLM config
├── memory/                     # Checkpointer backends (SQLite, Postgres)
└── schema/                     # API request/response models
```

## Additional Commands

```bash
# Run agent directly (testing without API)
uv run python backend/run_agent.py

# Test search agent in isolation
cd backend/dreampath_processing/dreampath_agent/search_agent
uv run python test_graph.py

# Run linting
uv run ruff check backend/

# Run type checking
uv run mypy backend/
```
