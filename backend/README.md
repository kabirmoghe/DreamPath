# Backend

FastAPI service with LangGraph-based agent for DreamPath backend processing.

## Quick Start

```bash
# 1. Start infrastructure (from project root)
docker compose up -d

# 2. Setup PostgreSQL schema (first time only)
python backend/setup_database.py

# 3. Import Weaviate data (see "Weaviate Data Setup" below)
python backend/import_weaviate_data.py

# 4. Run server
python backend/run_service.py
# API at http://localhost:8080/docs
```

## Weaviate Data Setup

The course search functionality requires course data in Weaviate. Data files are **not in git** (too large).

### Prerequisites

- Docker running (`docker compose up -d`)
- OpenAI API key in `.env` (required for embeddings)

### Option A: Import from Export (Recommended)

If you have a `weaviate_export/` directory:

```bash
python backend/import_weaviate_data.py
```

This imports pre-computed embeddings - fast and no API costs.

### Option B: Ingest from CSV

If you have raw CSV data files in `dreampath_processing/courses/data/`:

```bash
# Ingest courses (generates embeddings via OpenAI - costs ~$2-5)
python backend/dreampath_processing/courses/data_retrieval/ingest_weaviate_courses_v4.py \
  backend/dreampath_processing/courses/data/all_courses_with_reviews.csv --recreate

# Ingest majors
python backend/dreampath_processing/courses/data_retrieval/ingest_weaviate_majors_v4.py \
  backend/dreampath_processing/courses/data/dartmouth_majors.csv --recreate
```

### Required Data Files

| File | Size | Purpose | How to Get |
|------|------|---------|------------|
| `weaviate_export/` | ~50MB | Pre-computed embeddings | Request from maintainer |
| **OR** | | | |
| `all_courses_with_reviews.csv` | ~315MB | Raw course data | Request from maintainer |
| `dartmouth_majors.csv` | ~11KB | Major definitions | Request from maintainer |

### Exporting Data (For Sharing)

To create an export:

```bash
python backend/export_weaviate_data.py
# Creates weaviate_export/ with course_data.json, major_data.json, and schemas
```

### Verify Weaviate Data

```bash
# Check Weaviate is ready
curl http://localhost:8080/v1/.well-known/ready

# Check collection counts (from Python)
python -c "
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
├── setup_database.py           # Database schema setup
├── import_weaviate_data.py     # Course data import to Weaviate
├── export_weaviate_data.py     # Export Weaviate data for sharing
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
python backend/run_agent.py

# Test search agent in isolation
cd backend/dreampath_processing/dreampath_agent/search_agent
python test_graph.py

# Run linting
ruff check backend/

# Run type checking
mypy backend/
```
