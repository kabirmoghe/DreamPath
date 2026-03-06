"""
Career search node for retrieving career role data.

This is a data-lookup node (no LLM call). It reads the orchestrator's
handoff, matches it against the hardcoded SWE career data, and returns
formatted role information as tool_call + tool_result messages.
"""

import asyncio

from dreampath_processing.careers.career_data import match_query_to_roles
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain


def _format_role(role: dict) -> str:
    """Format a single role dict into readable markdown-style text."""
    d = role["data"]
    lines = [
        f"## {role['title']}",
        "",
        d["spec"],
        "",
        "### Most Important Capabilities",
    ]
    for i, cap in enumerate(d["most_important_capabilities"], 1):
        lines.append(f"{i}. **{cap['name']}** — {cap['description']}")

    lines.append("")
    lines.append("### Key Industry Changes")
    for ch in d["changes"]:
        scope_parts = []
        if ch["role_level"]:
            scope_parts.append("role-level")
        if ch["interview_level"]:
            scope_parts.append("interview-level")
        scope = ", ".join(scope_parts)
        lines.append(f"- **{ch['label']}** ({scope}): {ch['description']}")

    return "\n".join(lines)


async def career_search_node(state: DreamPathAgentState, config, *, writer=None) -> dict:
    """
    Career search node that looks up career role data.

    Uses tool_input.query as the search query. Matches against SWE career
    family data and returns formatted results. No LLM call needed.
    """
    from dreampath_processing.dreampath_agent.tools.schemas import CareerSearchInput

    tool_input: CareerSearchInput = state.tool_input
    search_query = tool_input.query

    print(f"| CareerSearchNode: matching query='{search_query[:80]}'")

    matched_roles = match_query_to_roles(search_query)

    if matched_roles:
        result_text = "\n\n---\n\n".join(_format_role(r) for r in matched_roles)
        print(f"| CareerSearchNode: matched {len(matched_roles)} role(s)")
        print(result_text)
    else:
        result_text = (
            "No career data available for this query yet. "
            "Career data is currently available for Software Engineering roles "
            "(Full Stack, Backend, AI Engineer, FDE). "
            "More career families are coming soon."
        )
        print("| CareerSearchNode: no matches found")

    tool_call_id = state.pending_tool_call["tool_call_id"]

    # Create tool call message (shows what was searched)
    tool_call = {
        "role": "assistant",
        "content": {
            "name": "career_search",
            "arguments": {"query": search_query},
        },
        "tool_call_id": tool_call_id,
    }

    # Create tool result message
    tool_result = {
        "role": "tool",
        "content": {
            "name": "career_search",
            "result": result_text,
        },
        "tool_call_id": tool_call_id,
    }

    # Convert to LangChain messages
    tool_call_lc = dreampath_to_langchain(tool_call)
    tool_result_lc = dreampath_to_langchain(tool_result)
    
    # Sleep for each role to simulate processing time
    await asyncio.sleep(5)

    return {
        "turn_messages": state.turn_messages + [tool_call, tool_result],
        "messages": [tool_call_lc, tool_result_lc],
    }
