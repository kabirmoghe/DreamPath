from dreampath_processing.dreampath_agent.context_building import (
    async_client,
    build_small_context,
    calculate_token_count,
)
from dreampath_processing.dreampath_agent.dreampath_types import (
    CoursePathOperations,
    DreamPathAgentState,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.nodes.prompts import BUILD_OPERATIONS_SYS
from dreampath_processing.dreampath_agent.tools.schemas import PlanBuilderInput


def format_worklist(worklist: list[str]) -> str:
    """Format worklist of operations for context."""
    output_str = "<worklist>\n"
    for op in worklist:
        output_str += "Ops. awaiting execution:\n"
        output_str += f"<op>{op}</op>\n"
    output_str += "</worklist>"
    return output_str


async def build_operations_from_context_and_results(state: DreamPathAgentState, config, instructions: str) -> tuple[CoursePathOperations, dict]:
    """Build course path operations based on context and search results."""
    messages = await build_small_context(state, BUILD_OPERATIONS_SYS, config, instructions)
    print(f"[ MODEL=gpt-4o | TOKEN COUNT: {calculate_token_count(messages, 'gpt-4o')} ]")
    completion = await async_client.chat.completions.parse(
        model="gpt-4o",
        messages=messages,
        response_format=CoursePathOperations,
        temperature=0
    )
    return completion.choices[0].message.parsed, {}


async def plan_builder_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    Plan builder node that creates course path modification operations.

    Generates a worklist of operations (add, remove, move, swap, replace, rebuild)
    to be executed by the course_path node.
    """
    tool_input: PlanBuilderInput = state.tool_input
    ops, _ = await build_operations_from_context_and_results(state, config, instructions=tool_input.instructions)

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
