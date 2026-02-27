"""Interactive search agent test harness with live TUI display."""

import asyncio
import logging
import os
import time
import warnings

from dreampath_processing.dreampath_agent.search_agent.context.building import (
    _render_message_lines,
    _render_task_state_block,
    _render_tool_result,
)
from dreampath_processing.dreampath_agent.search_agent.graph import build_search_agent
from dreampath_processing.dreampath_agent.search_agent.nodes.summarize import (
    render_search_summary_markdown,
)
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchTask,
)
from dreampath_processing.dreampath_agent.search_agent.strategy import get_strategy
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Suppress unclosed transport warnings from async clients
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

# Suppress "Event loop is closed" errors from httpx/AsyncOpenAI cleanup.
# These are harmless — async clients try to close connections after the event loop
# is already shut down by asyncio.run(). The OS cleans up the sockets regardless.
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

def _suppress_async_cleanup_errors(loop, context):
    """Silently ignore 'Event loop is closed' errors from async client finalizers."""
    if "Event loop is closed" in str(context.get("exception", "")):
        return
    loop.default_exception_handler(context)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation", "outputs")

console = Console()

# ============================================
# TUI RENDERING
# ============================================

STATUS_STYLE = {
    "complete": ("bold green", "done"),
    "partially_complete": ("bold yellow", "partial"),
    "in_progress": ("bold cyan", "searching"),
    "failed": ("bold red", "failed"),
    "not_started": ("dim", "pending"),
}

TRACE_HEIGHT = 8


def _build_tasks_table(tasks: list[SearchTask], iteration: int, elapsed: float) -> Table:
    """Build a rich Table showing tasks with notes and top courses."""
    table = Table(
        title=f"Tasks  (iteration {iteration}, {elapsed:.1f}s)",
        title_style="bold",
        expand=True,
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Status", width=12)
    table.add_column("Description", ratio=2)
    table.add_column("Top Results", ratio=2)
    table.add_column("Notes", ratio=3)

    if not tasks:
        table.add_row("-", Text("waiting", style="dim"), "No tasks yet", "", "")
        return table

    for task in tasks:
        style, label = STATUS_STYLE.get(task.status, ("dim", task.status))
        status_text = Text(f"[{label}]", style=style)

        # Top results with course titles
        top_lines = []
        if task.top_results:
            for code in task.top_results:
                course = task.course_index.get(code)
                if course:
                    top_lines.append(f"[green]{code}[/green] {course.course_title}")
                else:
                    top_lines.append(f"[green]{code}[/green]")
        top_text = "\n".join(top_lines) if top_lines else "[dim]-[/dim]"

        # Notes
        notes = task.orchestrator_notes or ""

        table.add_row(
            str(task.task_id),
            status_text,
            task.description,
            top_text,
            f"[dim]{notes}[/dim]" if notes else "[dim]-[/dim]",
        )
    return table


def _build_trace_panel(search_trace: list[dict]) -> Panel:
    """Build a small fixed-height panel showing the most recent trace action."""
    if not search_trace:
        content = "[dim]Waiting for first orchestrator decision...[/dim]"
        return Panel(content, title="Trace", border_style="blue", height=TRACE_HEIGHT)

    lines: list[str] = []
    # Show only the last 2 messages (most recent action + result)
    for msg in search_trace[-2:]:
        role = msg.get("role", "?")
        if role == "tool":
            rendered = _render_tool_result(msg, compact=True)
            lines.extend(rendered)
        elif role == "system":
            content = msg.get("content", "")
            if isinstance(content, tuple):
                content = " ".join(str(c) for c in content)
            lines.append(f"[bold red]>> {content}[/bold red]")
        else:
            args = msg.get("args", {})
            action = args.get("action", role)
            content = str(msg.get("content", ""))
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"[bold]{action}:[/bold] {content}")

    # Cap lines to fit panel
    max_lines = TRACE_HEIGHT - 2
    if len(lines) > max_lines:
        lines = lines[-max_lines:]

    return Panel("\n".join(lines), title="Trace", border_style="blue", height=TRACE_HEIGHT)


def _build_final_panel(elapsed: float, iteration: int, tokens: int, completion_reasoning: str) -> Panel:
    """Build the final panel showing completion stats and orchestrator's overall reasoning."""
    lines = [f"[bold]Done in {elapsed:.1f}s[/bold] | {iteration} iterations | {tokens:,} tokens"]
    if completion_reasoning:
        lines.append("")
        lines.append(f"[italic]{completion_reasoning}[/italic]")

    return Panel("\n".join(lines), title="Complete", border_style="green")


def _build_display(
    goal: str,
    tasks: list[SearchTask],
    search_trace: list[dict],
    iteration: int,
    elapsed: float,
    finished: bool = False,
    tokens: int = 0,
    completion_reasoning: str = "",
) -> Group:
    """Build the full TUI: sticky tasks table + trace (or final reasoning)."""
    goal_panel = Panel(f"[bold]{goal}[/bold]", title="Search Goal", border_style="magenta")
    tasks_table = _build_tasks_table(tasks, iteration, elapsed)

    if finished:
        bottom = _build_final_panel(elapsed, iteration, tokens, completion_reasoning)
    else:
        bottom = _build_trace_panel(search_trace)

    return Group(goal_panel, tasks_table, bottom)


# ============================================
# FILE EXPORT (reuses task_test patterns)
# ============================================

