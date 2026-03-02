import json

from dreampath_processing.dreampath_agent.context_building import (
    async_client,
    build_complete_context,
    calculate_token_count,
)
from dreampath_processing.dreampath_agent.debug_logger import log_messages_to_file
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.prompts import ORCHESTRATOR_DECISION_SYS
from dreampath_processing.dreampath_agent.tools.registry import (
    get_node_for_tool,
    get_openai_tools,
)
from langchain_core.messages import AIMessage


def format_orchestrator_tool_call(tool_name: str, arguments: dict) -> str:
    """Format a tool call for the turn trace."""
    reason = arguments.get("reason", "")
    # Include all fields except reason for context
    other_fields = {k: v for k, v in arguments.items() if k != "reason"}
    parts = [f"tool: {tool_name}", f"reason: {reason}"]
    for k, v in other_fields.items():
        parts.append(f"{k}: {v}")
    return "\n".join(parts)


async def orchestrator_node(state: DreamPathAgentState, config, *, writer=None) -> DreamPathAgentState:
    """
    Orchestrator node that routes user requests to appropriate specialized nodes.

    Uses tool calling: emits exactly one tool call per turn with structured input.
    The tool_executor node downstream parses the raw call into a typed Pydantic model.
    """
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name

    # Build context (summarization + status events happen inside)
    messages, state_updates = await build_complete_context(
        state,
        ORCHESTRATOR_DECISION_SYS.format(student_name=student_name),
        config,
        task_prompt="What should happen next?",
        writer=writer,
    )

    log_messages_to_file(messages)
    print(f"[ MODEL=o4-mini | TOKEN COUNT: {calculate_token_count(messages, 'o4-mini')} ]")

    # Emit "Thinking" status right before LLM call
    if writer:
        try:
            thinking_event = AIMessage(
                content="",
                additional_kwargs={
                    "event_type": "node_status",
                    "node": "orchestrator",
                    "status": "thinking",
                    "message": "Thinking"
                }
            )
            writer(thinking_event)
        except Exception as e:
            print(f"Warning: Error emitting thinking status: {e}")

    # Call LLM with tool calling
    response = await async_client.chat.completions.create(
        model="o4-mini",
        messages=messages,
        tools=get_openai_tools(),
        tool_choice="required",
    )

    # Extract tool call (tool_choice="required" guarantees at least one)
    tool_call = response.choices[0].message.tool_calls[0]
    tool_name = tool_call.function.name
    raw_arguments = json.loads(tool_call.function.arguments)
    reason = raw_arguments.get("reason", "")

    # Log decision
    next_node = get_node_for_tool(tool_name)
    print(f"| -> Orchestrator: {tool_name} | {reason}")

    # Build trace message for turn_messages
    orchestrator_decision = {
        "role": "assistant",
        "content": {
            "name": "orchestrator",
            "result": format_orchestrator_tool_call(tool_name, raw_arguments),
        },
    }
    orchestrator_msg_lc = dreampath_to_langchain(orchestrator_decision)

    # Create completion status event
    complete_event = AIMessage(
        content="",
        additional_kwargs={
            "event_type": "node_status",
            "node": "orchestrator",
            "status": "node_info",
            "next_node": next_node,
            "reason": reason,
        }
    )

    return {
        "pending_tool_call": {"name": tool_name, "arguments": raw_arguments},
        "turn_messages": state.turn_messages + [orchestrator_decision],
        "messages": [orchestrator_msg_lc, complete_event],
        **state_updates,
    }
