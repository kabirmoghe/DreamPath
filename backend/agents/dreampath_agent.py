"""DreamPath Agent - Course path planning and academic advising."""

from langgraph.graph import StateGraph, START, END

from dreampath_processing.dreampath_agent.agent_stateless import (
    orchestrator_node,
    course_search_node,
    plan_builder_node,
    course_path_node,
    modify_profile_node,
    rebuild_course_path_node,
    finalize_node
)
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState


def build_dreampath_graph():
    """Build the DreamPath agent graph.

    The checkpointer is provided via config at runtime by the service layer.
    """
    g = StateGraph(DreamPathAgentState)

    # Add nodes
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("course_search", course_search_node)
    g.add_node("plan_builder", plan_builder_node)
    g.add_node("course_path", course_path_node)
    g.add_node("modify_profile", modify_profile_node)
    g.add_node("rebuild_course_path", rebuild_course_path_node)
    g.add_node("finalize", finalize_node)

    # Set entry point
    g.add_edge(START, "orchestrator")

    # Orchestrator routing
    def router(state: DreamPathAgentState):
        return state.route or "finalize"

    g.add_conditional_edges("orchestrator", router, {
        "course_search": "course_search",
        "plan_builder": "plan_builder",
        "course_path": "course_path",
        "modify_profile": "modify_profile",
        "rebuild_course_path": "rebuild_course_path",
        "finalize": "finalize",
    })

    # Sub-node routing
    def sub_node_router(state: DreamPathAgentState):
        return state.route or "orchestrator"

    g.add_edge("course_search", "orchestrator")
    g.add_edge("plan_builder", "orchestrator")
    g.add_conditional_edges("course_path", sub_node_router, {
        "course_path": "course_path",
        "orchestrator": "orchestrator",
    })
    g.add_edge("modify_profile", "orchestrator")
    g.add_edge("rebuild_course_path", "orchestrator")
    g.add_edge("finalize", END)

    # Compile without checkpointer - it will be provided via config at runtime
    return g.compile()


# Export compiled graph
dreampath_agent = build_dreampath_graph()
dreampath_agent.name = "dreampath-agent"
