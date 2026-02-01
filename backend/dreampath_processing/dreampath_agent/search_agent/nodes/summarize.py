"""
Summarize node for search agent.

Generates structured summary from completed tasks. The render function
can be called separately with different modes (full vs top_results_only).
"""

from dreampath_processing.dreampath_agent.dreampath_types import CourseSearchResult
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    FinalSearchSummary,
    SearchAgentState,
    SearchExecution,
    TaskSummary,
)
from langchain_core.runnables import RunnableConfig

# ============================================
# HELPER FUNCTIONS
# ============================================

def _get_unique_courses_from_executions(search_executions: list[SearchExecution]) -> list[CourseSearchResult]:
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
    description_max_len: int = 300,
    blurb_max_len: int = 200,
) -> str:
    """
    Render markdown summary from structured search data.

    Args:
        summary: The structured search summary
        verbosity: Level of detail (0=minimal, 1=medium, 2=full)
            - 0: Minimal - code, title, difficulty/value classifications, truncated target audience
            - 1: Medium - adds description and blurbs
            - 2: Full - complete summary with task status, search counts, other results
        description_max_len: Max chars for course description (verbosity 1)
        blurb_max_len: Max chars for blurbs (verbosity 1)

    Returns:
        Markdown-formatted string
    """
    if verbosity == 0:
        return _render_minimal(summary, blurb_max_len)
    elif verbosity == 1:
        return _render_medium(summary, description_max_len, blurb_max_len)
    else:
        return _render_full_summary(summary)


def _render_full_summary(summary: FinalSearchSummary) -> str:
    """Render full markdown summary with task status, search counts, etc."""

    lines = [
        f"# Search Results: {summary.goal}",
        "",
        f"**Status:** {summary.completed_tasks}/{summary.total_tasks} tasks completed in {summary.total_iterations} iterations",
        f"**Total Courses Found:** {summary.total_unique_courses} unique courses",
        "",
        "---",
        ""
    ]

    for task_summary in summary.task_summaries:
        status_emoji = {
            "complete": "✅",
            "failed": "❌",
            "in_progress": "🔄",
            "not_started": "⭕"
        }.get(task_summary.status, "❓")

        lines.append(f"## {status_emoji} Task {task_summary.task_id}: {task_summary.description}")
        lines.append("")
        lines.append(f"**Status:** {task_summary.status}")
        lines.append(f"**Searches:** {task_summary.search_attempt_count} attempts")
        lines.append(f"**Courses Found:** {task_summary.unique_courses_found} unique courses")
        lines.append("")

        if task_summary.top_results:
            lines.append("### Top Recommendations")
            lines.append("")

            # Show detailed info for top results
            top_course_codes = set(task_summary.top_results)
            top_courses = [c for c in task_summary.all_courses if c.course_code in top_course_codes]

            for course in top_courses:
                lines.append(f"<course>**{course.course_code}: {course.course_title}**")
                lines.append(f"- Department: {course.department}")
                if course.num_prereqs > 0:
                    lines.append(f"- Prerequisites: {course.prerequisites}")
                if course.course_url:
                    lines.append(f"- URL: {course.course_url}")
                if course.global_difficulty_classification:
                    lines.append(f"- Difficulty: {course.global_difficulty_classification}{' (Percentile: ' + str(round(course.global_difficulty_percentile, 2)) + ')' if course.global_difficulty_percentile else ''}")
                if course.global_value_classification:
                    lines.append(f"- Learning Value: {course.global_value_classification}{' (Percentile: ' + str(round(course.global_value_percentile, 2)) + ')' if course.global_value_percentile else ''}")

                if course.difficulty_blurb or course.learning_value_blurb or course.target_audience_blurb:
                    lines.append("- Students sentiment:")
                    if course.difficulty_blurb:
                        lines.append(f"\t→ About difficulty: {course.difficulty_blurb}")
                    if course.learning_value_blurb:
                        lines.append(f"\t→ About learning value: {course.learning_value_blurb}")
                    if course.target_audience_blurb:
                        lines.append(f"\t→ Target audience: {course.target_audience_blurb}")
                lines.append("</course>")

        # Show all other courses as a compact list (only remaining 10)
        other_courses = [c for c in task_summary.all_courses if c.course_code not in task_summary.top_results][:10]
        if other_courses:
            lines.append("### 📚 Other Results")
            lines.append("")
            for course in other_courses:
                lines.append(f"- **{course.course_code}**: {course.course_title} ({course.department})")
            lines.append("")

        if task_summary.orchestrator_notes:
            lines.append(f"**Notes:** {task_summary.orchestrator_notes}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _render_minimal(
    summary: FinalSearchSummary,
    blurb_max_len: int
) -> str:
    """
    Render minimal format - just essentials for quick synthesis.

    Format:
    - Course code + title
    - Difficulty + Value classifications (no blurbs)
    - Target audience (truncated)
    """
    lines = ["## Top Courses", ""]

    # Collect all top results across all tasks
    all_top_courses: list[CourseSearchResult] = []
    seen_codes = set()

    for task_summary in summary.task_summaries:
        top_codes = set(task_summary.top_results)
        for course in task_summary.all_courses:
            if course.course_code in top_codes and course.course_code not in seen_codes:
                seen_codes.add(course.course_code)
                all_top_courses.append(course)

    if not all_top_courses:
        lines.append("No courses found.")
        return "\n".join(lines)

    for course in all_top_courses:
        lines.append(f"**{course.course_code}: {course.course_title}**")

        # Difficulty + Value on one line
        diff = course.global_difficulty_classification or "Unknown"
        val = course.global_value_classification or "Unknown"
        lines.append(f"- Difficulty: {diff} | Learning Value: {val}")

        # Target Audience (truncated)
        if course.target_audience_blurb:
            lines.append(f"- Target Audience: '{_truncate(course.target_audience_blurb, blurb_max_len)}'")

        lines.append("")

    return "\n".join(lines)


