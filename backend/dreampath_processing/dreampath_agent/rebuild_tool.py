"""
Legacy re-exports for backwards compatibility.
Rebuild functionality has moved to dreampath_agent/nodes/rebuild.py.
"""

from dreampath_processing.dreampath_agent.nodes.rebuild import (
    CourseRecommendations,
    execute_rebuild_tool,
    format_deep_course_search_results,
    format_rebuild_course_path_output,
    format_recommended_courses,
)

__all__ = [
    "execute_rebuild_tool",
    "format_rebuild_course_path_output",
    "format_recommended_courses",
    "format_deep_course_search_results",
    "CourseRecommendations",
]
