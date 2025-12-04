# DreamPath

An AI platform that equips students with the tools to achieve their goals and maximize career readiness by making the most of the college experience.

Outfitted with an agentic system that generates personalized, dynamic recommendations **grounded in successful alumni trajectories** and **real time data**, DreamPath guides students across 3 core college pillars:

1. **Courses** — the courses you take, within and outside of your major
2. **Clubs** — your on-campus extracurricular activities
3. **Career** – your personal alumni network

## Architecture

DreamPath makes use of *Compass*, an agentic advising system to provide a means of long-term communication with students to factor in changes to their interests, goals, and lives and make dynamic, adaptive recommendations for their bast path forward.

Compass takes action via tools (e.g, hybrid search, modifying students' profiles, building a modification plan, executing a full-scale upheaval of recommendations for things like career pivots) and subagents (e.g., dedicated mini-agent for executing 'CoursePath' modifications). Tool and agent execution / results, student data, and running summaries are dynamically engineered into agent nodes' context for greater awareness of relevant information and efficiency.

> *Stateless system implemented in LangGraph with custom context handling and hybrid vector search in Weaviate.*

![DreamPath Architecture](media/compass_architecture.svg)

## Infrastructure / Stack

### Backend
- **Framework**: FastAPI
- **Agent Orchestration**: LangGraph (custom node-based orchestration with handoff routing)
- **LLM Providers**: OpenAI, Anthropic
- **Vector Database**: Weaviate v4 (hybrid search with BM25 + embeddings)
- **Database**: PostgreSQL (Supabase transaction pooler)

> *Both service and Weaviate DB hosted in Fly.io, with PSQL DB in Supabase*

### Frontend 
- **Framework**: React + Vite
- **State Management**: React Query + Context API
- **Authentication**: Supabase Auth (JWT-based)
- **Styling**: Custom CSS with CSS variables (purple/blue gradient theme)
- **API Client**: Axios with streaming support

> *Hosted on Vercel*


## Project Structure

```
backend/
├── agents/                    # Agent service toolkit integration
├── dreampath_processing/      # Core DreamPath logic
│   ├── dreampath_agent/       # Main agent (stateless orchestrator)
│   │   └── agent_stateless.py # Active node implementations
│   ├── courses/               # Course path building & scheduling
│   │   └── coursepath_agent/  # Course path sub-agent
│   ├── database/              # PostgreSQL services & schema
│   └── modules/               # Student profiles, shared logic
├── service/                   # FastAPI service layer
└── memory/                    # LangGraph checkpointing (PostgreSQL)

frontend/
├── src/
│   ├── components/            # React components (Dashboard, Courses, etc.)
│   ├── contexts/              # AuthContext (Supabase auth)
│   ├── lib/                   # API client, utilities
│   └── styles/                # CSS (base, components, course path)
```

## Acknowledgments

This project incorporates components from the [Agent Service Toolkit](https://github.com/JoshuaC215/agent-service-toolkit) by Joshua Carroll. The toolkit provides infrastructure for productionizing LangGraph agents, including the FastAPI service layer, client SDK, and agent registry patterns.
