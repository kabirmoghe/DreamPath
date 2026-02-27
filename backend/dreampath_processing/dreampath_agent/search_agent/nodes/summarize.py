"""
Summarize node for search agent.

Generates structured summary from completed tasks. The render function
can be called separately with different verbosity levels.
"""

from dreampath_processing.dreampath_agent.search_agent.search_types import (
    MAX_ITERATIONS,
    FinalSearchSummary,
    SearchAgentState,
    SearchExecution,
    TaskSummary,
)
from dreampath_processing.dreampath_agent.search_agent.strategy import get_strategy
from langchain_core.runnables import RunnableConfig

# ============================================
# HELPER FUNCTIONS
# ============================================

def _get_unique_results_from_executions(search_executions: list[SearchExecution], strategy=None) -> list:
    """Get all unique results from search executions (deduplicated by result ID)."""
    all_results = []
    for execution in search_executions:
        all_results.extend(execution.output.results)

    seen_ids = set()
    unique_results = []
    for r in all_results:
        result_id = strategy.get_result_id(r) if strategy else r.id
        if result_id not in seen_ids:
            seen_ids.add(result_id)
            unique_results.append(r)

    return unique_results


def _truncate(text: str | None, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# ============================================
# RENDER FUNCTIONS (Exported)
# ============================================

def render_search_summary_markdown(
    summary: FinalSearchSummary,
    verbosity: int = 2,
    strategy=None,
) -> str:
    """
    Render markdown summary from structured search data.

    Args:
        summary: The structured search summary
        verbosity: Level of detail (0=minimal, 1=medium, 2=full)
        strategy: SearchStrategy for domain-specific rendering (resolved from summary.domain if None)
    """
    if strategy is None:
        strategy = get_strategy(summary.domain)

    if verbosity == 0:
        return _render_minimal_or_medium(summary, strategy, verbosity=0)
    elif verbosity == 1:
        return _render_minimal_or_medium(summary, strategy, verbosity=1)
    else:
        return _render_full_summary(summary, strategy)


def _render_full_summary(summary: FinalSearchSummary, strategy) -> str:
    """Render full markdown summary with task status, search counts, etc."""
    lines = [
        "# Search Results:",
        "",
        f"**Goal:** {summary.goal}",
        f"**Status:** in {summary.total_iterations} iterations:",
        f"  - {summary.completed_tasks}/{summary.total_tasks} tasks completed",
        f"  - {summary.partially_completed_tasks}/{summary.total_tasks} tasks partially completed",
        f"  - {summary.failed_tasks}/{summary.total_tasks} tasks failed",
        f"**Total Results Found:** {summary.total_unique_results} unique results",
    ]

    if summary.completion_reasoning:
        lines.append(f"**SearchAgent Final Notes:** {summary.completion_reasoning}")
        lines.append("")

    lines.extend(["---", ""])

    for task_summary in summary.task_summaries:
        status_emoji = {
            "complete": "✅",
            "partially_complete": "🟡",
            "failed": "❌",
            "in_progress": "🔄",
            "not_started": "⭕"
        }.get(task_summary.status, "❓")

        lines.append(f"## {status_emoji} Task {task_summary.task_id}: {task_summary.description}")
        lines.append("")
        lines.append(f"**Status:** {task_summary.status}")
        lines.append(f"**Searches:** {task_summary.search_attempt_count} attempts")
        lines.append(f"**Results Found:** {task_summary.unique_results_found} unique results")
        lines.append("")

        if task_summary.top_results:
            lines.append("### Top Recommendations")
            lines.append("")

            top_ids = set(task_summary.top_results)
            top_results = [r for r in task_summary.all_results if strategy.get_result_id(r) in top_ids]

            for result in top_results:
                lines.extend(strategy.render_result_for_summary(result, verbosity=2))

        # Other results (compact list, max 10)
        top_ids = set(task_summary.top_results)
        other_results = [r for r in task_summary.all_results if strategy.get_result_id(r) not in top_ids][:10]
        if other_results:
            lines.append("### Other Results")
            lines.append("")
            for r in other_results:
                lines.append(f"- **{r.id}**: {r.title}")
            lines.append("")

        if task_summary.orchestrator_notes:
            lines.append(f"**SearchAgent Task Notes:** {task_summary.orchestrator_notes}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _render_minimal_or_medium(summary: FinalSearchSummary, strategy, verbosity: int) -> str:
    """Render minimal or medium format — top results across all tasks."""
    lines = ["## Top Results", ""]

    # Collect all top results across all tasks (deduplicated)
    all_top_results = []
    seen_ids = set()

    for task_summary in summary.task_summaries:
        top_ids = set(task_summary.top_results)
        for result in task_summary.all_results:
            result_id = strategy.get_result_id(result)
            if result_id in top_ids and result_id not in seen_ids:
                seen_ids.add(result_id)
                all_top_results.append(result)

    if not all_top_results:
        lines.append("No results found.")
        return "\n".join(lines)

    for result in all_top_results:
        lines.extend(strategy.render_result_for_summary(result, verbosity=verbosity))

    return "\n".join(lines)


# ============================================
# SUMMARIZE NODE
# ============================================

def summarize_node(state: SearchAgentState, config: RunnableConfig, verbose=False) -> dict:
    """
    Generate structured summary from search execution.
    """
    strategy = get_strategy(state.domain)

    if verbose:
        print(f"\n[SUMMARIZE] Generating summary for {len(state.tasks)} tasks...")

    # ============================================
    # DETECT EXHAUSTION & CLEAN UP TASK STATUSES
    # ============================================
    exhausted = state.iteration >= MAX_ITERATIONS

    if exhausted and verbose:
        print(f"  ⚠️ Search exhausted (iteration {state.iteration} >= {MAX_ITERATIONS})")

    terminal_statuses = {"complete", "partially_complete", "failed"}
    for task in state.tasks:
        if task.status not in terminal_statuses:
            task.status = "failed"
            if exhausted:
                task.orchestrator_notes = (
                    f"Search exhausted after {state.iteration} iterations. "
                    f"Last reasoning: {state.latest_reasoning}"
                )
            else:
                task.orchestrator_notes = task.orchestrator_notes or "Task did not reach completion."

    # ============================================
    # BUILD STRUCTURED SUMMARY
    # ============================================
    task_summaries = []
    all_unique_ids = set()

    for task in state.tasks:
        total_found = sum(len(ex.output.results) for ex in task.search_executions)
        unique_results = _get_unique_results_from_executions(task.search_executions, strategy)
        unique_found = len(unique_results)

        for r in unique_results:
            all_unique_ids.add(strategy.get_result_id(r))

        task_summaries.append(TaskSummary(
            task_id=task.task_id,
            description=task.description,
            status=task.status,
            top_results=task.top_results,
            all_results=unique_results,
            search_attempt_count=len(task.search_executions),
            total_results_found=total_found,
            unique_results_found=unique_found,
            orchestrator_notes=task.orchestrator_notes or ""
        ))

    completed_count = sum(1 for t in state.tasks if t.status == "complete")
    partially_completed_count = sum(1 for t in state.tasks if t.status == "partially_complete")
    failed_count = sum(1 for t in state.tasks if t.status == "failed")

    if exhausted:
        completion_reasoning = (
            "SearchAgent reached maximum iterations without completing all tasks. "
            "Unfinished tasks have been marked as failed."
        )
    else:
        completion_reasoning = state.latest_reasoning

    structured_summary = FinalSearchSummary(
        goal=state.goal,
        domain=state.domain,
        total_tasks=len(state.tasks),
        completed_tasks=completed_count,
        partially_completed_tasks=partially_completed_count,
        failed_tasks=failed_count,
        total_iterations=state.iteration,
        task_summaries=task_summaries,
        total_unique_results=len(all_unique_ids),
        completion_reasoning=completion_reasoning,
    )

    if verbose:
        print(f"  ✓ Summary complete: {completed_count}/{len(state.tasks)} completed, "
              f"{partially_completed_count}/{len(state.tasks)} partial, "
              f"{failed_count}/{len(state.tasks)} failed")
        print(f"  ✓ Total unique results: {len(all_unique_ids)}")

    # Save structured_summary to file
    with open("structured_summary.json", "w") as f:
        f.write(structured_summary.model_dump_json())

    return {
        "structured_summary": structured_summary,
    }
