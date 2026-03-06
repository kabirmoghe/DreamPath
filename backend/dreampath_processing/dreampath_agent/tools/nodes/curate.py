"""
Curate node — writes orchestrator-curated recommendations to state.

The orchestrator in build mode (after search phases) reviews all search results
and produces curated lists as structured tool arguments. This node persists them
to state and formats a readable summary for context.
"""

from dreampath_processing.dreampath_agent.dreampath_types import (
    ActivityRec,
    CourseRec,
    DreamPathAgentState,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.schemas import CurateInput


async def curate_node(state: DreamPathAgentState, config) -> dict:
    tool_input: CurateInput = state.tool_input

    # Convert Pydantic schema models into state types
    curated_courses = [CourseRec(**c.model_dump()) for c in tool_input.courses]
    curated_activities = [ActivityRec(**a.model_dump()) for a in tool_input.activities]

    # Format readable summary
    lines = [f"Curated {len(curated_courses)} courses and {len(curated_activities)} activities."]
    lines.append("")
    lines.append(f"Coverage rationale: {tool_input.coverage_rationale}")

    if curated_courses:
        lines.append("")
        lines.append("Courses:")
        for c in curated_courses:
            aligned = ", ".join(sorted(c.aligned_parameters)) if c.aligned_parameters else "none"
            lines.append(f"  - {c.course_code} (aligned: {aligned})")

    if curated_activities:
        lines.append("")
        lines.append("Activities:")
        for a in curated_activities:
            aligned = ", ".join(sorted(a.aligned_parameters)) if a.aligned_parameters else "none"
            lines.append(f"  - {a.activity_slug} (aligned: {aligned})")

    summary = "\n".join(lines)

    tool_result = {
        "role": "tool",
        "content": {"name": "curate", "result": summary},
        "tool_call_id": state.pending_tool_call["tool_call_id"],
    }

    print(f"| -> Curate: {len(curated_courses)} courses, {len(curated_activities)} activities")

    return {
        "curated_courses": curated_courses,
        "curated_activities": curated_activities,
        "turn_messages": state.turn_messages + [tool_result],
        "messages": [dreampath_to_langchain(tool_result)],
    }
