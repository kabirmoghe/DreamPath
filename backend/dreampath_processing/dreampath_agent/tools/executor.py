"""Tool executor node that parses raw tool calls into typed Pydantic models.

Sits between the orchestrator and target nodes. Reads pending_tool_call from
state, validates it against the registered input model, and sets tool_name +
tool_input for the target node to consume.
"""

from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.tools.registry import get_input_model


async def tool_executor_node(state: DreamPathAgentState, config) -> dict:
    """Parse raw tool call into typed Pydantic model, set tool_input for target node."""
    raw = state.pending_tool_call  # {name: str, arguments: dict}
    tool_name = raw["name"]
    input_model = get_input_model(tool_name)
    parsed = input_model.model_validate(raw["arguments"])

    print(f"| -> ToolExecutor: {tool_name} | {parsed.reason}")

    return {
        "tool_name": tool_name,
        "tool_input": parsed,
    }
