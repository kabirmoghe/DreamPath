import json

from dreampath_processing.dreampath_agent.context_building import calculate_token_count
from dreampath_processing.dreampath_agent.search_agent.context.templates import (
    SEARCH_MASTER_CONTEXT_TEMPLATE,
)
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchTask,
)
from dreampath_processing.dreampath_agent.search_agent.strategy import get_strategy


def _render_message_lines(message: dict) -> list[str]:
    """Render a message into a list of lines."""

    lines = []

    role = message.get("role", "user")
    args = message.get("args", {})
    content = message.get("content", "")

    if isinstance(args, dict):
        tag_text = f"<{role}"
        for key, value in args.items():
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            tag_text += f" {key}=\"{value}\""
        tag_text += ">"
        lines.append(tag_text)
    else:
        lines.append(f"<{role}>")

    lines.append(f"{content}")
    lines.append(f"</{role}>")

    return lines

def _render_tool_result(msg: dict, compact: bool = False, *, strategy) -> list[str]:
    """
    Render a tool result message from structured data stored in additional_kwargs.

    Delegates per-result rendering to the strategy.
    """
    kwargs = msg.get("additional_kwargs", {})
    args = msg.get("args", {})
    task_id = args.get("task_id", "?")
    task_desc = kwargs.get("task_description", "")
    search_desc = kwargs.get("search_description", "")
    params = kwargs.get("params", {})
    items = kwargs.get("items", kwargs.get("courses", []))  # backwards compat
    error = kwargs.get("error")

    lines = [f"<tool task_id='{task_id}' type='search'>"]

    if error:
        lines.append(f"Search failed: {error}")
        lines.append("</tool>")
        return lines

    lines.append(f"Task: {task_desc}")
    if search_desc:
        lines.append(f"Search: {search_desc}")
    lines.append(f"Params: {json.dumps(params, ensure_ascii=False)}")

    if compact:
        if items:
            item_list = "".join(f"\n{strategy.render_result(item, compact=True)[0]}" for item in items)
            lines.append(f"Found {len(items)} results:{item_list}")
        else:
            lines.append("No results found")
    else:
        if not items:
            lines.append("No results found")
        else:
            lines.append(f"Found {len(items)} results:")
            lines.append("")
            for i, item in enumerate(items, 1):
                result_lines = strategy.render_result(item)
                lines.append(f"{i}. " + result_lines[0] if result_lines else f"{i}. ???")
                lines.extend(result_lines[1:])
                lines.append("")

    lines.append("</tool>")
    return lines


def _render_search_trace_block(goal: str, search_trace: list[dict], current_iteration: int, *, strategy, recent_window: int = 2) -> str:
    """
    Render search trace block with compaction for older iterations.
    """
    lines = ["<search_trace>"]
    lines.append(f"<goal>{goal}</goal>")

    if not search_trace:
        lines.append("<trace>empty - iteration 0</trace>")
    else:
        compact_cutoff = current_iteration - recent_window

        lines.append("<trace>")
        current_iter = None
        for msg in search_trace:
            msg_iter = msg.get("additional_kwargs", {}).get("iteration", 0)

            if msg_iter != current_iter:
                if current_iter is not None:
                    lines.append("</iteration>")
                lines.append(f"<iteration number='{msg_iter}'>")
                current_iter = msg_iter

            if msg.get("role") == "tool":
                is_old = msg_iter <= compact_cutoff
                lines.extend(_render_tool_result(msg, compact=is_old, strategy=strategy))
            else:
                lines.extend(_render_message_lines(msg))

        if current_iter is not None:
            lines.append("</iteration>")

        lines.append("</trace>")

    lines.append("</search_trace>")

    with open(f"search_trace_iteration_{current_iteration}.txt", "w") as f:
        f.write(f"========== Iteration {current_iteration} ==========\n")
        f.write("\n".join(lines))

    return "\n".join(lines)

def _render_task_state_block(goal: str, iteration: int, tasks: list[SearchTask], *, strategy) -> str:
    """
    Render current task state (always fresh, never cached).
    """
    lines = ["<task_state>", f"<goal>{goal}</goal>", f"<iteration>{iteration}</iteration>"]

    for task in tasks:
        status_emoji = {
            "complete": "✓",
            "partially_complete": "~",
            "in_progress": "→",
            "failed": "✗",
            "not_started": "○"
        }.get(task.status, "?")

        lines.append(f"<task id='{task.task_id}' status='{task.status} {status_emoji}'>")
        lines.append(f"<description>{task.description}</description>")

        # Search execution history
        lines.append("<search_attempts>")
        for ex in task.search_executions:
            lines.append("<search_execution>")
            lines.append("<query_params>")
            for key, value in ex.params.model_dump().items():
                lines.append(f"{key}: {value}")
            lines.append("</query_params>")
            lines.append("</search_execution>")
        lines.append("</search_attempts>")

        # Results summary and top results
        lines.append("<results>")
        num_searches = len(task.search_executions)
        total_found = sum(len(ex.output.results) for ex in task.search_executions)
        lines.append(f"<summary>{num_searches} searches executed, {total_found} total results found</summary>")

        if task.top_results:
            lines.append("<top_results>")
            for result_id in task.top_results:
                lines.append(strategy.render_task_top_result(result_id, task.result_index))
            lines.append("</top_results>")
        else:
            lines.append("<top_results>None selected yet</top_results>")

        lines.append("</results>")

        if task.orchestrator_notes:
            lines.append(f"<orchestrator_notes>{task.orchestrator_notes}</orchestrator_notes>")

        lines.append("</task>")

    lines.append("</task_state>")
    return "\n".join(lines)

def build_search_context(state: SearchAgentState, prompt: str, config: dict = {}) -> tuple[list[dict], dict]:
    """
    Build complete context for orchestrator using two-block structure.
    """
    strategy = get_strategy(state.domain)

    msgs = [{"role": "system", "content": prompt}]

    # 1) Search Trace Block
    search_trace_block = _render_search_trace_block(
        goal=state.goal, search_trace=state.search_trace,
        current_iteration=state.iteration, strategy=strategy,
    )

    # 2) Task State Block
    task_state_block = _render_task_state_block(
        goal=state.goal, iteration=state.iteration,
        tasks=state.tasks, strategy=strategy,
    )

    # 3) Combine
    conversation_msg = SEARCH_MASTER_CONTEXT_TEMPLATE.format(
        search_trace_block=search_trace_block, task_state_block=task_state_block,
    )
    msgs.append({"role": "system", "content": conversation_msg})

    # Token count for observability
    token_count = calculate_token_count(msgs, model="gpt-4o")
    token_updates = {
        "iteration_tokens": state.iteration_tokens + [token_count],
        "cumulative_tokens": state.cumulative_tokens + token_count
    }

    return msgs, token_updates
