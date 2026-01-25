from dreampath_processing.courses.coursepath_agent.agent_v3 import CoursePathAPIService
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.frontend_message_helpers import (
    extract_coursepath_operations_metadata,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from langgraph.types import interrupt


def format_aggregate_coursepath_agent_result(outcomes: dict[str, CoursePathAgentOutput], diff: str | None = None) -> str:
    """Format aggregate outcome from multiple course path operations."""
    outcomes_str = ""

    for op, outcome in outcomes.items():
        outcomes_str += f"<op_result>\n* For op '{op}': {outcome.ui_text}\n</op_result>\n"

    if diff:
        diff_str = f"<aggregate_diff>{diff}\n</aggregate_diff>"
    else:
        diff_str = ""

    return f"{outcomes_str}{diff_str}"


async def course_path_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    Course path node that executes course modifications.

    Processes the worklist of operations created by plan_builder_node,
    executing each operation with user confirmation when required.
    """
    service: CoursePathAPIService = CoursePathAPIService(config["configurable"]["conn"])

    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    major = student_profile.major

    cursor = state.cursor
    current_op = None
    outcomes = state.current_cp_agent_outcomes
    worklist = state.worklist
    tool_messages = []
    langchain_messages = []

    print(f"| → CoursePathAgent: worklist={worklist}, cursor={cursor}")

    # Build tool call at start of execution
    if cursor == 0:
        tool_call = {
            "role": "assistant",
            "content": {
                "name": "course_path_agent",
                "arguments": {
                    "worklist": worklist,
                    "cursor": cursor
                }
            },
        }
        tool_messages.append(tool_call)
        langchain_messages.append(dreampath_to_langchain(tool_call))

    # Execute operations one by one
    if worklist and cursor < len(worklist):
        current_op = worklist[cursor]

        # If we have a pending pre-interrupt, use it
        if state.pending_pre_interrupt is not None:
            print("| * Using cached pre-interrupt output (avoiding re-execution)")
            cp_agent_output = state.pending_pre_interrupt
        else:
            print("| * Executing operation for the first time")
            cp_agent_output = await service.run_stateless(
                user_id=config['configurable']['user_id'],
                message=current_op,
                major=major,
                require_user_confirmation=state.require_user_confirmation
            )

        if cp_agent_output.status == "ask":
            # Extract structured metadata for frontend rendering
            structured_metadata = extract_coursepath_operations_metadata(cp_agent_output)
            print(f"🔍 DEBUG: structured_metadata = {structured_metadata}")

            # Use clean message when we have structured data for visual rendering
            # Include op_string for operation type display (e.g., "ADD COSC78")
            if structured_metadata:
                interrupt_text = ""  # Empty - let the card render everything
                if cp_agent_output.op_string:
                    structured_metadata['op_string'] = cp_agent_output.op_string
            else:
                # Fallback to detailed text if no structured data
                interrupt_text = cp_agent_output.ui_text

            # Use interrupt() function to pause and wait for user input
            user_response = interrupt({
                "pending_pre_interrupt": cp_agent_output,
                "text": interrupt_text,
                **structured_metadata
            })

            # Continue processing with user response
            cp_agent_output = await service.run_stateless(
                user_id=config['configurable']['user_id'],
                message=user_response,
                major=major,
                require_user_confirmation=state.require_user_confirmation
            )

        outcomes[current_op] = cp_agent_output
        cursor += 1
        route = "course_path"
    else:
        route = "orchestrator"

        # Format aggregate outcome
        aggregate_result = format_aggregate_coursepath_agent_result(state.current_cp_agent_outcomes)
        tool_result = {
            "role": "assistant",
            "content": {
                "name": "course_path_agent",
                "result": aggregate_result,
            },
        }
        tool_messages.append(tool_result)

    return {
        "turn_messages": state.turn_messages + tool_messages,
        "pending_pre_interrupt": None,
        "current_cp_agent_outcomes": outcomes,
        "worklist": worklist,
        "cursor": cursor,
        "route": route,
        "messages": langchain_messages,
    }
