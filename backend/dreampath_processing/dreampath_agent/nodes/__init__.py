# DreamPath Agent Nodes
# Each node is a separate module with its own logic and prompts
#
# Uses lazy loading to avoid circular imports with context_building.py

__all__ = [
    "orchestrator_node",
    "course_search_node",
    "plan_builder_node",
    "course_path_node",
    "modify_profile_node",
    "rebuild_course_path_node",
    "finalize_node",
]

# Lazy loading: nodes are imported only when accessed
def __getattr__(name: str):
    if name == "orchestrator_node":
        from .orchestrator import orchestrator_node
        return orchestrator_node
    elif name == "course_search_node":
        from .course_search import course_search_node
        return course_search_node
    elif name == "plan_builder_node":
        from .plan_builder import plan_builder_node
        return plan_builder_node
    elif name == "course_path_node":
        from .course_path import course_path_node
        return course_path_node
    elif name == "modify_profile_node":
        from .modify_profile import modify_profile_node
        return modify_profile_node
    elif name == "rebuild_course_path_node":
        from .rebuild import rebuild_course_path_node
        return rebuild_course_path_node
    elif name == "finalize_node":
        from .finalize import finalize_node
        return finalize_node
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
