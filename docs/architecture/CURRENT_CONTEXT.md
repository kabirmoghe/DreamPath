
# Historical Context & Decisions

> For current known issues and roadmap, see **Known Issues** and **What's Next** in [`CLAUDE.md`](../../CLAUDE.md). This doc captures historical context: what's been built, why, and key architectural decisions.

## Technical Achievements

- Integrated custom agent (`agent_stateless.py`) with agent-service-toolkit (FastAPI service layer)
- Implemented structured metadata for rich UI interactions (profile/course path cards)
- Solved Supabase transaction pooler compatibility (disabled prepared statements in 3 locations)
- Established append-only profile versioning pattern for user progression tracking
- Deployed full-stack application with CI/CD (GitHub Actions for backend, Vercel for frontend)
- Configured Fly.io private networking for secure backend-Weaviate communication
- Integrated search agent as subgraph with proper status emission pattern (avoiding message streaming issues)
- Generalized search agent with strategy pattern — supports course + activity domains with domain-specific query generators, prompts, and rendering
- Implemented true async parallelization for search tools (AsyncOpenAI + run_in_executor for Weaviate)
- Replaced LLM-based profile confirmation (`determine_user_confirmation`) with deterministic button-driven accept/reject
- Built dual-modal agent architecture (advise + build) with mode-aware tool registry, composable prompts, and soft phase guardrails
- Implemented ClubPath as first-class concept alongside CoursePath with DB persistence
- Cleaned up state management: worklist/cursor lifecycle (node-level reset + finalize safety net), tool call bookkeeping cleanup
- Added real-time mode pill updates via `mode_change` SSE events from `change_mode_node`
- Changed diff format to unambiguous `[removed]`/`[added]`/`[moved]` tags to prevent orchestrator misreading
- Added club edit capability with `roles_exposed` validation pipeline (Weaviate → Activity → ClubPath context → orchestrator prompt → node validation)
- Redesigned Clubs detail modal: alignment badges with SVG icons, structured status/at-a-glance sections, 2x2 mini tiles, neutral styling matching Courses aesthetic
- Enhanced ClubPathOperations card to render edit operations with per-field detail (membership_status, current_role, rank)

## Architectural Decision: Sub-Agent Integration

**Decision:** Option A - Single Graph (implemented)

Search agent is invoked as a subgraph within the main DreamPath agent:
- `course_search_node` calls `search_agent.ainvoke(search_state, search_config)`
- Status updates emitted via `writer` in config (not via `messages` return)
- `final_summary` returned to main agent for context

**Key Implementation Details:**
- Service uses `subgraphs=True` for streaming, so subgraph `messages` would leak to frontend
- Solution: Search agent nodes don't return `messages`, only `search_trace` for debugging
- Status updates use `_emit_status(config, reason)` pattern with `node_info` event type

**When to revisit (Option B — separate service):**
- Search latency becomes a bottleneck requiring horizontal scaling
- Need to reuse search agent from multiple different parent agents
- Want independent deployment/versioning of search logic

## Key Facts (stable)

- Agent nodes are in `dreampath_agent/tools/nodes/` (separate files per node, 13 nodes total)
- Graph is built in `dreampath_agent/graph.py` via `build_dreampath_graph()`
- `agent_stateless.py` is now a legacy re-export shim for backwards compatibility
- Orchestrator prompt is composable: `build_orchestrator_prompt(mode, student_name)` in `prompts/orchestrator.py`
- Mode-aware tool registry: 8 tools in advise, 12 in build (adds plan_build, curate, build_dreampath, complete_phase)
- Context order: DreamPath Context (primacy) → Thread → Current Turn (recency)
- Profile confirmation is deterministic: `startswith('accept')` check, no LLM call
- CP confirmation normalizes user response in `course_path_node` before calling `run_stateless()`
- `plan_builder` and `rebuild_course_path` are removed from graph (dead code, moved to `tools/nodes/legacy/`)
