from dreampath_processing.dreampath_agent.context_building import (
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.dreampath_types import (
    CoursePathOperations,
    DreamPathAgentState,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.nodes.prompts import BUILD_OPERATIONS_SYS


def format_worklist(worklist: list[str]) -> str:
    """Format worklist of operations for context."""
    output_str = "<worklist>\n"
    for op in worklist:
        output_str += "Ops. awaiting execution:\n"
        output_str += f"<op>{op}</op>\n"
    output_str += "</worklist>"
    return output_str


async def build_operations_from_context_and_results(state: DreamPathAgentState, config) -> tuple[CoursePathOperations, dict]:
    """Build course path operations based on context and search results."""
    return await extract_structured_output_from_context(
        state=state,
        config=config,
        system_prompt=BUILD_OPERATIONS_SYS,
        response_model=CoursePathOperations,
        small_context=True,
        model="gpt-4o"
    )


async def plan_builder_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    Plan builder node that creates course path modification operations.

    Generates a worklist of operations (add, remove, move, swap, replace, rebuild)
    to be executed by the course_path node.
    """
    ops, _ = await build_operations_from_context_and_results(state, config)

    tool_result = {
        "role": "assistant",
        "content": {
            "name": "plan_builder",
            "result": format_worklist(ops.operations),
        },
    }

    tool_result_lc = dreampath_to_langchain(tool_result)

    return {
        "worklist": ops.operations,
        "cursor": 0,
        "current_cp_agent_outcomes": {},
        "turn_messages": state.turn_messages + [tool_result],
        "messages": [tool_result_lc],
    }
