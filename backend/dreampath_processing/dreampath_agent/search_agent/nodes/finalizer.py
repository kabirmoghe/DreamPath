"""
Finalizer node for search agent.

Generates final summary from completed tasks in two formats:
1. Structured (for programmatic access)
2. Markdown (for display)
"""

from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchTask,
    SearchExecution
)
from dreampath_processing.dreampath_agent.dreampath_types import CourseSearchResult
from pydantic import BaseModel, Field
from typing import List
from langchain_core.messages import AIMessage


# ============================================
# STRUCTURED OUTPUT TYPES
# ============================================

class TaskSummary(BaseModel):
    """Structured summary for a single task"""
    task_id: int
    description: str
    status: str
    top_results: List[str] = Field(description="Orchestrator-curated course codes")
    all_courses: List[CourseSearchResult] = Field(description="All unique courses found")
    search_attempt_count: int
    total_courses_found: int  # Before deduplication across searches
    unique_courses_found: int  # After deduplication
    orchestrator_notes: str


class FinalSearchSummary(BaseModel):
    """Complete structured summary of search execution"""
    goal: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_iterations: int
    task_summaries: List[TaskSummary]
    total_unique_courses: int


# ============================================
# HELPER FUNCTIONS
# ============================================

def _get_unique_courses_from_executions(search_executions: List[SearchExecution]) -> List[CourseSearchResult]:
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


def _render_markdown_from_structured(summary: FinalSearchSummary) -> str:
    """Render markdown summary from structured data"""

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
            lines.append("### 🎯 Top Recommendations")
            lines.append("")

            # Show detailed info for top results
            top_course_codes = set(task_summary.top_results)
            top_courses = [c for c in task_summary.all_courses if c.course_code in top_course_codes]

            for course in top_courses:
                lines.append(f"**{course.course_code}: {course.course_title}**")
                lines.append(f"- Department: {course.department}")
                lines.append(f"- Difficulty: {course.global_difficulty_classification} (Percentile: {course.global_difficulty_percentile})")
                lines.append(f"- Learning Value: {course.global_value_classification} (Percentile: {course.global_value_percentile})")
                if course.num_prereqs > 0:
                    lines.append(f"- Prerequisites: {course.num_prereqs}")
                lines.append("")

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


# ============================================
# FINALIZER NODE
# ============================================

def finalize_node(state: SearchAgentState) -> dict:
    """
    Generate final summary in two formats:
    1. Structured (FinalSearchSummary) - For frontend programmatic access
    2. Markdown (string) - For display

    Returns:
        State updates with final_summary and structured_summary
    """

    print(f"\n[FINALIZER] Generating summary for {len(state.tasks)} tasks...")

    # ============================================
    # 1. BUILD STRUCTURED SUMMARY
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

    # ============================================
    # 2. RENDER MARKDOWN
    # ============================================
    markdown = _render_markdown_from_structured(structured_summary)

    print(f"  ✓ Summary complete: {completed_count}/{len(state.tasks)} tasks completed")
    print(f"  ✓ Total unique courses: {len(all_unique_courses_set)}")

    # ============================================
    # 3. RETURN STATE UPDATES
    # ============================================
    return {
        "final_summary": markdown,
        "messages": [AIMessage(content=markdown)]
    }