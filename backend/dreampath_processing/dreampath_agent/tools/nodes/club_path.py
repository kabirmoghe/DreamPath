"""
Club path node — deterministic executor for ClubPath operations.

Mirrors course_path_node pattern: orchestrator emits structured operations,
node executes them with HITL confirmation when require_user_confirmation=True.

Unlike course_path_node, operations are cheap (no scheduling algorithm),
so pending_pre_interrupt is not needed — we just re-execute after confirmation.
"""

from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.schemas import ClubPathInput, ClubPathOperation
from langgraph.types import interrupt


async def _execute_operation(
    op: ClubPathOperation,
    club_path,
    user_id: str,
    student_db_service,
) -> str:
    """Execute a single club path operation. Returns result text."""
    if op.action == "add":
        from dreampath_processing.clubs.modules.activity import Activity
        from dreampath_processing.clubs.modules.club_path import ClubPath
        from dreampath_processing.weaviate.activity_service import WeaviateActivityService

        activity_service = WeaviateActivityService()
        activity_data = activity_service.get_activity_by_slug(op.activity_slug)
        if not activity_data:
            return f"Could not find activity '{op.activity_slug}' in catalog."

        activity = Activity(
            activity_slug=op.activity_slug,
            display_name=activity_data.get("display_name", op.activity_slug),
            mission_synth=activity_data.get("mission_synth", ""),
            activity_type=activity_data.get("activity_type", ""),
            domain=activity_data.get("domain", ""),
            selectivity_est=activity_data.get("selectivity_est", ""),
            time_commitment_est=activity_data.get("time_commitment_est", ""),
            owner_type=activity_data.get("owner_type", ""),
            skills_exposed=activity_data.get("skills_exposed") or [],
            career_alignment=activity_data.get("career_alignment") or [],
            subtags=activity_data.get("subtags") or [],
            who_its_for_synth=activity_data.get("who_its_for_synth", ""),
            what_you_do_synth=activity_data.get("what_you_do_synth", ""),
            how_to_join_synth=activity_data.get("how_to_join_synth", ""),
            data_confidence=activity_data.get("data_confidence", ""),
            evidence_citations=activity_data.get("evidence_citations", ""),
            source_of_truth_url=activity_data.get("source_of_truth_url", ""),
            roles_exposed=activity_data.get("roles_exposed") or [],
        )
        if club_path is None:
            club_path = ClubPath(recommendations={op.activity_slug: activity})
        else:
            club_path.add_activity(activity)
        return f"Added '{op.activity_slug}' to ClubPath."

    elif op.action == "remove":
        if club_path is None:
            return f"No ClubPath exists to remove '{op.activity_slug}' from."
        club_path.remove_activity(op.activity_slug)
        return f"Removed '{op.activity_slug}' from ClubPath."

    elif op.action == "edit":
        if club_path is None or op.activity_slug not in club_path.recommendations:
            return f"Cannot edit '{op.activity_slug}': not in ClubPath."

        activity = club_path.recommendations[op.activity_slug]
        changes = []

        if op.membership_status is not None:
            activity.membership_status = op.membership_status
            changes.append(f"membership → {op.membership_status}")

        if op.current_role is not None:
            if op.current_role == "":
                activity.current_role = None
                changes.append("role cleared")
            else:
                if activity.roles_exposed and op.current_role not in activity.roles_exposed:
                    return f"Invalid role '{op.current_role}' for '{op.activity_slug}'. Valid roles: {', '.join(activity.roles_exposed)}."
                activity.current_role = op.current_role
                changes.append(f"role → {op.current_role}")

        if op.rank is not None:
            club_path.reorder_activity(op.activity_slug, op.rank - 1)  # 1-indexed → 0-indexed
            changes.append(f"rank → {op.rank}")

        if not changes:
            return f"No changes specified for '{op.activity_slug}'."

        return f"Edited '{op.activity_slug}': {', '.join(changes)}."

    return f"Unknown action '{op.action}'."


async def club_path_node(state: DreamPathAgentState, config) -> dict:
    """
    Club path node that executes ClubPath modifications.

    Reads structured operations from tool_input on first entry (club_cursor == 0),
    then loops through them with user confirmation when required.
    """
    student_db_service = config["configurable"]["student_db_service"]
    user_id = config["configurable"]["user_id"]

    cursor = state.club_cursor
    tool_messages = []
    langchain_messages = []

    # On first entry, read operations from tool_input
    if cursor == 0:
        tool_input: ClubPathInput = state.tool_input
        worklist = tool_input.operations
    else:
        worklist = state.club_worklist

    tool_call_id = state.pending_tool_call["tool_call_id"]

    print(f"| → ClubPathNode: club_worklist={[str(op) for op in worklist]}, club_cursor={cursor}")

    # Build tool call trace at start of execution
    if cursor == 0:
        tool_call = {
            "role": "assistant",
            "content": {
                "name": "club_path",
                "arguments": {
                    "operations": [op.model_dump() for op in worklist],
                }
            },
            "tool_call_id": tool_call_id,
        }
        tool_messages.append(tool_call)
        langchain_messages.append(dreampath_to_langchain(tool_call))

    if worklist and cursor < len(worklist):
        current_op = worklist[cursor]
        op_label = f"{current_op.action} {current_op.activity_slug}"

        # HITL confirmation if required
        if state.require_user_confirmation:
            op_metadata = {
                "type": current_op.action,
                "activity_slug": current_op.activity_slug,
            }
            if current_op.rank is not None:
                op_metadata["rank"] = current_op.rank
            if current_op.membership_status is not None:
                op_metadata["membership_status"] = current_op.membership_status
            if current_op.current_role is not None:
                op_metadata["current_role"] = current_op.current_role

            user_response = interrupt({
                "pending_pre_interrupt": None,
                "text": "",
                "event_type": "clubpath_operations",
                "op_string": op_label,
                "operations": [op_metadata],
            })

            action_word = user_response.split(":")[0].strip().lower()
            if action_word in ("reject", "cancel"):
                tool_result = {
                    "role": "tool",
                    "content": {"name": "club_path", "result": f"Cancelled: {op_label}"},
                    "tool_call_id": tool_call_id,
                }
                tool_messages.append(tool_result)
                cursor += 1
                return {
                    "turn_messages": state.turn_messages + tool_messages,
                    "club_worklist": worklist,
                    "club_cursor": cursor,
                    "messages": langchain_messages,
                }

        # Load current club path and execute
        club_path = await student_db_service.load_club_path(user_id)

        try:
            result_text = await _execute_operation(current_op, club_path, user_id, student_db_service)
        except Exception as e:
            result_text = f"Error executing '{op_label}': {e}"

        # Save updated club path
        if club_path:
            await student_db_service.save_club_path(club_path, user_id)

        tool_result = {
            "role": "tool",
            "content": {"name": "club_path", "result": result_text},
            "tool_call_id": tool_call_id,
        }
        tool_messages.append(tool_result)
        cursor += 1
    else:
        # All operations done — format aggregate result
        tool_result = {
            "role": "tool",
            "content": {"name": "club_path", "result": f"Completed {len(worklist)} club path operation(s)."},
            "tool_call_id": tool_call_id,
        }
        tool_messages.append(tool_result)

    updates = {
        "turn_messages": state.turn_messages + tool_messages,
        "club_worklist": worklist,
        "club_cursor": cursor,
        "messages": langchain_messages,
    }

    # Clean up when done looping so next club_path call this turn starts fresh
    if not worklist or cursor >= len(worklist):
        updates["club_worklist"] = []
        updates["club_cursor"] = 0

    return updates
