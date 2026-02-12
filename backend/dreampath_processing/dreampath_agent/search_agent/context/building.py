import json

from dreampath_processing.dreampath_agent.context_building import calculate_token_count
from dreampath_processing.dreampath_agent.search_agent.context.templates import (
    SEARCH_MASTER_CONTEXT_TEMPLATE,
)
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchTask,
)


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

def _render_tool_result(msg: dict, compact: bool = False) -> list[str]:
    """
    Render a tool result message from structured data stored in additional_kwargs.

    Always shows: task description, action type (module/manual), full search params.
    compact=True: + course code:title list only
    compact=False: + full course details (description, blurbs, metrics)
    """
    kwargs = msg.get("additional_kwargs", {})
    args = msg.get("args", {})
    task_id = args.get("task_id", "?")
    action_type = kwargs.get("action_type", args.get("name", "search"))
    task_desc = kwargs.get("task_description", "")
    params = kwargs.get("params", {})
    courses = kwargs.get("courses", [])
    error = kwargs.get("error")

    lines = [f"<tool task_id='{task_id}' type='{action_type}'>"]

    if error:
        lines.append(f"Search failed: {error}")
        lines.append("</tool>")
        return lines

    lines.append(f"Task: {task_desc}")
    search_desc = kwargs.get("search_description", "")
    if search_desc:
        lines.append(f"Search description: {search_desc}")
    lines.append(f"Params: {json.dumps(params, ensure_ascii=False)}")

    if compact:
        if courses:
            course_list = "".join(f"\n - {c['code']}: {c['title']}" for c in courses)
            lines.append(f"Found {len(courses)} courses:{course_list}")
        else:
            lines.append("No courses found")
    else:
        if not courses:
            lines.append("No courses found")
        else:
            lines.append(f"Found {len(courses)} courses:")
            lines.append("")
            for i, c in enumerate(courses, 1):
                lines.append(f"{i}. {c['code']} - {c['title']}")
                lines.append(f"   Dept: {c['department']}, Diff: {c['difficulty']}, Value: {c['value']}, Prereqs: {c['num_prereqs']}")

                desc = c.get("description", "")
                if desc:
                    if len(desc) > 500:
                        desc = desc[:500] + "..."
                    lines.append(f"   Description: {desc}")

                if c.get("difficulty_blurb"):
                    lines.append(f"   Difficulty Blurb: {c['difficulty_blurb']}")
                if c.get("learning_value_blurb"):
                    lines.append(f"   Learning Value Blurb: {c['learning_value_blurb']}")
                if c.get("target_audience_blurb"):
                    lines.append(f"   Target Audience Blurb: {c['target_audience_blurb']}")

                lines.append("")

    lines.append("</tool>")
    return lines


def _render_search_trace_block(goal: str, search_trace: list[dict], current_iteration: int, recent_window: int = 2) -> str:
    """
    Render search trace block with compaction for older iterations.

    For iterations older than (current_iteration - recent_window):
      - Orchestrator decisions: rendered normally (already concise)
      - Tool results: compacted to course codes + titles only

    For recent iterations: full content rendered.
    """
    lines = ["<search_trace>"]
    lines.append(f"<goal>{goal}</goal>")

    if not search_trace:
        lines.append("<trace>empty - iteration 0</trace>")
    else:
        compact_cutoff = current_iteration - recent_window

        lines.append("<trace>")
        # Group messages by iteration
        current_iter = None
        for msg in search_trace:
            msg_iter = msg.get("additional_kwargs", {}).get("iteration", 0)

            # Start new iteration block if needed
            if msg_iter != current_iter:
                if current_iter is not None:
                    lines.append("</iteration>")
                lines.append(f"<iteration number='{msg_iter}'>")
                current_iter = msg_iter

            # Tool results: use unified renderer with compact flag based on age
            # Everything else (orchestrator decisions): render normally
            if msg.get("role") == "tool":
                is_old = msg_iter <= compact_cutoff
                lines.extend(_render_tool_result(msg, compact=is_old))
            else:
                lines.extend(_render_message_lines(msg))

        # Close last iteration block
        if current_iter is not None:
            lines.append("</iteration>")

        lines.append("</trace>")

    lines.append("</search_trace>")

    with open(f"search_trace_iteration_{current_iteration}.txt", "w") as f:
        f.write(f"========== Iteration {current_iteration} ==========\n")
        f.write("\n".join(lines))
        
    return "\n".join(lines)

def _render_task_state_block(goal: str, iteration: int, tasks: list[SearchTask]) -> str:
    """
    Render current task state (always fresh, never cached).

    Includes course title + truncated description for top_results courses
    so the orchestrator can cross-check relevance against the task description.
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
        lines.append("<search_attempts>")
        for ex in task.search_executions:
            lines.append("<search_execution>")
            lines.append("<query_params>")

            for key, value in ex.params.model_dump().items():
                lines.append(f"{key}: {value}")

            lines.append("</query_params>")
            lines.append("</search_execution>")

        lines.append("</search_attempts>")

        # 3. Show results: summary, top results with course details
        lines.append("<results>")

        num_searches = len(task.search_executions)
        total_courses_found = sum(len(ex.output.results) for ex in task.search_executions)
        lines.append(f"<summary>{num_searches} searches executed, {total_courses_found} total courses found</summary>")

        # Show top results with title + description for cross-checking
        if task.top_results:
            lines.append("<top_results>")
            for code in task.top_results:
                course = task.course_index.get(code)
                if course:
                    desc = course.description[:200] + "..." if course.description and len(course.description) > 200 else (course.description or "No description")
                    lines.append(f"- {code}: {course.course_title} | {desc}")
                else:
                    lines.append(f"- {code}")
            lines.append("</top_results>")
        else:
            lines.append("<top_results>None selected yet</top_results>")

        lines.append("</results>")

        if task.orchestrator_notes:
            lines.append(f"<orchestrator_notes>{task.orchestrator_notes}</orchestrator_notes>")

        lines.append("</task>")

    lines.append("</task_state>")
    return "\n".join(lines)

def build_search_context(state: SearchAgentState, prompt: str, config: dict={}) -> tuple[list[dict], dict]:
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

    # 1) Search Trace Block (all past actions, older iterations compacted)
    search_trace_block = _render_search_trace_block(goal=state.goal, search_trace=state.search_trace, current_iteration=state.iteration)

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