def _render_medium(
    summary: FinalSearchSummary,
    description_max_len: int,
    blurb_max_len: int
) -> str:
    """
    Render medium format for synthesizer - top results with key info.

    Format:
    - Course code + title
    - Description (truncated)
    - Difficulty classification + blurb
    - Learning value classification + blurb
    - Target audience blurb
    """
    lines = ["## Top Courses", ""]

    # Collect all top results across all tasks
    all_top_courses: list[CourseSearchResult] = []
    seen_codes = set()

    for task_summary in summary.task_summaries:
        top_codes = set(task_summary.top_results)
        for course in task_summary.all_courses:
            if course.course_code in top_codes and course.course_code not in seen_codes:
                seen_codes.add(course.course_code)
                all_top_courses.append(course)

    if not all_top_courses:
        lines.append("No courses found.")
        return "\n".join(lines)

    for course in all_top_courses:
        lines.append(f"**{course.course_code}: {course.course_title}**")

        # Description (truncated)
        if course.description:
            lines.append(f"- {_truncate(course.description, description_max_len)}")

        # Difficulty
        if course.global_difficulty_classification:
            diff_line = f"- Difficulty: {course.global_difficulty_classification}"
            lines.append(diff_line)

        # Learning Value
        if course.global_value_classification:
            val_line = f"- Learning Value: {course.global_value_classification}"
            if course.learning_value_blurb:
                val_line += f" | '{course.learning_value_blurb}'"
            lines.append(val_line)

        # Target Audience
        if course.target_audience_blurb:
            lines.append(f"- Target Audience: '{course.target_audience_blurb}'")

        lines.append("")

    return "\n".join(lines)


# ============================================
# SUMMARIZE NODE
# ============================================

def summarize_node(state: SearchAgentState, config: RunnableConfig) -> dict:
    """
    Generate structured summary from search execution.

    Returns:
        State updates with structured_summary (FinalSearchSummary object)

    Note: Callers should use render_search_summary_markdown() to convert
    to markdown as needed, with appropriate mode (full vs top_results_only).
    """

    print(f"\n[SUMMARIZE] Generating summary for {len(state.tasks)} tasks...")

    # ============================================
    # BUILD STRUCTURED SUMMARY
    # ============================================
    task_summaries = []
    all_unique_courses_set = set()

    for task in state.tasks:
        # Calculate metrics
        total_found = sum(len(ex.output.results) for ex in task.search_executions)
        unique_courses = _get_unique_courses_from_executions(task.search_executions)
        unique_found = len(unique_courses)

        # Track global unique courses
        for course in unique_courses:
            all_unique_courses_set.add(course.course_code)

        task_summaries.append(TaskSummary(
            task_id=task.task_id,
            description=task.description,
            status=task.status,
            top_results=task.top_results,
            all_courses=unique_courses,
            search_attempt_count=len(task.search_executions),
            total_courses_found=total_found,
            unique_courses_found=unique_found,
            orchestrator_notes=task.orchestrator_notes or ""
        ))

    completed_count = sum(1 for t in state.tasks if t.status == "complete")
    failed_count = sum(1 for t in state.tasks if t.status == "failed")

    structured_summary = FinalSearchSummary(
        goal=state.goal,
        total_tasks=len(state.tasks),
        completed_tasks=completed_count,
        failed_tasks=failed_count,
        total_iterations=state.iteration,
        task_summaries=task_summaries,
        total_unique_courses=len(all_unique_courses_set)
    )

    print(f"  ✓ Summary complete: {completed_count}/{len(state.tasks)} tasks completed")
    print(f"  ✓ Total unique courses: {len(all_unique_courses_set)}")

    # ============================================
    # RETURN STATE UPDATES
    # ============================================
    # Return structured_summary object - callers render to markdown as needed
    return {
        "structured_summary": structured_summary,
    }
