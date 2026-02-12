"""
Custom tool executor for search agent.

Handles:
1. SearchAction - Execute searches in parallel, auto-update task.search_executions
2. TaskUpdateAction - Apply task updates deterministically
"""

import asyncio
import time

from dreampath_processing.dreampath_agent.search_agent.search_types import (
    CompleteAction,
    CourseSearchOutput,
    CourseSearchParams,
    SearchAction,
    SearchAgentState,
    SearchExecution,
    SearchTask,
    TaskSearch,
    TaskUpdateAction,
)
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig


def _emit_status(config: RunnableConfig, reason: str):
    """Emit a status message if writer is available in config."""
    writer = config.get("configurable", {}).get("writer")
    if writer:
        status_event = AIMessage(
            content="",
            additional_kwargs={
                "event_type": "node_status",
                "node": "course_search",
                "status": "node_info",
                "next_node": "course_search",
                "reason": reason
            }
        )
        try:
            writer(status_event)
        except Exception as e:
            print(f"  [TOOL] Error emitting status: {e}")

# ============================================
# SEARCH EXECUTION
# ============================================

async def _execute_single_search(task_search: TaskSearch, iteration: int) -> tuple[TaskSearch, tuple[CourseSearchParams, CourseSearchOutput] | Exception]:
    """
    Execute a single search (module_search or manual_search).

    Returns:
        (task_search, (params, result) | exception)
        Both search tools now return (params, result) tuple
    """
    try:
        if task_search.action_type == "module_search":
            from dreampath_processing.dreampath_agent.search_agent.tools import module_search

            print(f"    [SEARCH] Task {task_search.task_id} - module_search: {task_search.search_input[:60]}...")
            params, result = await module_search(task_search.search_input)
            return (task_search, (params, result))

        else:  # manual_search
            from dreampath_processing.dreampath_agent.search_agent.tools import manual_search

            search_desc = task_search.search_input.query or task_search.search_input.course_code or str(task_search.search_input)
            print(f"    [SEARCH] Task {task_search.task_id} - manual_search: {search_desc[:60]}...")
            params, result = await manual_search(task_search.search_input)
            return (task_search, (params, result))

    except Exception as e:
        print(f"    [ERROR] Task {task_search.task_id} search failed: {str(e)}")
        return (task_search, e)


def _build_tool_result_data(
    task_search: TaskSearch,
    task: SearchTask | None,
    params_and_result: tuple[CourseSearchParams, CourseSearchOutput] | Exception,
) -> dict:
    """
    Build structured data for a tool result message.

    Stores raw data so rendering (compact vs full) can happen at context-build time.
    """
    import json

    if isinstance(params_and_result, Exception):
        return {
            "error": str(params_and_result),
            "task_description": task.description if task else "",
            "search_description": "",
            "params": {},
            "courses": [],
        }

    params, result = params_and_result

    # module_search: search_input is the orchestrator's description string (query generator converts to params)
    # manual_search: search_input is CourseSearchParams (orchestrator sets params directly)
    search_description = task_search.search_input if task_search.action_type == "module_search" else ""

    courses = []
    for course in result.results[:25]:  # Cap at 25 per search
        courses.append({
            "code": course.course_code,
            "title": course.course_title,
            "department": course.department,
            "description": course.description or "",
            "difficulty": course.global_difficulty_classification,
            "value": course.global_value_classification,
            "num_prereqs": course.num_prereqs,
            "difficulty_blurb": course.difficulty_blurb or "",
            "learning_value_blurb": course.learning_value_blurb or "",
            "target_audience_blurb": course.target_audience_blurb or "",
        })

    params_dict = {k: v for k, v in params.model_dump().items() if v is not None}

    return {
        "task_description": task.description if task else "",
        "search_description": search_description,
        "action_type": task_search.action_type,
        "params": params_dict,
        "courses": courses,
    }


async def _execute_searches(
    state: SearchAgentState,
    action: SearchAction,
    config: RunnableConfig
) -> dict:
    """
    Execute multiple searches in parallel and AUTOMATICALLY update task results.

    Key behavior:
    - Each search has task_id from TaskSearch wrapper
    - Results automatically appended to corresponding task.search_executions
    - No separate TaskUpdateAction needed to merge results

    Returns:
        State updates dict
    """

    print(f"\n[TOOL EXECUTOR] Executing {len(action.searches)} searches in parallel...")
    _emit_status(config, f"Executing {len(action.searches)} search{'es' if len(action.searches) > 1 else ''}")

    # ============================================
    # 1. EXECUTE SEARCHES IN PARALLEL
    # ============================================
    search_tasks = [
        _execute_single_search(task_search, state.iteration)
        for task_search in action.searches
    ]

    results = await asyncio.gather(*search_tasks)

    # ============================================
    # 2. AUTO-UPDATE TASK.SEARCH_EXECUTIONS
    # ============================================
    updated_tasks = [task.model_copy(deep=True) for task in state.tasks]
    tool_messages = []

    for task_search, params_and_result in results:
        task_id = task_search.task_id

        # Find the task
        task = next((t for t in updated_tasks if t.task_id == task_id), None)

        if task and not isinstance(params_and_result, Exception):
            # Unpack params and result
            params, result = params_and_result

            # Create search execution record with actual params used
            execution = SearchExecution(
                params=params,
                output=result,
                timestamp=time.time(),
                iteration=state.iteration
            )

            # Append to task's search history
            task.search_executions.append(execution)
            task.last_updated_iteration = state.iteration

            # Update course index for course_code lookup
            for course in result.results:
                if course.course_code not in task.course_index:
                    task.course_index[course.course_code] = course

            total_courses = len(result.results)
            total_unique = len(_get_unique_courses_from_executions(task.search_executions))
            print(f"    → Task {task_id} now has {len(task.search_executions)} searches, {total_unique} unique courses")

        # Build structured data for rendering at context-build time
        tool_data = _build_tool_result_data(task_search, task, params_and_result)

        tool_msg = {
            "role": "tool",
            "args": {
                "name": task_search.action_type,
                "type": "result",
                "task_id": task_id,
            },
            "additional_kwargs": {
                "iteration": state.iteration,
                "timestamp": time.time(),
                **tool_data,
            }
        }

        tool_messages.append(tool_msg)

    # ============================================
    # 3. RETURN STATE UPDATES
    # ============================================
    # Note: Don't return messages here - they get streamed via subgraphs=True
    # and cause intermediate content to appear in frontend
    return {
        "tasks": updated_tasks,
        "search_trace": state.search_trace + tool_messages,
    }


