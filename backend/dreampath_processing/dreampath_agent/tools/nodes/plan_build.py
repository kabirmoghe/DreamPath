"""
Plan build node — pure state write, no LLM call.

Writes per-phase guidance onto BuildPhase objects so the orchestrator
sees targeted instructions when it reaches each phase.
"""

from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.schemas import PlanBuildInput


async def plan_build_node(state: DreamPathAgentState, config) -> dict:
    tool_input: PlanBuildInput = state.tool_input
    plan = state.build_plan

    # Build lookup from phase_guidance input
    guidance_map = {entry.phase: entry.guidance for entry in tool_input.phase_guidance}

    # Write guidance onto each phase
    for phase in plan.phases:
        if phase.name in guidance_map:
            phase.guidance = guidance_map[phase.name]

    # Format summary for context
    lines = ["Build plan guidance set:"]
    for phase in plan.phases:
        if phase.guidance:
            lines.append(f"  - {phase.name}: {phase.guidance}")

    tool_result = {
        "role": "tool",
        "content": {"name": "plan_build", "result": "\n".join(lines)},
        "tool_call_id": state.pending_tool_call["tool_call_id"],
    }

    print(f"| -> PlanBuild: set guidance for {len(guidance_map)} phases")

    return {
        "build_plan": plan,
        "turn_messages": state.turn_messages + [tool_result],
        "messages": [dreampath_to_langchain(tool_result)],
    }
