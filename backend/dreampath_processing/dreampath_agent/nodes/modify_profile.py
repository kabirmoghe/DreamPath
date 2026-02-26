from dotenv import load_dotenv
from dreampath_processing.dreampath_agent.context_building import (
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.dreampath_types import (
    DreamPathAgentState,
    ModifiedStudentProfile,
)
from dreampath_processing.dreampath_agent.frontend_message_helpers import (
    extract_profile_update_metadata,
)
from dreampath_processing.dreampath_agent.nodes.prompts import MODIFY_PROFILE_SYS
from langgraph.types import interrupt

load_dotenv()


def format_modified_student_profile(modified_profile: ModifiedStudentProfile) -> str:
    """Format modified profile for context."""
    modified_profile_content = f"major: {modified_profile.major}\n"
    modified_profile_content += f"college_interests: {modified_profile.college_interests}\n"
    modified_profile_content += f"post_grad_goals: {modified_profile.post_grad_goals}\n"
    modified_profile_content += f"career_goals: {modified_profile.career_goals}\n"
    return f"<mod_result>\n{modified_profile_content}</mod_result>"


async def modify_student_profile(state: DreamPathAgentState, config) -> tuple[ModifiedStudentProfile, dict]:
    """Generate modified student profile based on context."""
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    return await extract_structured_output_from_context(
        state=state,
        config=config,
        system_prompt=MODIFY_PROFILE_SYS.format(student_name=student_name),
        response_model=ModifiedStudentProfile,
        small_context=True,
        model="gpt-4o",
        temperature=0.1
    )


async def modify_profile_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    Modify profile node that handles student profile updates.

    Supports modifying:
    - Major
    - College interests
    - Post-grad goals
    - Career goals

    Requires user confirmation before saving changes.
    """
    print("| → ProfileModifier")

    langchain_messages = []

    # Check if we already computed the modified profile (to avoid re-computing on interrupt resume)
    if state.pending_pre_interrupt is not None:
        print("| * Using cached modified profile (avoiding re-computation)")
        modified_profile = state.pending_pre_interrupt
    else:
        print("| * Computing modified profile for the first time")
        modified_profile, _ = await modify_student_profile(state, config)

    # Verify modified profile with user (skipped when require_user_confirmation=False, e.g. during rebuild)
    if state.require_user_confirmation:
        # Load current profile from DB for comparison
        student_db_service = config["configurable"]["student_db_service"]
        current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

        # Extract structured metadata for frontend rendering
        structured_metadata = extract_profile_update_metadata(modified_profile, current_profile)

        # Use clean message when we have structured data for visual rendering
        if structured_metadata:
            interrupt_text = ""  # Empty - let the card render everything
        else:
            # Fallback to detailed text if no structured data
            interrupt_text = f"How do you feel about the modified profile? {modified_profile.__str__()}"

        user_response = interrupt({
            "pending_pre_interrupt": modified_profile,
            "text": interrupt_text,
            **structured_metadata
        })

        # Determine accept/reject directly from button-driven response (startswith 'accept')
        raw = user_response.strip()
        accepted = raw.lower().startswith('accept')
        note = raw.split(':', 1)[1].strip() if ':' in raw else ''

        if accepted:
            # Reload profile to ensure we have latest data
            current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

            # Update only the modifiable fields from ModifiedStudentProfile
            current_profile.major = modified_profile.major
            current_profile.college_interests = modified_profile.college_interests
            current_profile.post_grad_goals = modified_profile.post_grad_goals
            current_profile.career_goals = modified_profile.career_goals

            print(f"| → ProfileModifier: user accepted, updated_profile={current_profile}")

            formatted_result = format_modified_student_profile(modified_profile)
            if note:
                formatted_result += f"\n<user_note>{note}</user_note>"
            tool_result = {
                "role": "assistant",
                "content": {
                    "name": "modify_profile",
                    "result": formatted_result,
                },
            }

            # Save the complete StudentProfile back to the database
            await student_db_service.save_student_profile(current_profile, config["configurable"]["user_id"])

            return {
                "turn_messages": state.turn_messages + [tool_result],
                "pending_pre_interrupt": None,
                "messages": langchain_messages,
            }
        else:
            # User rejected — include the proposed changes so the orchestrator can reference them
            rejection_note = f"\n<user_note>{note}</user_note>" if note else ""
            proposed = format_modified_student_profile(modified_profile)
            tool_result = {
                "role": "assistant",
                "content": {
                    "name": "modify_profile",
                    "result": f"<mod_result>User rejected profile modification.{rejection_note}\n<proposed_changes>{proposed}</proposed_changes></mod_result>",
                },
            }
            return {
                "turn_messages": state.turn_messages + [tool_result],
                "pending_pre_interrupt": None,
                "messages": langchain_messages,
            }

    # require_user_confirmation=False: profile already handled upstream (e.g. rebuild)
    return {}
