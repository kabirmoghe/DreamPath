"""
Legacy re-exports for backwards compatibility.
All prompts have moved to dreampath_agent/nodes/prompts/.
"""

# Re-export MODIFY_PROFILE_SYS from modify_profile prompts
# (This was duplicated in the original build_prompts.py)
from dreampath_processing.dreampath_agent.nodes.prompts import (
    MODIFY_PROFILE_SYS,
    PARAMETER_COURSE_SEARCH_QUERIES_SYS,
    UPDATE_COURSE_RECOMMENDATIONS_SYS,
)

__all__ = [
    "PARAMETER_COURSE_SEARCH_QUERIES_SYS",
    "UPDATE_COURSE_RECOMMENDATIONS_SYS",
    "MODIFY_PROFILE_SYS",
]
