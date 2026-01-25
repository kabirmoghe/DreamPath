"""
Legacy re-exports for backwards compatibility.
All node implementations have moved to dreampath_agent/nodes/.
All functionality has moved to dreampath_agent/graph.py.
"""

# Re-export nodes from new locations
# Re-export DreampathAgent class from graph.py
from dreampath_processing.dreampath_agent.graph import (
    DreampathAgent,
    clear_langchain_messages,
    log_langchain_messages,
    main,
)
from dreampath_processing.dreampath_agent.nodes import (
    course_path_node,
    course_search_node,
    finalize_node,
    modify_profile_node,
    orchestrator_node,
    plan_builder_node,
    rebuild_course_path_node,
)

__all__ = [
    # Nodes
    "orchestrator_node",
    "course_search_node",
    "plan_builder_node",
    "course_path_node",
    "modify_profile_node",
    "rebuild_course_path_node",
    "finalize_node",
    # Agent class
    "DreampathAgent",
    "main",
    "clear_langchain_messages",
    "log_langchain_messages",
]
