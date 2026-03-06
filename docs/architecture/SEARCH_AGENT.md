
# Search Agent Architecture

The Search Agent (`dreampath_agent/search_agent/`) is a generalized LangGraph sub-agent for course and activity discovery. It uses a **strategy pattern** (`SearchStrategy` protocol) to support multiple domains. Integrated into the main DreamPath agent via `course_search_node` and `activity_search_node`.

**Integration Status:** ✅ Complete
- `course_search_node` and `activity_search_node` invoke search agent as a subgraph
- Supports multi-goal: each goal spawns a parallel search agent via `asyncio.gather()`
- Returns `final_summary` as the tool result for main agent context

**Directory Structure:**
```
search_agent/
├── graph.py                     # StateGraph: orchestrator → tool_executor → [orchestrator|summarize]
├── search_types.py              # SearchAgentState, SearchTask, OrchestratorResult, actions (generalized)
├── strategy.py                  # SearchStrategy protocol + get_strategy(domain) — course + activity
├── strategies/
│   ├── course_strategy.py       # CourseSearchStrategy (execute_search, prompts, rendering, QG singleton)
│   └── activity_strategy.py     # ActivitySearchStrategy (same pattern, activity QG singleton)
├── types/
│   ├── base.py                  # SearchParams, SearchResult, SearchOutput
│   ├── course_types.py          # CourseSearchParams, CourseSearchResult, CourseSearchOutput, enums
│   └── activity_types.py        # ActivitySearchParams, ActivitySearchResult, ActivitySearchOutput, enums
├── nodes/
│   ├── orchestrator.py          # SEARCH_ORCHESTRATOR_SKELETON + domain sections from strategy
│   ├── tool_executor.py         # Calls strategy.execute_search(description)
│   └── summarize.py             # Build FinalSearchSummary, delegates rendering to strategy
├── tools/
│   ├── course_search_client.py  # CourseSearchClient (imports from weaviate/course_service.py)
│   ├── activity_search_client.py # ActivitySearchClient (imports from weaviate/activity_service.py)
│   ├── query_generator.py       # CourseQueryGenerator (used by CourseSearchStrategy)
│   └── activity_query_generator.py # ActivityQueryGenerator (used by ActivitySearchStrategy)
├── context/
│   └── building.py              # build_search_context(), delegates rendering to strategy
├── evaluation/                  # Prompt optimization infra
├── utils/
│   ├── structured_output.py     # LLMManagedModel, llm_field, system_field
│   └── token_counting.py
└── tui.py                       # Interactive test harness (--domain flag)
```

**State Type** (`search_types.py`):
- `SearchAgentState` - Main state container
  - `goal`: Original search goal from user/parent agent
  - `domain`: "course" or "activity" — determines which strategy is used
  - `tasks`: List of `SearchTask` objects with task_id, description, status, top_results, search_executions
  - `search_trace`: All orchestrator decisions + tool results
  - `iteration`: Current iteration counter
  - `next_action`: Union[SearchAction, TaskUpdateAction, CompleteAction]

**Graph Flow:**
```
START → orchestrator → tool_executor → [orchestrator OR summarize] → END
```

**Testing the Search Agent Directly:**
```bash
cd backend/dreampath_processing/dreampath_agent/search_agent
uv run python tui.py                    # Course search (default)
uv run python tui.py --domain activity  # Activity search
```

**Integration Pattern:**
The search agent is invoked as a subgraph from `course_search_node`:
```python
# course_search_node passes writer through config for status updates
search_config = {**config, "configurable": {..., "writer": writer}}
final_state = await search_agent.ainvoke(search_state, search_config)
final_summary = final_state.get("final_summary")
```

**Status Emission for Subgraphs:**
Since the service uses `subgraphs=True` for streaming, search agent nodes must NOT return `messages`
(they would be streamed as intermediate text). Instead, status updates are emitted via `writer`:
```python
def _emit_status(config: RunnableConfig, reason: str):
    writer = config.get("configurable", {}).get("writer")
    if writer:
        status_event = AIMessage(
            content="",
            additional_kwargs={
                "event_type": "node_status",
                "node": "course_search",
                "status": "node_info",
                "next_node": "course_search",
                "reason": reason  # e.g., "Executing 3 searches"
            }
        )
        writer(status_event)
```

**Async Requirement for Real-Time Status Delivery:**
Status events emitted via `writer()` are pushed to a buffer but only delivered to the frontend when the event loop yields. **LLM calls must be async** (`await async_client.chat.completions.create(...)`) for status events to be delivered in real-time. Sync LLM calls block the event loop, causing status events to queue up and arrive late (or be immediately overwritten by subsequent events). See `context_building.py` for the async pattern using with `AsyncOpenAI` with native structured output.

**Parallelization Pattern (search_tools.py):**
Search tools are truly async to enable parallel execution with `asyncio.gather()`:
- **Query generation**: Uses `AsyncOpenAI` via `query_generator.generate_async()`
- **Weaviate search**: Uses `loop.run_in_executor()` since Weaviate client is sync

This enables:
1. Multiple searches within one tool_executor iteration to run in parallel
2. Multi-goal search: `course_search_node` and `activity_search_node` run parallel search agents via `asyncio.gather()`

**Key Files:**
- `tools/nodes/course_search.py` - Course search integration, invokes search agent subgraph
- `tools/nodes/activity_search.py` - Activity search integration, same pattern with domain="activity"
- `search_agent/strategy.py` - `get_strategy(domain)` returns domain-specific strategy
- `search_agent/nodes/*.py` - Search agent nodes (don't return `messages` to avoid streaming issues)