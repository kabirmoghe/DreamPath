"""
Custom tool executor for search agent.

Handles:
1. SearchAction - Execute searches in parallel, auto-update task.search_executions
2. TaskUpdateAction - Apply task updates deterministically
"""

from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchAction,
    TaskUpdateAction,
    CompleteAction,
    TaskSearch,
    SearchExecution,
    SearchTask,
    CourseSearchParams,
    CourseSearchOutput
)
from typing import List, Dict, Any, Optional
import asyncio
import time
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage


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

            print(f"    [SEARCH] Task {task_search.task_id} - manual_search: {task_search.search_input.query[:60]}...")
            params, result = await manual_search(task_search.search_input)
            return (task_search, (params, result))

    except Exception as e:
        print(f"    [ERROR] Task {task_search.task_id} search failed: {str(e)}")
        return (task_search, e)


def _format_search_result_content(
    task_search: TaskSearch,
    params_and_result: tuple[CourseSearchParams, CourseSearchOutput] | Exception
) -> str:
    """
    Format search result into human-readable content for context.
    Shows ALL courses and the params used (especially important for module_search).
    Node's responsibility to format content!
    """
    import json

    if isinstance(params_and_result, Exception):
        return f"Search failed: {str(params_and_result)}"

    params, result = params_and_result
    num_results = len(result.results)

    lines = []

    # Show search description for module_search (what the orchestrator asked for)
    if task_search.action_type == "module_search":
        lines.append(f"Search description: {task_search.search_input}")

    # Show params as compact JSON (what was actually executed)
    params_dict = {k: v for k, v in params.model_dump().items() if v is not None}
    lines.append(f"Params: {json.dumps(params_dict, ensure_ascii=False)}")
    lines.append("")

    # Show results (max 25 per search for context management)
    MAX_RESULTS_SHOWN = 25

    if num_results == 0:
        lines.append("No courses found")
    else:
        lines.append(f"Found {num_results} course{'s' if num_results != 1 else ''}:")
        lines.append("")

        # Show up to 25 results
        results_to_show = result.results[:MAX_RESULTS_SHOWN]
        for i, course in enumerate(results_to_show, 1):
            lines.append(f"{i}. {course.course_code} - {course.course_title}")
            lines.append(f"   Dept: {course.department}, Diff: {course.global_difficulty_classification}, Value: {course.global_value_classification}, Prereqs: {course.num_prereqs}")

            # Show first 500 chars of description
            desc = course.description[:500]
            if len(course.description) > 500:
                desc += "..."
            lines.append(f"   Description: {desc}")

            # Show complete blurbs if present (critical for decision making)
            if course.difficulty_blurb:
                lines.append(f"   Difficulty Blurb: {course.difficulty_blurb}")
            if course.learning_value_blurb:
                lines.append(f"   Learning Value Blurb: {course.learning_value_blurb}")
            if course.target_audience_blurb:
                lines.append(f"   Target Audience Blurb: {course.target_audience_blurb}")

            lines.append("")  # Blank line between courses

        # Indicate if there are more results
        if num_results > MAX_RESULTS_SHOWN:
            lines.append(f"... and {num_results - MAX_RESULTS_SHOWN} more courses not shown")

    return "\n".join(lines)


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

            total_courses = len(result.results)
            total_unique = len(_get_unique_courses_from_executions(task.search_executions))
            print(f"    → Task {task_id} now has {len(task.search_executions)} searches, {total_unique} unique courses")

        # Format tool message (node's responsibility!)
        # Pass the full params_and_result tuple (or exception) to formatter
        content = _format_search_result_content(task_search, params_and_result)

        # Extract num_results for metadata
        num_results = 0
        if not isinstance(params_and_result, Exception):
            _, result = params_and_result
            num_results = len(result.results)

        tool_msg = {
            "role": "tool",
            "args": {
                "name": task_search.action_type,
                "type": "result",
                "task_id": task_id,
            },
            "content": content,
            "additional_kwargs": {
                "iteration": state.iteration,
                "timestamp": time.time(),
                "num_results": num_results
            }
        }

        tool_messages.append(tool_msg)

    # ============================================
    # 3. RETURN STATE UPDATES
    # ============================================
    return {
        "tasks": updated_tasks,
        "search_trace": state.search_trace + tool_messages,
        "messages": [ToolMessage(content=msg["content"], tool_call_id=f"search_{i}") for i, msg in enumerate(tool_messages)]
    }


def _get_unique_courses_from_executions(search_executions: List[SearchExecution]) -> List:
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
        print("  Creating initial tasks...")
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

    else:
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
