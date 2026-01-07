from dreampath_processing.dreampath_agent.search_agent.search_types import SearchAgentState, SearchTask
from langchain_core.messages import AIMessage

def format_task_summary(tasks: list[SearchTask]) -> str:
    """Format task completion summary"""
    summary_lines = []

    for task in tasks:
        status_emoji = {
            "complete": "✓",
            "failed": "✗",
            "in progress": "→",
            "not started": "○"
        }.get(task.status, "?")

        num_results = len(task.results.results) if task.results else 0

        summary_lines.append(
            f"{status_emoji} Task {task.task_id}: {task.description} "
            f"({num_results} courses found)"
        )

    return "\n".join(summary_lines)

async def finalize_node(state: SearchAgentState, config) -> dict:
    """
    Aggregates results and creates final summary grouped by task.

    Called when all tasks are complete or max iterations reached.
    """

    print(f"Finalizing search results for goal: {state.goal}")
    print(f"Tasks: {state.tasks}")
    # Count task statuses
    completed = sum(1 for t in state.tasks if t.status == "complete")
    failed = sum(1 for t in state.tasks if t.status == "failed")
    in_progress = sum(1 for t in state.tasks if t.status == "in progress")

    # Count total unique courses across all tasks
    all_courses = []
    for task in state.tasks:
        if task.results and task.results.results:
            all_courses.extend(task.results.results)

    seen_codes = set()
    unique_count = 0
    for course in all_courses:
        if course.course_code not in seen_codes:
            unique_count += 1
            seen_codes.add(course.course_code)

    # Build summary
    summary_parts = [
        f"# Search Complete",
        f"",
        f"**Goal:** {state.goal}",
        f"",
        f"## Summary",
        f"- Total unique courses found: {unique_count}",
        f"- Tasks completed: {completed}/{len(state.tasks)}",
        f"- Tasks failed: {failed}",
        f"- Tasks in progress: {in_progress}",
        f"",
    ]

    # Group courses by task
    for task in state.tasks:
        status_emoji = {
            "complete": "✓",
            "failed": "✗",
            "in progress": "→",
            "not started": "○"
        }.get(task.status, "?")

        summary_parts.append(f"## {status_emoji} Task {task.task_id}: {task.description}")
        summary_parts.append(f"**Status:** {task.status}")
        summary_parts.append("")

        if task.results and task.results.results:
            # Show up to 20 courses per task
            courses = task.results.results[:10]
            summary_parts.append(f"**Courses Found ({len(task.results.results)} total):**")
            summary_parts.append("")

            for i, course in enumerate(courses, 1):
                summary_parts.append(f"{i}. **{course.course_code}** - {course.course_title}")
                summary_parts.append(f"   Department: {course.department}")
                summary_parts.append(f"   Description: {course.description[:300]}")
                summary_parts.append(f"   URL: {course.course_url}")

                if course.prerequisites:
                    summary_parts.append(f"   Prerequisites: {course.prerequisites}")

                if course.global_difficulty_classification:
                    summary_parts.append(f"   Global Difficulty: {course.global_difficulty_classification}")
                
                if course.dept_difficulty_classification:
                    summary_parts.append(f"   Department Difficulty: {course.dept_difficulty_classification}")

                if course.difficulty_blurb:
                    summary_parts.append(f"   Difficulty: {course.difficulty_blurb}")

                if course.global_value_classification:
                    summary_parts.append(f"   Global Learning Value: {course.global_value_classification}")

                if course.dept_value_classification:
                    summary_parts.append(f"   Department Learning Value: {course.dept_value_classification}")

                if course.learning_value_blurb:
                    summary_parts.append(f"   Learning Value: {course.learning_value_blurb}")

                if course.target_audience_blurb:
                    summary_parts.append(f"   Target Audience: {course.target_audience_blurb}")

                summary_parts.append("")

            if len(task.results.results) > 10:
                summary_parts.append(f"... and {len(task.results.results) - 10} more courses for this task")
                summary_parts.append("")
        else:
            summary_parts.append("No courses found for this task.")
            summary_parts.append("")

    final_summary = "\n".join(summary_parts)

    # Pretty print the messages
    for i, message in enumerate(state.messages):
        print()
        print(f"Message {i} | Type: {message.type}\nContent: {message.content}")

    return {
        "final_summary": final_summary,
        "messages": [AIMessage(content=final_summary)]
    }
