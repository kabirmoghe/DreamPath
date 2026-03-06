"""
Legacy rebuild course path node implementation.

This file preserves the original parameter-based search approach that:
1. Generates course search queries per profile parameter (college_interests, post_grad_goals, career_goals)
2. Executes searches using direct course_search_tool.structured_hybrid_search() calls
3. Scores courses by parameter weights

This has been replaced by rebuild.py which uses the search agent for more intelligent,
iterative course discovery with task decomposition.
"""

from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import (
    build_prereq_tree,
    construct_course,
    is_major_course,
)
from dreampath_processing.courses.schedule_modules.course import COMPLEMENTARY, MAJOR
from dreampath_processing.dreampath_agent.context_building import (
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.dreampath_types import (
    CourseSearchQueries,
    CourseSearchResult,
    DreamPathAgentState,
    RebuildCoursePathOutput,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.tools.nodes.course_search import (
    format_course_search_result,
)
from dreampath_processing.dreampath_agent.tools.nodes.modify_profile import modify_student_profile
from dreampath_processing.dreampath_agent.tools.nodes.prompts import (
    PARAMETER_COURSE_SEARCH_QUERIES_SYS,
    UPDATE_COURSE_RECOMMENDATIONS_SYS,
)
from langchain_core.messages import AIMessage
from pydantic import BaseModel


class CourseRecommendations(BaseModel):
    courses: set[str]


def format_recommended_courses(recommended_courses: set[str], course_search_tool: CourseSearchTool) -> str:
    """Format recommended courses for display."""
    if len(recommended_courses) == 0:
        return "None"
    else:
        results = ""
        for course_code in recommended_courses:
            print(f"Getting course {course_code}...")
            course_result = course_search_tool.structured_get_course_by_code(course_code)
            if course_result:
                results += format_course_search_result(course_result)
            else:
                print(f"Course {course_code} not found. Skipping...")
        return results


def format_deep_course_search_results(course_search_results: list[CourseSearchResult]) -> str:
    """Format deep course search results for display."""
    results = ""
    for result in course_search_results:
        results += "<course>\n"
        results += format_course_search_result(result)
        results += "</course>\n"
    return results


def format_rebuild_course_path_output(output: RebuildCoursePathOutput) -> str:
    """Format rebuild output for context."""
    from dreampath_processing.dreampath_agent.tools.nodes.modify_profile import (
        format_modified_student_profile,
    )

    output_str = ""

    # Modified profile
    if output.modified_profile:
        output_str += f"<modify_profile>\n{format_modified_student_profile(output.modified_profile)}\n</modify_profile>\n"
    else:
        output_str += "<modify_profile>\nProfile not modified.\n</modify_profile>\n"

    # Course search queries by parameter
    if output.course_search_queries_by_parameter:
        output_str += "<course_search_by_profile_parameter>\n"
        for parameter, queries in output.course_search_queries_by_parameter.items():
            output_str += f"<{parameter}>\n"
            for query in queries.queries:
                output_str += f"<query>{query.query}</query>\n"
            output_str += f"</{parameter}>\n"
        output_str += "</course_search_by_profile_parameter>\n"

    # Updated recommended courses
    if output.updated_recommended_courses:
        output_str += f"<updated_recommended_courses>\n{output.updated_recommended_courses}\n</updated_recommended_courses>\n"

    # Course path update mode
    if output.course_path_update_mode == "new":
        output_str += "<course_path_update_mode>\nNo existing course path found. New course path constructed.\n</course_path_update_mode>\n"
    elif output.course_path_update_mode == "update_existing":
        output_str += "<course_path_update_mode>\nExisting course path updated.\n</course_path_update_mode>"

    return output_str


async def execute_rebuild_tool_legacy(
    state: DreamPathAgentState,
    config: dict,
    parameter_weights: dict[str, float] | None = None,
    N: int = 15,
    writer=None
) -> RebuildCoursePathOutput:
    """
    Legacy rebuild tool using parameter-based course search.

    Steps:
    1. Modify profile (if not init_mode)
    2. Generate course search queries per parameter
    3. Execute searches and score courses
    4. Update recommendations
    5. Build/rebuild course path
    """
    output = {}

    # Helper function to emit status updates
    def emit_status(reason: str):
        if writer:
            status_event = AIMessage(
                content="",
                additional_kwargs={
                    "event_type": "node_status",
                    "node": "rebuild_course_path",
                    "status": "node_info",
                    "next_node": "rebuild_course_path",
                    "reason": reason
                }
            )
            try:
                writer(status_event)
                print(f"🔄 REBUILD: Emitted status - rebuild_course_path: {reason}")
            except Exception as e:
                print(f"🔄 REBUILD: Error emitting status: {e}")

    # -----------------------------------------------------
    # 1. Modify profile
    # -----------------------------------------------------
    student_db_service = config["configurable"]["student_db_service"]
    current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

    if not state.init_mode:
        emit_status("Adjusting your profile")
        print("Modifying student profile...")
        modified_profile, _ = await modify_student_profile(state, config)

        # Update only the modifiable fields from ModifiedStudentProfile
        current_profile.major = modified_profile.major
        current_profile.college_interests = modified_profile.college_interests
        current_profile.post_grad_goals = modified_profile.post_grad_goals
        current_profile.career_goals = modified_profile.career_goals

        output["modified_profile"] = modified_profile

        # Save the complete StudentProfile to the database
        await student_db_service.save_student_profile(current_profile, config["configurable"]["user_id"])
    else:
        print("Using existing student profile...")
        output["modified_profile"] = None

    # -----------------------------------------------------
    # 2. Extract parameter weights, default weights
    # -----------------------------------------------------
    if parameter_weights is None:
        parameter_weights = {
            "college_interests": 1.0,
            "post_grad_goals": 1.0,
            "long_term_goal": 0.5
        }

    # -----------------------------------------------------
    # 3. For each parameter, generate 5 course search queries
    # -----------------------------------------------------
    emit_status("Performing deep course search")
    course_search_queries = {}
    student_name = current_profile.name

    for parameter, _ in parameter_weights.items():
        print(f"Generating course search queries for parameter: {parameter}...")
        course_search_queries[parameter], _ = await extract_structured_output_from_context(
            state=state,
            config=config,
            system_prompt=PARAMETER_COURSE_SEARCH_QUERIES_SYS.format(
                student_name=student_name,
                parameter=parameter.replace("_", " ").capitalize()
            ),
            response_model=CourseSearchQueries,
            small_context=True,
            model="gpt-4o",
            verbose=True
        )

    output["course_search_queries_by_parameter"] = course_search_queries

    # -----------------------------------------------------
    # 4. Execute course search queries
    # -----------------------------------------------------
    course_search_tool: CourseSearchTool = config["configurable"]["course_search_tool"]
    course_search_results = {}

    for parameter, queries in course_search_queries.items():
        print(f"Executing course search queries for parameter: {parameter}...")
        for query in queries.queries:
            print(f">>> Executing course search query: {query}...")
            search_results = course_search_tool.structured_hybrid_search(query)
            for result in search_results.results:
                if result.course_code not in course_search_results:
                    course_search_results[result.course_code] = {}
                current_hits = course_search_results[result.course_code].get(parameter, 0)
                course_search_results[result.course_code][parameter] = current_hits + 1
                course_search_results[result.course_code]["result"] = result

    # -----------------------------------------------------
    # 5. Score courses by weights, sort by score
    # -----------------------------------------------------
    print("Scoring courses...")
    scored_course_results = {}

    for course, results_dict in course_search_results.items():
        score = sum(
            results_dict.get(parameter, 0) * parameter_weights[parameter]
            for parameter in parameter_weights.keys()
        )
        scored_course_results[course] = {
            "score": score,
            "result": results_dict["result"]
        }

    sorted_course_results = sorted(
        scored_course_results.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )
    top_course_results = [result["result"] for _, result in sorted_course_results[:N]]

    # -----------------------------------------------------
    # 6. Update recommended courses, must-have courses
    # -----------------------------------------------------
    emit_status("Adjusting course recommendations")
    print("Updating recommended courses...")

    current_course_path = await student_db_service.load_course_path(config["configurable"]["user_id"])

    if current_course_path is None:
        recommended_courses = set()
    else:
        recommended_courses = current_course_path.recommended_courses

    # Approximate number of recommended courses based on rough capacity remaining
    window_start_term = current_course_path.curr_window_start if current_course_path is not None else 0
    num_recommended_courses = int(20 * (12 - window_start_term) / 12)

    formatted_recommended_courses = format_recommended_courses(recommended_courses, course_search_tool)
    formatted_top_courses = format_deep_course_search_results(top_course_results)
    formatted_updated_course_recommendation_prompt = UPDATE_COURSE_RECOMMENDATIONS_SYS.format(
        student_name=student_name,
        recommended_courses=formatted_recommended_courses,
        course_search_results=formatted_top_courses,
        num_recommended_courses=num_recommended_courses
    )

    updated_recommendations, _ = await extract_structured_output_from_context(
        state=state,
        config=config,
        system_prompt=formatted_updated_course_recommendation_prompt,
        response_model=CourseRecommendations,
        small_context=True,
        model="gpt-4o",
        verbose=True
    )

    print(f"Updated recommendations: {updated_recommendations.courses}")
    output["updated_recommended_courses"] = updated_recommendations.courses

    # -----------------------------------------------------
    # 7. Construct updated course path
    # -----------------------------------------------------
    if current_course_path is None:
        emit_status("Building CoursePath")
        course_bank = {
            c: construct_course(course_code=c, major=current_profile.major)
            for c in updated_recommendations.courses
        }
        new_course_path = build_course_path(updated_recommendations.courses, course_bank)
        course_path_id = await student_db_service.save_course_path(
            new_course_path,
            config["configurable"]["user_id"]
        )
        output["course_path_update_mode"] = "new"
    else:
        emit_status("Rebuilding CoursePath")
        # Update recommended courses & must-have courses
        current_course_path.recommended_courses = updated_recommendations.courses

        # Remove windows from removed must-have courses
        for course_code in current_course_path.must_have_courses - updated_recommendations.courses:
            current_course_path.course_bank[course_code].must_have_window = None

        current_course_path.must_have_courses = (
            current_course_path.recommended_courses & current_course_path.must_have_courses
        )

        # Update course bank with new courses
        course_bank = current_course_path.course_bank

        for course in current_course_path.recommended_courses:
            # (Re)construct course object
            if course not in course_bank:
                course_obj = construct_course(course_code=course, major=current_profile.major)
            else:
                course_obj = course_bank[course]
                course_obj.course_type = MAJOR if is_major_course(course, current_profile.major) else COMPLEMENTARY

            course_prereq_tree, course_prereqs = build_prereq_tree(course)
            course_obj.prereq_tree = course_prereq_tree
            course_bank[course] = course_obj

            # Add prereq. objects to course bank
            for prereq in course_prereqs:
                print(f"Prereq: {prereq}, parent course: {course}")
                if prereq not in course_bank:
                    prereq_obj = construct_course(course_code=prereq, hardcoded_type=course_obj.course_type)
                    if prereq_obj is None:
                        print(f"Unknown prereq course code '{prereq}'.")
                        continue
                else:
                    prereq_obj = course_bank[prereq]
                    prereq_obj.course_type = course_obj.course_type

                prereq_obj.is_prereq = True
                course_bank[prereq] = prereq_obj

        # Rebuild course path
        current_course_path.rebuild()
        course_path_id = await student_db_service.save_course_path(
            current_course_path,
            config["configurable"]["user_id"]
        )
        output["course_path_update_mode"] = "update_existing"

    print(output)
    print(f"Saved course path with ID: {course_path_id}")

    return RebuildCoursePathOutput(**output)


async def rebuild_course_path_node_legacy(state: DreamPathAgentState, config, *, writer=None) -> DreamPathAgentState:
    """
    Legacy rebuild course path node for major course path overhauls.

    Used for:
    - Initial course path creation
    - Major career/interest pivots
    - Full-scale rebuilds
    """
    output = await execute_rebuild_tool_legacy(state, config, writer=writer)

    tool_result = {
        "role": "tool",
        "content": {
            "name": "rebuild_course_path",
            "result": format_rebuild_course_path_output(output),
        },
        "tool_call_id": state.pending_tool_call["tool_call_id"],
    }

    tool_result_lc = dreampath_to_langchain(tool_result)

    return {
        "turn_messages": state.turn_messages + [tool_result],
        "require_user_confirmation": False,
        "messages": [tool_result_lc],
    }
