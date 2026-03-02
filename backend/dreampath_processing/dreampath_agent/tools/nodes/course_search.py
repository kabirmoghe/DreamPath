"""
Course search node that invokes the search agent subgraph.

This replaces the legacy single-shot query generation with an iterative
search agent that can refine queries and evaluate results.
"""

from dreampath_processing.dreampath_agent.dreampath_types import (
    DreamPathAgentState,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.search_agent.graph import build_search_agent
from dreampath_processing.dreampath_agent.search_agent.nodes.summarize import (
    render_search_summary_markdown,
)
from dreampath_processing.dreampath_agent.search_agent.search_types import SearchAgentState
from dreampath_processing.dreampath_agent.search_agent.types.course_types import (
    CourseSearchResult,
)


def format_course_search_result(course_obj: CourseSearchResult) -> str:
    """Format a single course search result for display."""
    course_str = f"Code: {course_obj.course_code}\n"
    course_str += f"Title: {course_obj.course_title}\n"
    course_str += f"Description: {course_obj.description}\n"
    course_str += f"Prereqs: {course_obj.prerequisites}\n"
    course_str += f"Dept: {course_obj.department}\n"
    course_str += f"URL: {course_obj.course_url}\n"
    return course_str


def _extract_all_course_results(final_state: dict) -> list[CourseSearchResult]:
    """
    Extract all unique CourseSearchResult objects from the search agent's final state.

    Returns deduplicated list of courses across all tasks.
    """
    all_courses = []
    seen_codes = set()

    tasks = final_state.get("tasks", [])
    for task in tasks:
        for execution in task.search_executions:
            for course in execution.output.results:
                if hasattr(course, 'course_code') and course.course_code not in seen_codes:
                    seen_codes.add(course.course_code)
                    all_courses.append(course)

    return all_courses


# Build the search agent graph once at module load
_search_agent_graph = None


def _get_search_agent():
    """Get or build the search agent graph (lazy initialization)."""
    global _search_agent_graph
    if _search_agent_graph is None:
        _search_agent_graph = build_search_agent()
    return _search_agent_graph


async def course_search_node(state: DreamPathAgentState, config, *, writer=None) -> dict:
    """
    Course search node that invokes the search agent subgraph.
    """
    from dreampath_processing.dreampath_agent.tools.schemas import CourseSearchInput

    tool_input: CourseSearchInput = state.tool_input
    search_goal = tool_input.goal

    print(f"| CourseSearchNode: invoking search agent with goal='{search_goal[:80]}...'")

    search_state = SearchAgentState(goal=search_goal, domain="course")

    # Pass writer through config for status updates
    search_config = {
        **config,
        "configurable": {
            **config.get("configurable", {}),
            "writer": writer
        }
    }

    search_agent = _get_search_agent()
    final_state = await search_agent.ainvoke(search_state, search_config)

    print(f"| CourseSearchNode: search agent completed with {len(final_state.get('tasks', []))} tasks")

    # Get structured summary and render to full markdown
    structured_summary = final_state.get("structured_summary")
    if structured_summary:
        final_summary = render_search_summary_markdown(structured_summary, verbosity=2)
    else:
        final_summary = "No results found."

    tool_call = {
        "role": "assistant",
        "content": {
            "name": "course_search",
            "arguments": {"goal": search_goal}
        },
    }

    tool_result = {
        "role": "assistant",
        "content": {
            "name": "course_search",
            "result": final_summary,
        },
    }

    tool_call_lc = dreampath_to_langchain(tool_call)
    tool_result_lc = dreampath_to_langchain(tool_result)

    return {
        "turn_messages": state.turn_messages + [tool_call, tool_result],
        "messages": [tool_call_lc, tool_result_lc],
    }


# ============================================
# UTILITY FUNCTIONS FOR REBUILD INTEGRATION
# ============================================

async def invoke_search_agent(goal: str, config: dict, domain: str = "course") -> dict:
    """
    Invoke the search agent with a goal and return the final state.

    Utility function for use by other nodes (e.g., rebuild_course_path)
    that need to run searches without the full node machinery.
    """
    search_state = SearchAgentState(goal=goal, domain=domain)
    search_agent = _get_search_agent()
    return await search_agent.ainvoke(search_state, config)


def get_top_course_codes_from_search(final_state: dict) -> list[str]:
    """Extract all top_results course codes from search agent state."""
    top_codes = []
    seen = set()

    for task in final_state.get("tasks", []):
        for code in task.top_results:
            if code not in seen:
                seen.add(code)
                top_codes.append(code)

    return top_codes


def get_all_courses_from_search(final_state: dict) -> list[CourseSearchResult]:
    """Extract all unique CourseSearchResult objects from search agent state."""
    return _extract_all_course_results(final_state)
