"""Complete phase node — pure state mutation, no LLM call.

Marks the current build phase complete and advances to the next phase.
"""

from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.schemas import CompletePhaseInput
from langchain_core.messages import AIMessage


async def complete_phase_node(state: DreamPathAgentState, config) -> dict:
    tool_input: CompletePhaseInput = state.tool_input
    plan = state.build_plan

    # Mark current phase complete with notes
    current = plan.phases[plan.current_phase]
    current.status = "complete"
    current.notes = tool_input.notes

    phase_name = current.name

    # Advance to next phase
    plan.current_phase += 1
    if plan.current_phase < len(plan.phases):
        plan.phases[plan.current_phase].status = "active"
        next_name = plan.phases[plan.current_phase].name
    else:
        next_name = "done"

    tool_result = {
        "role": "tool",
        "content": {
            "name": "complete_phase",
            "result": f"Phase '{phase_name}' marked complete. Current phase is now '{next_name}' — call tools for '{next_name}' next (or complete_phase to skip it).",
        },
        "tool_call_id": state.pending_tool_call["tool_call_id"],
    }

    # Emit phase progress event for frontend
    phase_event = AIMessage(
        content="",
        additional_kwargs={
            "event_type": "phase_update",
            "current_phase": plan.current_phase,
            "total_phases": len(plan.phases),
            "phases": [{"name": p.name, "status": p.status} for p in plan.phases],
        }
    )

    print(f"| -> CompletePhase: '{phase_name}' → '{next_name}'")

    return {
        "build_plan": plan,
        "turn_messages": state.turn_messages + [tool_result],
        "messages": [dreampath_to_langchain(tool_result), phase_event],
    }
