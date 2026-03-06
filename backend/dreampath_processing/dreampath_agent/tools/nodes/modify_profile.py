"""
Modify profile node — deterministic executor, no LLM call.

The orchestrator emits structured profile fields directly via ModifyProfileInput.
The node compares against the current profile, presents changes for HITL
confirmation, and saves on accept.
"""

from dreampath_processing.dreampath_agent.dreampath_types import (
    DreamPathAgentState,
    ModifiedStudentProfile,
)
from dreampath_processing.dreampath_agent.frontend_message_helpers import (
    extract_profile_update_metadata,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.schemas import ModifyProfileInput
from langgraph.types import interrupt


def format_modified_student_profile(modified_profile: ModifiedStudentProfile) -> str:
    """Format modified profile for context."""
    modified_profile_content = f"major: {modified_profile.major}\n"
    modified_profile_content += f"college_interests: {modified_profile.college_interests}\n"
    modified_profile_content += f"post_grad_goals: {modified_profile.post_grad_goals}\n"
    modified_profile_content += f"career_goals: {modified_profile.career_goals}\n"
    return f"<mod_result>\n{modified_profile_content}</mod_result>"


async def modify_profile_node(state: DreamPathAgentState, config) -> dict:
    """
    Modify profile node that handles student profile updates.

    Reads structured profile fields from tool_input (emitted by orchestrator).
    Presents changes for HITL confirmation when require_user_confirmation=True.
    """
    print("| → ProfileModifier")

    tool_input: ModifyProfileInput = state.tool_input

    # Merge only non-None fields onto the current profile to build the modified version
    student_db_service = config["configurable"]["student_db_service"]
    current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

    modified_profile = ModifiedStudentProfile(
        major=tool_input.major if tool_input.major is not None else current_profile.major,
        college_interests=tool_input.college_interests if tool_input.college_interests is not None else current_profile.college_interests,
        post_grad_goals=tool_input.post_grad_goals if tool_input.post_grad_goals is not None else current_profile.post_grad_goals,
        career_goals=tool_input.career_goals if tool_input.career_goals is not None else current_profile.career_goals,
    )

    # HITL confirmation (skipped when require_user_confirmation=False, e.g. during build mode)
    if state.require_user_confirmation:
        # Extract structured metadata for frontend rendering
        structured_metadata = extract_profile_update_metadata(modified_profile, current_profile)

        if structured_metadata:
            interrupt_text = ""  # Empty - let the card render everything
        else:
            interrupt_text = f"How do you feel about the modified profile? {modified_profile}"

        user_response = interrupt({
            "pending_pre_interrupt": modified_profile,
            "text": interrupt_text,
            **structured_metadata
        })

        raw = user_response.strip()
        accepted = raw.lower().startswith("accept")
        note = raw.split(":", 1)[1].strip() if ":" in raw else ""

        if accepted:
            current_profile.major = modified_profile.major
            current_profile.college_interests = modified_profile.college_interests
            current_profile.post_grad_goals = modified_profile.post_grad_goals
            current_profile.career_goals = modified_profile.career_goals

            print("| → ProfileModifier: user accepted")

            formatted_result = format_modified_student_profile(modified_profile)
            if note:
                formatted_result += f"\n<user_note>{note}</user_note>"
            tool_result = {
                "role": "tool",
                "content": {"name": "modify_profile", "result": formatted_result},
                "tool_call_id": state.pending_tool_call["tool_call_id"],
            }

            await student_db_service.save_student_profile(current_profile, config["configurable"]["user_id"])

            return {
                "turn_messages": state.turn_messages + [tool_result],
                "pending_pre_interrupt": None,
                "messages": [dreampath_to_langchain(tool_result)],
            }
        else:
            rejection_note = f"\n<user_note>{note}</user_note>" if note else ""
            proposed = format_modified_student_profile(modified_profile)
            tool_result = {
                "role": "tool",
                "content": {
                    "name": "modify_profile",
                    "result": f"<mod_result>User rejected profile modification.{rejection_note}\n<proposed_changes>{proposed}</proposed_changes></mod_result>",
                },
                "tool_call_id": state.pending_tool_call["tool_call_id"],
            }
            return {
                "turn_messages": state.turn_messages + [tool_result],
                "pending_pre_interrupt": None,
                "messages": [dreampath_to_langchain(tool_result)],
            }

    # require_user_confirmation=False: save directly (build mode)
    current_profile.major = modified_profile.major
    current_profile.college_interests = modified_profile.college_interests
    current_profile.post_grad_goals = modified_profile.post_grad_goals
    current_profile.career_goals = modified_profile.career_goals

    await student_db_service.save_student_profile(current_profile, config["configurable"]["user_id"])

    formatted_result = format_modified_student_profile(modified_profile)
    tool_result = {
        "role": "tool",
        "content": {"name": "modify_profile", "result": formatted_result},
        "tool_call_id": state.pending_tool_call["tool_call_id"],
    }

    print("| → ProfileModifier: saved directly (no confirmation required)")

    return {
        "turn_messages": state.turn_messages + [tool_result],
        "messages": [dreampath_to_langchain(tool_result)],
    }
