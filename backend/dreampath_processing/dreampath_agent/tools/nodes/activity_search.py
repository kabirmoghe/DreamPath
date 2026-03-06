"""
Activity search node that invokes the search agent subgraph with domain="activity".

Mirrors course_search_node but for clubs/activities.
Supports multiple goals — runs parallel agents and combines results.
"""

import asyncio

from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.search_agent.nodes.summarize import (
    render_search_summary_markdown,
)
from dreampath_processing.dreampath_agent.tools.nodes.course_search import invoke_search_agent
from dreampath_processing.dreampath_agent.tools.schemas import ActivitySearchInput


async def activity_search_node(state: DreamPathAgentState, config, *, writer=None) -> dict:
    """
    Activity search node that invokes the search agent subgraph.
    Supports multiple goals — runs parallel agents and combines results.
    """
    tool_input: ActivitySearchInput = state.tool_input
    goals = tool_input.goals

    print(f"| ActivitySearchNode: invoking {len(goals)} search agent(s)")

    # Pass writer through config for status updates
    search_config = {
        **config,
        "configurable": {
            **config.get("configurable", {}),
            "writer": writer
        }
    }

    # Run search agents in parallel for each goal
    search_tasks = [invoke_search_agent(goal, search_config, domain="activity") for goal in goals]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Combine summaries from all results
    summary_parts = []
    for i, (goal, result) in enumerate(zip(goals, results)):
        if isinstance(result, Exception):
            print(f"⚠️ ActivitySearchNode: goal {i + 1} failed: {result}")
            summary_parts.append(f'<search_result goal="{i + 1}">\n## Goal: {goal}\nSearch failed: {result}\n</search_result>')
            continue

        structured_summary = result.get("structured_summary")
        if structured_summary:
            rendered = render_search_summary_markdown(structured_summary, verbosity=2)
            if len(goals) > 1:
                summary_parts.append(f'<search_result goal="{i + 1}">\n## Goal: {goal}\n{rendered}\n</search_result>')
            else:
                summary_parts.append(rendered)
        else:
            summary_parts.append(f'<search_result goal="{i + 1}">\n## Goal: {goal}\nNo results found.\n</search_result>')

    final_summary = "\n\n".join(summary_parts) if summary_parts else "No results found."

    print(f"| ActivitySearchNode: completed {len(goals)} search(es)")

    tool_call_id = state.pending_tool_call["tool_call_id"]

    tool_call = {
        "role": "assistant",
        "content": {
            "name": "activity_search",
            "arguments": {"goals": goals}
        },
        "tool_call_id": tool_call_id,
    }

    tool_result = {
        "role": "tool",
        "content": {
            "name": "activity_search",
            "result": final_summary,
        },
        "tool_call_id": tool_call_id,
    }

    tool_call_lc = dreampath_to_langchain(tool_call)
    tool_result_lc = dreampath_to_langchain(tool_result)

    return {
        "turn_messages": state.turn_messages + [tool_call, tool_result],
        "messages": [tool_call_lc, tool_result_lc],
    }
