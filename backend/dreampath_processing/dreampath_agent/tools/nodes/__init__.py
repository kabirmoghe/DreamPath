# DreamPath Tool-Target Nodes
# Each node is a LangGraph node that implements a specific tool.
#
# Uses lazy loading to avoid circular imports with context_building.py

__all__ = [
    "course_search_node",
    "activity_search_node",
    "career_search_node",
    "course_path_node",
    "club_path_node",
    "modify_profile_node",
    "finalize_node",
    "change_mode_node",
    "complete_phase_node",
    "curate_node",
    "build_dreampath_node",
    "plan_build_node",
]

# Lazy loading: nodes are imported only when accessed
def __getattr__(name: str):
    if name == "course_search_node":
        from .course_search import course_search_node
        return course_search_node
    elif name == "activity_search_node":
        from .activity_search import activity_search_node
        return activity_search_node
    elif name == "career_search_node":
        from .career_search import career_search_node
        return career_search_node
    elif name == "course_path_node":
        from .course_path import course_path_node
        return course_path_node
    elif name == "club_path_node":
        from .club_path import club_path_node
        return club_path_node
    elif name == "modify_profile_node":
        from .modify_profile import modify_profile_node
        return modify_profile_node
    elif name == "finalize_node":
        from .finalize import finalize_node
        return finalize_node
    elif name == "change_mode_node":
        from .change_mode import change_mode_node
        return change_mode_node
    elif name == "complete_phase_node":
        from .complete_phase import complete_phase_node
        return complete_phase_node
    elif name == "curate_node":
        from .curate import curate_node
        return curate_node
    elif name == "build_dreampath_node":
        from .build_dreampath import build_dreampath_node
        return build_dreampath_node
    elif name == "plan_build_node":
        from .plan_build import plan_build_node
        return plan_build_node
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
