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
    SearchAction,
    SearchAgentState,
    SearchExecution,
    SearchTask,
    TaskSearch,
    TaskUpdateAction,
)
from dreampath_processing.dreampath_agent.search_agent.strategy import get_strategy
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig


def _emit_status(config: RunnableConfig, reason: str, domain: str = "course"):
    """Emit a status message if writer is available in config."""
    writer = config.get("configurable", {}).get("writer")
    if writer:
        status_event = AIMessage(
            content="",
            additional_kwargs={
                "event_type": "node_status",
                "node": f"{domain}_search",
                "status": "node_info",
                "next_node": f"{domain}_search",
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

async def _execute_single_search(task_search: TaskSearch, strategy, verbose=False):
    """
    Execute a single search using the domain strategy.

    The strategy's execute_search takes a natural language description,
    runs its internal query generator to produce optimized params,
    then executes the search.

    Returns:
        (task_search, (params, result) | exception)
    """
    try:
        if verbose:
            print(f"    [SEARCH] Task {task_search.task_id} - search: {task_search.search_description[:60]}...")

        params_used, result = await strategy.execute_search(task_search.search_description)
        return (task_search, (params_used, result))

    except Exception as e:
        print(f"    [ERROR] Task {task_search.task_id} search failed: {str(e)}")
        return (task_search, e)


def _build_tool_result_data(
    search_description: str,
    task: SearchTask | None,
    params_and_result,
    strategy,
) -> dict:
    """
    Build structured data for a tool result message.

    Stores raw data so rendering (compact vs full) can happen at context-build time.
    """
    if isinstance(params_and_result, Exception):
        return {
            "error": str(params_and_result),
            "task_description": task.description if task else "",
            "search_description": search_description,
            "params": {},
            "items": [],
        }

    params, result = params_and_result

    items = []
    for r in result.results[:25]:  # Cap at 25 per search
        items.append(strategy.build_tool_result_entry(r))

    params_dict = {k: v for k, v in params.model_dump().items() if v is not None}

    return {
        "task_description": task.description if task else "",
        "search_description": search_description,
        "params": params_dict,
        "items": items,
    }


async def _execute_searches(
    state: SearchAgentState,
    action: SearchAction,
    config: RunnableConfig,
    verbose=False
) -> dict:
    """
    Execute multiple searches in parallel and AUTOMATICALLY update task results.
    """
    strategy = get_strategy(state.domain)

    if verbose:
        print(f"\n[TOOL EXECUTOR] Executing {len(action.searches)} searches in parallel...")
    _emit_status(config, f"Executing {len(action.searches)} search{'es' if len(action.searches) > 1 else ''}", state.domain)

    # ============================================
    # 1. EXECUTE SEARCHES IN PARALLEL
    # ============================================
    search_tasks = [
        _execute_single_search(task_search, strategy)
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
            params, result = params_and_result

            # Create search execution record
            execution = SearchExecution(
                params=params,
                output=result,
                timestamp=time.time(),
                iteration=state.iteration
            )

            task.search_executions.append(execution)
            task.last_updated_iteration = state.iteration

            # Update result index for ID lookup
            for r in result.results:
                result_id = strategy.get_result_id(r)
                if result_id not in task.result_index:
                    task.result_index[result_id] = r

            total_unique = len(_get_unique_results_from_executions(task.search_executions, strategy))

            if verbose:
                print(f"    → Task {task_id} now has {len(task.search_executions)} searches, {total_unique} unique results")

        # Build structured data for rendering at context-build time
        tool_data = _build_tool_result_data(task_search.search_description, task, params_and_result, strategy)

        tool_msg = {
            "role": "tool",
            "args": {
                "name": "search",
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
    return {
        "tasks": updated_tasks,
        "search_trace": state.search_trace + tool_messages,
    }


def _get_unique_results_from_executions(search_executions: list[SearchExecution], strategy) -> list:
    """
    Get all unique results from search executions (deduplicated by result ID).
    """
    all_results = []
    for execution in search_executions:
        all_results.extend(execution.output.results)

    seen_ids = set()
    unique_results = []
    for r in all_results:
        result_id = strategy.get_result_id(r)
        if result_id not in seen_ids:
            seen_ids.add(result_id)
            unique_results.append(r)

    return unique_results


# ============================================
# TASK UPDATE EXECUTION
# ============================================

async def _execute_task_updates(
    state: SearchAgentState,
    action: TaskUpdateAction,
    config: RunnableConfig,
    strategy,
    verbose=False
) -> dict:
    """
    Apply task updates deterministically (no LLM involved).
    """

    if verbose:
        print(f"\n[TOOL EXECUTOR] Applying {len(action.task_updates)} task updates...")

    updated_tasks = [task.model_copy(deep=True) for task in state.tasks]

    # Handle initial task creation (iteration 0)
    if state.iteration == 0 and len(updated_tasks) == 0:
        if verbose:
            print("  Creating initial tasks")
        for i, update in enumerate(action.task_updates, 1):
            new_task = SearchTask(
                task_id=i,
                description=update.orchestrator_notes,  # On iteration 0, notes contains description
                status=update.new_status,
                top_results=update.top_results,
                orchestrator_notes="",
                search_executions=[],
                created_iteration=state.iteration,
                last_updated_iteration=state.iteration
            )
            updated_tasks.append(new_task)

            if verbose:
                print(f"    Created Task {i}: {new_task.description[:60]}...")

        _emit_status(config, f"Created {len(updated_tasks)} search task{'s' if len(updated_tasks) > 1 else ''}", state.domain)

    else:
        _emit_status(config, f"Updating {len(action.task_updates)} task{'s' if len(action.task_updates) > 1 else ''}", state.domain)
        # Update existing tasks
        for update in action.task_updates:
            task = next((t for t in updated_tasks if t.task_id == update.task_id), None)

            if task:
                old_status = task.status
                task.status = update.new_status
                task.top_results = update.top_results
                task.orchestrator_notes = update.orchestrator_notes
                task.last_updated_iteration = state.iteration

                total_unique = len(_get_unique_results_from_executions(task.search_executions, strategy))

                if verbose:
                    print(f"  Task {task.task_id}: {old_status} → {task.status}")
                    print(f"    Search history: {len(task.search_executions)} searches, {total_unique} unique results")
                    print(f"    Top results: {len(task.top_results)} curated ({', '.join(task.top_results[:3])}...)")

    return {
        "tasks": updated_tasks,
    }

def _verify_task_completion(tasks: list[SearchTask]) -> list[int]:
    """Check if all tasks are complete, partially complete, or failed."""
    flagged_task_ids = []
    for task in tasks:
        if task.status not in ["complete", "partially_complete", "failed"]:
            flagged_task_ids.append(task.task_id)
    return flagged_task_ids

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
    strategy = get_strategy(state.domain)

    if isinstance(next_action, SearchAction):
        result = await _execute_searches(state, next_action, config)
        result["iteration"] = state.iteration + 1
        return result

    elif isinstance(next_action, TaskUpdateAction):
        result = await _execute_task_updates(state, next_action, config, strategy)
        result["iteration"] = state.iteration + 1
        return result

    elif isinstance(next_action, CompleteAction):
        flagged_task_ids = _verify_task_completion(state.tasks)
        if flagged_task_ids:
            warning_content = (f"Warning: CompleteAction called with tasks {', '.join([str(task_id) for task_id in flagged_task_ids])} not in valid terminal statuses (complete, partially complete, failed).",
                           "If you meant to complete the search, update task statuses and notes properly before calling CompleteAction.")
            warning_msg = {
                "role": "system",
                "content": warning_content,
            }

            return {
                "system_warning": True,
                "search_trace": state.search_trace + [warning_msg]
            }
        else:
            return {}

    else:
        raise ValueError(f"Unknown action type: {type(next_action)}")
