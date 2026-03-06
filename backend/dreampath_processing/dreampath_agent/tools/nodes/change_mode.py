"""Change mode node — pure state mutation, no LLM call.

Handles transition between advise and build modes, initializing/tearing down
build plan state as appropriate.
"""

from dreampath_processing.dreampath_agent.dreampath_types import (
    BuildPhase,
    BuildPlan,
    DreamPathAgentState,
)
from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.database.thread_service import ThreadDatabaseService
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.schemas import ChangeModeInput
from langchain_core.messages import AIMessage


def _summarize_build_results(plan: BuildPlan) -> str:
    """Generate structured summary from completed build phases."""
    lines = ["<build_summary>"]
    for i, phase in enumerate(plan.phases):
        if phase.status == "complete" and phase.notes:
            lines.append(f"  Phase {i + 1} ({phase.name}): {phase.notes}")
        elif phase.status == "skipped":
            lines.append(f"  Phase {i + 1} ({phase.name}): Skipped")
    lines.append("</build_summary>")
    return "\n".join(lines)


_BUILD_PHASES = [
    "plan_build",
    "update_profile",
    "course_search",
    "activity_search",
    "curate",
    "build_dreampath",
    "reflect",
    "refine",
    "finish",
]


async def change_mode_node(state: DreamPathAgentState, config) -> dict:
    tool_input: ChangeModeInput = state.tool_input
    target = tool_input.target_mode
    current_mode = state.mode

    updates: dict = {"mode": target}

    if target == "build":
        updates["require_user_confirmation"] = False
        updates["build_plan"] = BuildPlan(
            phases=[BuildPhase(name=name) for name in _BUILD_PHASES]
        )
        result_text = f"Entering build mode.\nInstructions: {tool_input.instructions}"

    else:  # target == "advise"
        updates["require_user_confirmation"] = True
        updates["build_plan"] = None
        updates["curated_courses"] = []
        updates["curated_activities"] = []

        if current_mode == "build" and state.build_plan:
            summary = _summarize_build_results(state.build_plan)
            result_text = f"Exiting build mode.\n{summary}\nEntering advise mode.\nInstructions: {tool_input.instructions}"
        else:
            result_text = f"Entering advise mode.\nInstructions: {tool_input.instructions}"

    tool_result = {
        "role": "tool",
        "content": {"name": "change_mode", "result": result_text},
        "tool_call_id": state.pending_tool_call["tool_call_id"],
    }
    # Emit mode_change event for frontend
    mode_event = AIMessage(
        content="",
        additional_kwargs={
            "event_type": "mode_change",
            "mode": target,
        }
    )

    updates["turn_messages"] = state.turn_messages + [tool_result]
    updates["messages"] = [dreampath_to_langchain(tool_result), mode_event]

    # Persist mode to threads table
    thread_id = config.get("configurable", {}).get("thread_id")
    if thread_id:
        try:
            db = get_db_connection()
            thread_service = ThreadDatabaseService(db)
            await thread_service.update_mode(thread_id, target)
        except Exception as e:
            print(f"⚠️ ChangeMode: Failed to persist mode to threads table: {e}")

    print(f"| -> ChangeMode: {current_mode} → {target}")

    return updates
