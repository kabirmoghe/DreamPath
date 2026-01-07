from typing import List, Dict, Tuple
import json
from dreampath_processing.dreampath_agent.search_agent.search_types import SearchAgentState, SearchTask, SearchExecution, CourseSearchParams, CourseSearchResult, CourseSearchOutput
from dreampath_processing.dreampath_agent.search_agent.context.templates import SEARCH_MASTER_CONTEXT_TEMPLATE
from dreampath_processing.dreampath_agent.context_building import calculate_token_count

def _render_message_lines(message: dict) -> list[str]:
    """Render a message into a list of lines

    Assume message formatting with following examples:

    # Orchestrator action
    {
        "role": "orchestrator",
        "args": {
            "action": "search",
            "searches": [...],
        },
        "content": "Reasoning for the action"

    }

    # Tool execution result
    {
        "role": "tool",
        "args": {
            "name": "module_search",
            "type": "result",
        },
        "content": CourseSearchOutput(...)
    }

    # Task update
    {
        "role": "orchestrator",
        "args": {
            "action": "update_tasks",
            "task_updates": [...]
        },
        "content": "Reasoning for the update"
    }

    """

    lines = []

    role = message.get("role", "user")
    args = message.get("args", {})
    content = message.get("content", "")

    if isinstance(args, dict):
        tag_text = f"<{role}"
        for key, value in args.items():
            # Serialize complex types (list/dict) to avoid breaking XML-like format
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

def _render_search_trace_block(goal: str, search_trace: List[dict]) -> str:
    """
    Render search trace block (all past iterations).
    """
    lines = ["<search_trace>"]
    lines.append(f"<goal>{goal}</goal>")

    if not search_trace:
        lines.append("<trace>empty - iteration 0</trace>")
    else:
        lines.append("<trace>")
        # Group messages by iteration
        current_iter = None
        for msg in search_trace:
            msg_iter = msg.get("additional_kwargs", {}).get("iteration", 0)

            # Start new iteration block if needed
            if msg_iter != current_iter:
                if current_iter is not None:
                    lines.append(f"</iteration>")
                lines.append(f"<iteration number='{msg_iter}'>")
                current_iter = msg_iter

            # Delegate to _render_message_lines for each message
            lines.extend(_render_message_lines(msg))

        # Close last iteration block
        if current_iter is not None:
            lines.append(f"</iteration>")

        lines.append("</trace>")

    lines.append("</search_trace>")
    return "\n".join(lines)

def _render_task_state_block(goal: str, iteration: int, tasks: List[SearchTask]) -> str:
    """
    Render current task state (always fresh, never cached).

    Format:
    <task_state>
    <task id="1" status="complete">
      <description>Find easy ML courses</description>
      <search_attempts>3 searches executed, 12 total courses found</search_attempts>
      <top_results>COSC74, COSC75, COSC16</top_results>
      <notes>Task complete, good variety found</notes>
    </task>
    ...
    </task_state>
    """
    lines = ["<task_state>", f"<goal>{goal}</goal>", f"<iteration>{iteration}</iteration>"]

    # 1. Render each task
    for task in tasks:
        status_emoji = {
            "complete": "✓",
            "in_progress": "→",
            "failed": "✗",
            "not_started": "○"
        }.get(task.status, "?")

        lines.append(f"<task id='{task.task_id}' status='{task.status} {status_emoji}'>")
        lines.append(f"<description>{task.description}</description>")

        # 2. Show search execution history
        lines.append(f"<search_attempts>")
        for ex in task.search_executions:
            lines.append(f"<search_execution>")
            lines.append(f"<query_params>")

            for key, value in ex.params.model_dump().items():
                lines.append(f"{key}: {value}")

            lines.append(f"</query_params>")
            lines.append(f"</search_execution>")

        lines.append(f"</search_attempts>")

        # 3. Show results: summary, top results
        lines.append(f"<results>")

        num_searches = len(task.search_executions)
        total_courses_found = sum(len(ex.output.results) for ex in task.search_executions)
        lines.append(f"<summary>{num_searches} searches executed, {total_courses_found} total courses found</summary>")
    
        # Show orchestrator-curated top results
        if task.top_results:
            lines.append(f"<top_results>{', '.join(task.top_results)}</top_results>")
        else:
            lines.append(f"<top_results>None selected yet</top_results>")

        lines.append(f"</results>")

        if task.orchestrator_notes:
            lines.append(f"<orchestrator_notes>{task.orchestrator_notes}</orchestrator_notes>")

        lines.append(f"</task>")

    lines.append("</task_state>")
    return "\n".join(lines)

def build_search_context(state: SearchAgentState, prompt: str, config: dict={}) -> Tuple[List[Dict], Dict]:
    """
    Build complete context for orchestrator using two-block structure.

    Context Structure:
    1. Search Trace - All past orchestrator decisions + tool results
    2. Task State - Current task statuses (always fresh)

    Returns:
        (messages_array, state_updates)
    """

    # Init system prompt
    msgs = [{"role": "system", "content": prompt}]

    # Render context blocks

    # 1) Search Trace Block (all past actions)
    search_trace_block = _render_search_trace_block(goal=state.goal, search_trace=state.search_trace)

    # 2) Task State Block (live from system)
    task_state_block = _render_task_state_block(goal=state.goal, iteration=state.iteration, tasks=state.tasks)

    # 3) Combine all blocks
    conversation_msg = SEARCH_MASTER_CONTEXT_TEMPLATE.format(search_trace_block=search_trace_block, task_state_block=task_state_block)

    # Add master context to messages
    msgs.append({"role": "system", "content": conversation_msg})

    # Calculate token count for observability
    token_count = calculate_token_count(msgs, model="gpt-4o")

    token_updates = {
        "iteration_tokens": state.iteration_tokens + [token_count],
        "cumulative_tokens": state.cumulative_tokens + token_count
    }

    return msgs, token_updates