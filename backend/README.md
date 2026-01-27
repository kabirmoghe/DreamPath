# Backend

FastAPI service with LangGraph-based agent for DreamPath backend processing.

## Structure

```
backend/
├── run_service.py              # Entry point - starts FastAPI server
├── run_agent.py                # Direct agent execution (testing)
├── setup_database.py           # Database schema setup
├── import_weaviate_data.py     # Course data import to Weaviate
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
│   │   └── data_retrieval/     # Weaviate service
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

## Quick Start

```bash
# Start infrastructure
docker compose up -d

# Setup database (first time)
python backend/setup_database.py

# Run server
python backend/run_service.py
# API at http://localhost:8080/docs
```
