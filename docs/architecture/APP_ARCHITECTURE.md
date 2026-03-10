
# App Architecture — Deep Dive

> For graph topology, node summary table, and dual-modal overview, see the **Agent Architecture** section in [`CLAUDE.md`](../../CLAUDE.md). This doc covers the details beyond that summary.

## State Management (`dreampath_types.py`)

- `DreamPathAgentState` — main state container
- Tracks conversation history, current turn messages, tool calling state, and worklist
- Maintains both LangChain messages (for service) and custom format (for orchestrator)
- **Dual-modal state**: `mode` (advise/build), `build_plan` (BuildPlan with 9 phases), `curated_courses`/`curated_activities` (set by curate node)
- **Club path state**: `club_worklist`, `club_cursor` (mirrors course worklist pattern)

### Worklist Lifecycle
Course/club path nodes use a cursor/worklist pattern for multi-operation execution. Critical cleanup points:
1. **Node-level reset**: When the aggregate result is formed (all ops processed), the node resets `worklist=[]` and `cursor=0`. This prevents stale state from leaking if the orchestrator calls the same tool again within the same turn.
2. **Finalize safety net**: `finalize_node` always resets `course_worklist`, `course_cursor`, `club_worklist`, `club_cursor`, `pending_tool_call`, `tool_name`, and `tool_input` to ensure a clean slate for the next turn.

### Diff Format
`operation_tools.py` uses explicit `[removed]`/`[added]`/`[moved]` prefixes in `summarize_diff()` to avoid ambiguity for the orchestrator (previously used `+`/`-`/`Moved` which could be misread).

## Node Details

Each node is a separate module in `dreampath_agent/tools/nodes/` with its own logic and prompts. Key implementation details not covered in CLAUDE.md:

- **orchestrator** — uses `build_orchestrator_prompt(mode)` to compose prompt from `ORCHESTRATOR_BASE` + mode-specific `TOOLS` + `EXAMPLES`/`PLAN` sections
- **course_search / activity_search** — support multi-goal (`goals: list[str]`); each goal spawns a parallel search agent via `asyncio.gather()`
- **course_path** — operations passed directly from orchestrator (no plan_builder intermediary); normalizes confirm/reject before calling CP sub-agent's `run_stateless()`
- **club_path** — ClubPath operations (add/remove/edit) with HITL confirmation. Edit supports `membership_status`, `current_role` (validated against `roles_exposed`), and `rank`. Null-handling: `None` = skip, `""` = clear (for `current_role`), value = set.
- **modify_profile** — `startswith('accept')` check; skips interrupt when `require_user_confirmation=False` (build mode)
- **change_mode** — generates `_summarize_build_results()` when exiting build mode; advise orchestrator sees summary in turn_messages; emits `mode_change` SSE event (AIMessage with `event_type: "mode_change"`) for real-time frontend pill update
- **curate** — writes curated lists to state from orchestrator's structured output
- **build_dreampath** — deterministic scheduling from curated lists; builds CoursePath + ClubPath without LLM call

**Prompts** (`dreampath_agent/prompts/`)
- `orchestrator.py` — composable sections; `build_orchestrator_prompt(mode, student_name)` helper
- `tools/nodes/prompts/` — per-node prompt files: `context.py` (master context templates), `course_search.py`, `finalize.py`, `modify_profile.py`, etc.

## ClubPath (`clubs/modules/`)

- `Activity` dataclass: activity_slug, display_name, metadata (mission_synth, domain, skills_exposed, career_alignment, roles_exposed, etc.)
- `ClubPath` dataclass: `recommendations: dict[str, Activity]` — ranked collection with add/remove/reorder methods; `__str__()` renders membership_status, current_role, and available roles for orchestrator context
- DB persistence: `student_service.py` (`save_club_path`, `load_club_path`); schema in `database/schema/club_path_tables.sql`
- Simple ranked list model (no scheduling/prerequisites unlike CoursePath)

## Context Building (`context_building.py`)

- Context order: DreamPath Context (profile, CoursePath, ClubPath, build plan) → Thread (summary + recent messages) → Current Turn Trace
- Persistent state placed early for primacy; current turn at end for recency
- `_render_build_plan_block()` visualizes build plan phases with current-phase marker
- Master templates in `tools/nodes/prompts/context.py`
- **Thread block rendering**: `_render_thread_block` wraps summary in `<summary>` tags and recent messages in `<recent_messages_prior_to_current_turn>` tags (XML structure, not plain text labels)

### Node Message Pattern
Nodes emit only `tool_result` to both `turn_messages` (DreamPath format) and `messages` (LangChain format). The orchestrator already records the tool call decision — nodes must not duplicate it. This applies uniformly across all nodes (course_search, activity_search, career_search, course_path, club_path, etc.).

**Known issue — HITL blank assistant message**: The interrupt flow injects an empty `<assistant></assistant>` tag into the context trace. TODO: replace with descriptive filler text like "[Presented to user for confirmation]".

## Course Path Sub-Agent (`courses/coursepath_agent/agent_v3.py`)

- `CoursePathAPIService` — handles add, remove, swap, view operations on course schedules
- Uses `CoursePathTools` for diff tracking and state management
- Maintains episodic memory with recent messages and summary
- Base `CoursePathAgent.run()` uses **exact string matching** (`text.strip().upper() == "CONFIRM"` / `"CANCEL"`) for confirmation routing — `course_path_node` must normalize responses before calling `run_stateless()`

## Legacy Files

- `agent_stateless.py` — re-exports from `nodes/` and `graph.py` for backwards compatibility
- `course_search_legacy.py` — old single-shot query generation (kept for reference)
- `legacy/rebuild_legacy.py`, `legacy/rebuild_static_search.py` — dead code (removed from graph); shared helpers moved to `build_dreampath.py`
- `legacy/plan_builder.py` — dead code (operations merged into `CoursePathInput.operations`)

## SSE Events for Frontend

Nodes emit `AIMessage` objects with `additional_kwargs` containing event metadata. These are streamed to the frontend via `subgraphs=True` streaming. Key event types:

| Event | Emitted by | Purpose |
|-------|-----------|---------|
| `mode_change` | `change_mode_node` | Real-time mode pill update (`mode: "advise"\|"build"`) |
| `phase_update` | `complete_phase_node` | Build phase progress (phase name, index, status) |
| `node_info` | search agent nodes | Status updates during search execution |