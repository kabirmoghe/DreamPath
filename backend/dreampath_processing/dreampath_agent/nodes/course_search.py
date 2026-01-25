import json

from dreampath_processing.dreampath_agent.context_building import (
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.dreampath_types import (
    CourseSearchOutput,
    CourseSearchQueries,
    CourseSearchResult,
    DreamPathAgentState,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.nodes.prompts import COURSE_SEARCH_SYS


def format_course_search_result(course_obj: CourseSearchResult) -> str:
    """Format a single course search result for display."""
    course_str = f"Code: {course_obj.course_code}\n"
    course_str += f"Title: {course_obj.course_title}\n"
    course_str += f"Description: {course_obj.description}\n"
    course_str += f"Prereqs: {course_obj.prerequisites}\n"
    course_str += f"Dept: {course_obj.department}\n"
    course_str += f"URL: {course_obj.course_url}\n"
    return course_str


def format_course_search_output(output: CourseSearchOutput) -> str:
    """Format course search output for context."""
    output_str = ""
    for result in output.results:
        output_str += f"<course_search_result>\n{format_course_search_result(result)}\n</course_search_result>\n"
    return output_str


async def determine_course_search_queries(state: DreamPathAgentState, config) -> tuple[CourseSearchQueries, dict]:
    """Determine the course search queries based on user intent and context."""
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    return await extract_structured_output_from_context(
        state=state,
        config=config,
        system_prompt=COURSE_SEARCH_SYS.format(student_name=student_name),
        response_model=CourseSearchQueries,
        small_context=True,
        model="gpt-4o"
    )


async def course_search_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    Course search node that handles course lookup and semantic search.

    Supports:
    - Specific course lookups by code
    - Semantic search by topic/description
    - Filtered searches by department, prerequisites, etc.
    """
    course_search_tool: CourseSearchTool = config["configurable"]["course_search_tool"]
    queries, _ = await determine_course_search_queries(state, config)
    print(f"| CourseSearchNode: queries={queries}")

    tool_messages = []
    langchain_messages = []

    for query in queries.queries:
        # Build tool call
        tool_call = {
            "role": "assistant",
            "content": {
                "name": "course_search",
                "arguments": {
                    "queries": json.dumps(query.model_dump()),
                }
            },
        }

        tool_messages.append(tool_call)
        langchain_messages.append(dreampath_to_langchain(tool_call))

        # Execute tool call
        search_results = course_search_tool.structured_hybrid_search(query)

        tool_result = {
            "role": "assistant",
            "content": {
                "name": "course_search",
                "result": format_course_search_output(search_results),
            },
        }

        tool_messages.append(tool_result)
        langchain_messages.append(dreampath_to_langchain(tool_result))

    return {
        "turn_messages": state.turn_messages + tool_messages,
        "messages": langchain_messages,
    }
