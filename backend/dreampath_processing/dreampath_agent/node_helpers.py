"""
Legacy re-exports for backwards compatibility.
All helper functions have moved to their respective node files in dreampath_agent/nodes/.
"""

# Re-export from orchestrator
# Re-export from course_path
from dreampath_processing.dreampath_agent.nodes.course_path import (
    format_aggregate_coursepath_agent_result,
)

# Re-export from course_search
from dreampath_processing.dreampath_agent.nodes.course_search import (
    determine_course_search_queries,
    format_course_search_output,
    format_course_search_result,
)

# Re-export from finalize
from dreampath_processing.dreampath_agent.nodes.finalize import (
    render_final_reply,
    render_final_reply_streaming,
)

# Re-export from modify_profile
from dreampath_processing.dreampath_agent.nodes.modify_profile import (
    determine_user_confirmation,
    format_modified_student_profile,
    modify_student_profile,
)
from dreampath_processing.dreampath_agent.nodes.orchestrator import (
    decide_next_route,
    format_orchestrator_decision,
)

# Re-export from plan_builder
from dreampath_processing.dreampath_agent.nodes.plan_builder import (
    build_operations_from_context_and_results,
    format_worklist,
)

# Re-export from rebuild
from dreampath_processing.dreampath_agent.nodes.rebuild import (
    format_rebuild_course_path_output,
)

__all__ = [
    # Orchestrator
    "decide_next_route",
    "format_orchestrator_decision",
    # Course search
    "determine_course_search_queries",
    "format_course_search_output",
    "format_course_search_result",
    # Plan builder
    "build_operations_from_context_and_results",
    "format_worklist",
    # Course path
    "format_aggregate_coursepath_agent_result",
    # Modify profile
    "modify_student_profile",
    "format_modified_student_profile",
    "determine_user_confirmation",
    # Rebuild
    "format_rebuild_course_path_output",
    # Finalize
    "render_final_reply",
    "render_final_reply_streaming",
]
