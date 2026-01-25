from dreampath_processing.dreampath_agent.context_building import (
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.dreampath_types import (
    DreamPathAgentState,
    OrchestratorDecision,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.nodes.prompts import ORCHESTRATOR_DECISION_SYS
from langchain_core.messages import AIMessage


def format_orchestrator_decision(decision: OrchestratorDecision) -> str:
    return f"route: {decision.route}\nreason: {decision.reason}\nconfidence: {decision.confidence}\nhandoff: {decision.handoff}"


async def decide_next_route(
    state: DreamPathAgentState,
    config,
    writer=None,
) -> tuple[OrchestratorDecision, dict]:
    """Determine the next route based on current state and context."""
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    return await extract_structured_output_from_context(
        state=state,
        config=config,
        system_prompt=ORCHESTRATOR_DECISION_SYS.format(student_name=student_name),
        response_model=OrchestratorDecision,
        small_context=False,
        model="o4-mini",
        task_prompt="What should happen next?",
        verbose=True,
        writer=writer,
    )


async def orchestrator_node(state: DreamPathAgentState, config, *, writer=None) -> DreamPathAgentState:
    """
    Orchestrator node that routes user requests to appropriate specialized nodes.

    Determines the next step based on:
    - User's latest message and conversation history
    - Current turn trace (tool calls/results)
    - Student's profile and course path context
    """
    # Create thinking status event
    thinking_event = AIMessage(
        content="",
        additional_kwargs={
            "event_type": "node_status",
            "node": "orchestrator",
            "status": "thinking",
            "message": "Thinking"
        }
    )

    # Emit thinking status IMMEDIATELY via custom event stream
    if writer:
        try:
            writer(thinking_event)
        except Exception as e:
            print(f"🎯 ORCHESTRATOR: Error emitting thinking event: {e}")

    # Do the actual LLM processing (pass writer for status updates during summarization)
    decision, state_updates = await decide_next_route(state, config, writer=writer)

    # Log decision
    print(f"| → Orchestrator: {decision.route} | {decision.reason}")

    orchestrator_decision = {
        "role": "assistant",
        "content": {
            "name": "orchestrator",
            "result": format_orchestrator_decision(decision),
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
            "next_node": decision.route,
            "reason": decision.reason
        }
    )

    # Return with routing info in messages list
    # (thinking_event was already streamed immediately via writer)
    return {
        "route": decision.route,
        "handoff": decision.handoff,
        "turn_messages": state.turn_messages + [orchestrator_decision],
        "messages": [orchestrator_msg_lc, complete_event],
        **state_updates,
    }