def _get_unique_courses_from_executions(search_executions: list[SearchExecution]) -> list:
    """
    Get all unique courses from search executions (deduplicated by course_code).
    """
    all_courses = []
    for execution in search_executions:
        all_courses.extend(execution.output.results)

    # Deduplicate by course_code (keep first occurrence)
    seen_codes = set()
    unique_courses = []
    for course in all_courses:
        if course.course_code not in seen_codes:
            seen_codes.add(course.course_code)
            unique_courses.append(course)

    return unique_courses


# ============================================
# TASK UPDATE EXECUTION
# ============================================

async def _execute_task_updates(
    state: SearchAgentState,
    action: TaskUpdateAction,
    config: RunnableConfig
) -> dict:
    """
    Apply task updates deterministically (no LLM involved).

    Updates:
    - task.status (orchestrator's assessment)
    - task.top_results (orchestrator-curated course codes)
    - task.orchestrator_notes (guidance for next iteration)
    - task.last_updated_iteration (metadata)

    Note: task.search_executions updated automatically during search execution.
    """

    print(f"\n[TOOL EXECUTOR] Applying {len(action.task_updates)} task updates...")

    updated_tasks = [task.model_copy(deep=True) for task in state.tasks]

    # Handle initial task creation (iteration 0)
    if state.iteration == 0 and len(updated_tasks) == 0:
        print("  Creating initial tasks")
        for i, update in enumerate(action.task_updates, 1):
            new_task = SearchTask(
                task_id=i,
                description=update.orchestrator_notes,  # On iteration 0, notes contains description
                status=update.new_status,
                top_results=update.top_results,
                orchestrator_notes="",  # Clear after using for description
                search_executions=[],
                created_iteration=state.iteration,
                last_updated_iteration=state.iteration
            )
            updated_tasks.append(new_task)
            print(f"    Created Task {i}: {new_task.description[:60]}...")

        _emit_status(config, f"Created {len(updated_tasks)} search task{'s' if len(updated_tasks) > 1 else ''}")

    else:
        _emit_status(config, f"Updating {len(action.task_updates)} task{'s' if len(action.task_updates) > 1 else ''}")
        # Update existing tasks
        for update in action.task_updates:
            task = next((t for t in updated_tasks if t.task_id == update.task_id), None)

            if task:

                # Update LLM-managed fields
                old_status = task.status
                task.status = update.new_status
                task.top_results = update.top_results
                task.orchestrator_notes = update.orchestrator_notes
                task.last_updated_iteration = state.iteration

                # Calculate metrics for logging
                total_unique = len(_get_unique_courses_from_executions(task.search_executions))

                print(f"  Task {task.task_id}: {old_status} → {task.status}")
                print(f"    Search history: {len(task.search_executions)} searches, {total_unique} unique courses")
                print(f"    Top results: {len(task.top_results)} curated ({', '.join(task.top_results[:3])}...)")

    return {
        "tasks": updated_tasks,
    }


# ============================================
# MAIN TOOL EXECUTOR
# ============================================

async def tool_executor_node(state: SearchAgentState, config: RunnableConfig) -> dict:
    """
    Execute tools based on next_action type.

    Routes to:
    - SearchAction → _execute_searches()
    - TaskUpdateAction → _execute_task_updates()
    - CompleteAction → (no-op, router handles)

    When looping back to orchestrator (search/update actions), increments iteration counter.
    """

    next_action = state.next_action

    if isinstance(next_action, SearchAction):
        result = await _execute_searches(state, next_action, config)
        # Increment iteration when looping back to orchestrator
        result["iteration"] = state.iteration + 1
        return result

    elif isinstance(next_action, TaskUpdateAction):
        result = await _execute_task_updates(state, next_action, config)
        # Increment iteration when looping back to orchestrator
        result["iteration"] = state.iteration + 1
        return result

    elif isinstance(next_action, CompleteAction):
        # No execution needed, router will send to finalize
        return {}

    else:
        raise ValueError(f"Unknown action type: {type(next_action)}")