def _render_full_trace(search_trace: list[dict], strategy=None) -> str:
    """Render the entire search trace with no compaction."""
    lines = []
    current_iter = None
    for msg in search_trace:
        msg_iter = msg.get("additional_kwargs", {}).get("iteration", 0)
        if msg_iter != current_iter:
            if current_iter is not None:
                lines.append("</iteration>")
            lines.append(f"<iteration number='{msg_iter}'>")
            current_iter = msg_iter

        if msg.get("role") == "tool":
            lines.extend(_render_tool_result(msg, compact=False, strategy=strategy))
        else:
            lines.extend(_render_message_lines(msg))

    if current_iter is not None:
        lines.append("</iteration>")
    return "\n".join(lines)


def _export_run(goal: str, final_state: dict, elapsed: float, run_id: str, strategy=None) -> str:
    """Export full run to file and return the file path."""
    sections = []

    sections.append(f"Goal: {goal}")
    sections.append(f"Time: {elapsed:.2f}s | Iterations: {final_state['iteration']} | Tasks: {len(final_state['tasks'])}")
    sections.append(f"Tokens per iteration: {final_state['iteration_tokens']}")
    sections.append(f"Cumulative tokens: {final_state['cumulative_tokens']}")
    sections.append("")

    sections.append("=" * 80)
    sections.append("SEARCH TRACE (full, uncompacted)")
    sections.append("=" * 80)
    sections.append(_render_full_trace(final_state['search_trace'], strategy=strategy))
    sections.append("")

    sections.append("=" * 80)
    sections.append("FINAL TASK STATE")
    sections.append("=" * 80)
    sections.append(_render_task_state_block(
        goal=goal,
        iteration=final_state['iteration'],
        tasks=final_state['tasks'],
        strategy=strategy,
    ))
    sections.append("")

    sections.append("=" * 80)
    sections.append("FINAL SUMMARY")
    sections.append("=" * 80)
    if final_state.get('structured_summary'):
        sections.append(render_search_summary_markdown(final_state['structured_summary']))
    elif final_state.get('final_summary'):
        sections.append(final_state['final_summary'])
    else:
        sections.append("(no summary produced)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{run_id}.txt")
    with open(filepath, "w") as f:
        f.write("\n".join(sections))

    return filepath


# ============================================
# MAIN EXECUTION
# ============================================

async def run_search(goal: str, graph, run_id: str):
    """Run the search agent with live TUI, export results."""

    # Suppress async cleanup errors for this run
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_suppress_async_cleanup_errors)

    initial_state = SearchAgentState(goal=goal)
    start_time = time.time()

    # Accumulated state for TUI
    tasks: list[SearchTask] = []
    search_trace: list[dict] = []
    iteration = 0
    final_state_snapshot: dict = {}

    with Live(
        _build_display(goal, tasks, search_trace, iteration, 0.0),
        console=console,
        refresh_per_second=4,
        screen=False,
        vertical_overflow="crop",
    ) as live:
        async for event in graph.astream(initial_state, stream_mode="updates"):
            for node_name, updates in event.items():
                if not isinstance(updates, dict):
                    continue

                if "tasks" in updates:
                    tasks = updates["tasks"]
                if "search_trace" in updates:
                    search_trace = updates["search_trace"]
                if "iteration" in updates:
                    iteration = updates["iteration"]

                # Capture everything for final export
                final_state_snapshot.update(updates)

            elapsed = time.time() - start_time
            live.update(_build_display(goal, tasks, search_trace, iteration, elapsed))

        # Final update: swap trace for completion reasoning
        elapsed = time.time() - start_time
        tokens = final_state_snapshot.get("cumulative_tokens", 0)
        completion_reasoning = final_state_snapshot.get("latest_reasoning", "")
        live.update(_build_display(goal, tasks, search_trace, iteration, elapsed, finished=True, tokens=tokens, completion_reasoning=completion_reasoning))

    elapsed = time.time() - start_time

    # Ensure we have all needed fields for export
    final_state_snapshot.setdefault("tasks", tasks)
    final_state_snapshot.setdefault("search_trace", search_trace)
    final_state_snapshot.setdefault("iteration", iteration)
    final_state_snapshot.setdefault("iteration_tokens", [])
    final_state_snapshot.setdefault("cumulative_tokens", 0)

    # Export full run
    strategy = get_strategy(initial_state.domain)
    filepath = _export_run(goal, final_state_snapshot, elapsed, run_id, strategy=strategy)
    console.print(f"[dim]Full trace exported to {filepath}[/dim]")

    # Export summary markdown
    if final_state_snapshot.get("structured_summary"):
        summary_md = render_search_summary_markdown(final_state_snapshot["structured_summary"])
        summary_path = os.path.join(OUTPUT_DIR, f"{run_id}_summary.md")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(summary_path, "w") as f:
            f.write(summary_md)
        console.print(f"[dim]Summary exported to {summary_path}[/dim]")

    return final_state_snapshot


if __name__ == "__main__":
    console.print("[bold magenta]Search Agent Test Harness[/bold magenta]")
    console.print("[dim]Type a search goal and watch the agent work. Type 'exit' to quit.[/dim]\n")

    graph = build_search_agent()
    run_counter = 0

    while True:
        try:
            goal = console.input("[bold]Search goal:[/bold] ")
        except (EOFError, KeyboardInterrupt):
            break
        if goal.strip().lower() in ("exit", "quit", "q"):
            break
        if not goal.strip():
            continue

        run_counter += 1
        run_id = f"interactive_{run_counter}"
        asyncio.run(run_search(goal.strip(), graph, run_id))
        console.print()
