from dreampath_processing.dreampath_agent.search_agent.nodes.finalizer import finalize_node
from dreampath_processing.dreampath_agent.search_agent.nodes.orchestrator import orchestrator_node
from dreampath_processing.dreampath_agent.search_agent.nodes.tool_executor import tool_executor_node
from dreampath_processing.dreampath_agent.search_agent.search_types import SearchAgentState
from langgraph.graph import END, START, StateGraph

# Max iterations safety limit
MAX_ITERATIONS = 20

def build_search_agent():
    """
    Build the search agent graph.

    Flow:
    START → orchestrator → tool_executor → router → [orchestrator OR finalizer] → END

    Simplified architecture:
    - No iteration_messages - nodes append directly to search_trace
    - Iteration increments when looping back to orchestrator
    - MAX_ITERATIONS safety check forces completion
    """

    # Create graph
    graph = StateGraph(SearchAgentState)

    # Add nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("finalizer", finalize_node)

    # Entry point
    graph.add_edge(START, "orchestrator")

    # Orchestrator always goes to tool executor
    graph.add_edge("orchestrator", "tool_executor")

    # Tool executor routes based on action type
    def tool_executor_router(state: SearchAgentState):
        """Route based on next_action and iteration limit"""

        # Safety check: max iterations
        if state.iteration >= MAX_ITERATIONS:
            print(f"\n⚠️  MAX_ITERATIONS ({MAX_ITERATIONS}) reached, forcing completion")
            return "finalizer"

        # Normal routing based on action type
        if state.next_action.action_type == "complete":
            return "finalizer"
        else:
            # Loop back to orchestrator - increment iteration via state update
            return "orchestrator"

    graph.add_conditional_edges(
        "tool_executor",
        tool_executor_router,
        # When routing to orchestrator, increment iteration
        path_map={
            "orchestrator": "orchestrator",
            "finalizer": "finalizer"
        }
    )

    # Finalizer always goes to END
    graph.add_edge("finalizer", END)

    # Compile and return
    compiled_graph = graph.compile()

    # Generate visualization
    try:
        png_graph = compiled_graph.get_graph().draw_mermaid_png()
        with open("search_architecture.png", "wb") as f:
            f.write(png_graph)
        print("✓ Graph visualization saved to search_architecture.png")
    except Exception as e:
        print(f"Warning: Could not generate graph visualization: {e}")

    return compiled_graph
