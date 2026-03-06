"""Tool executor node that parses raw tool calls into typed Pydantic models.

Sits between the orchestrator and target nodes. Reads pending_tool_call from
state, validates it against the registered input model, and sets tool_name +
tool_input for the target node to consume.

In build mode, enforces soft phase guardrails: if the called tool doesn't match
the current phase, injects a developer warning and routes back to orchestrator.
"""

from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.registry import get_input_model

# Phase → expected tools mapping
_PHASE_TOOLS: dict[str, set[str]] = {
    "plan_build": {"plan_build", "career_search", "complete_phase"},
    "update_profile": {"modify_profile", "complete_phase"},
    "course_search": {"course_search", "complete_phase"},
    "activity_search": {"activity_search", "complete_phase"},
    "curate": {"curate", "course_search", "activity_search", "complete_phase"},
    "build_dreampath": {"build_dreampath", "complete_phase"},
    "reflect": {"complete_phase"},
    "refine": {"course_search", "activity_search", "course_path", "club_path", "modify_profile", "complete_phase"},
    "finish": {"change_mode"},
}


async def tool_executor_node(state: DreamPathAgentState, config) -> dict:
    """Parse raw tool call into typed Pydantic model, set tool_input for target node."""
    raw = state.pending_tool_call  # {name: str, arguments: dict}
    tool_name = raw["name"]
    input_model = get_input_model(tool_name)
    parsed = input_model.model_validate(raw["arguments"])

    print(f"| -> ToolExecutor: {tool_name} | {parsed.reason}")

    # Phase guardrails (build mode only)
    if state.mode == "build" and state.build_plan and tool_name != "change_mode":
        phase = state.build_plan.phases[state.build_plan.current_phase]
        expected = _PHASE_TOOLS.get(phase.name, set())
        if tool_name not in expected:
            warning = (
                f"Warning: you called `{tool_name}` but you are in phase "
                f"'{phase.name}' (phase {state.build_plan.current_phase + 1}). "
                f"Expected tools: {expected}. Call `complete_phase` to advance "
                f"before using `{tool_name}`, or proceed if intentional."
            )
            print(f"| ⚠️ Phase guardrail: {warning}")
            dev_msg = {"role": "developer", "content": warning}
            return {
                "turn_messages": state.turn_messages + [dev_msg],
                "tool_name": None,
            }

    return {
        "tool_name": tool_name,
        "tool_input": parsed,
    }
