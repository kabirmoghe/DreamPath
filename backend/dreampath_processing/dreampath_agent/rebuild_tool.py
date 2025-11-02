import asyncio

from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import (
    build_prereq_tree,
    construct_course,
    is_major_course,
)
from dreampath_processing.courses.schedule_modules.course import COMPLEMENTARY, MAJOR
from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.database.student_service import StudentDatabaseService
from dreampath_processing.dreampath_agent.build_prompts import (
    PARAMETER_COURSE_SEARCH_QUERIES_SYS,
    UPDATE_COURSE_RECOMMENDATIONS_SYS,
)
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
from dreampath_processing.dreampath_agent.node_helpers import (
    format_course_search_result,
    modify_student_profile,
)
from pydantic import BaseModel


class CourseRecommendations(BaseModel):
    courses: set[str]

def format_recommended_courses(recommended_courses: set[str], course_search_tool: CourseSearchTool) -> str:

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
    results = ""
    for result in course_search_results:
        results += "<course>\n"
        results += format_course_search_result(result)
        results += "</course>\n"

    return results

async def execute_rebuild_tool(state: DreamPathAgentState, config: dict, parameter_weights: dict[str, float] | None=None, N: int=15) -> RebuildCoursePathOutput:
    
    output = {}

    # -----------------------------------------------------
    # 1. Modify profile
    # -----------------------------------------------------
    student_db_service: StudentDatabaseService = config["configurable"]["student_db_service"]
    current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

    if not state.init_mode: # not in init mode, so we need to modify the profile to capture shift in user's interests, goals, etc.
        print("Modifying student profile...")
        modified_profile, _ = await modify_student_profile(state, config)

        # Update only the modifiable fields from ModifiedStudentProfile
        current_profile.major = modified_profile.major
        current_profile.college_interests = modified_profile.college_interests
        current_profile.post_grad_goals = modified_profile.post_grad_goals
        current_profile.career_goals = modified_profile.career_goals

        # Update output
        output["modified_profile"] = modified_profile

        # Save the complete StudentProfile to the database
        await student_db_service.save_student_profile(current_profile, config["configurable"]["user_id"])
    else:
        print("Using existing student profile...")

        # Update output (no modified profile)
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
    course_search_queries = {}
    student_name = current_profile.name

    for parameter, _ in parameter_weights.items():
        print(f"Generating course search queries for parameter: {parameter}...")
        course_search_queries[parameter], _ = await extract_structured_output_from_context(state=state, config=config, system_prompt=PARAMETER_COURSE_SEARCH_QUERIES_SYS.format(student_name=student_name, parameter=parameter.replace("_", " ").capitalize()), response_model=CourseSearchQueries, small_context=True, model="gpt-4o", verbose=True)

    # Update output
    output["course_search_queries_by_parameter"] = course_search_queries

    # -----------------------------------------------------
    # 4. Execute course search queries
    # -----------------------------------------------------
    course_search_tool: CourseSearchTool = config["configurable"]["course_search_tool"]
    course_search_results = {} # course: {parameter: {hits, course_info}}

    for parameter, queries in course_search_queries.items():
        print(f"Executing course search queries for parameter: {parameter}...")
        for query in queries.queries:
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
        score = sum(results_dict.get(parameter, 0) * parameter_weights[parameter] for parameter in parameter_weights.keys())
        scored_course_results[course] = {
            "score": score,
            "result": results_dict["result"]
        }
    
    sorted_course_results = sorted(scored_course_results.items(), key=lambda x: x[1]["score"], reverse=True)
    top_course_results = [result["result"] for _, result in sorted_course_results[:N]]

    # -----------------------------------------------------
    # 6. Update recommended courses, must-have courses
    # -----------------------------------------------------
    print("Updating recommended courses...")

    current_course_path = await student_db_service.load_course_path(config["configurable"]["user_id"])

    if current_course_path is None:
        current_course_path = None
        recommended_courses = set()
    else:
        recommended_courses = current_course_path.recommended_courses

    # Approximate number of recommended courses based on rough capacity remaining
    window_start_term = current_course_path.curr_window_start if current_course_path is not None else 0
    num_recommended_courses = int(20 * (12 - window_start_term) / 12)

    formatted_recommended_courses = format_recommended_courses(recommended_courses, course_search_tool)
    formatted_top_courses = format_deep_course_search_results(top_course_results)
    formatted_updated_course_recommendation_prompt = UPDATE_COURSE_RECOMMENDATIONS_SYS.format(student_name=student_name, recommended_courses=formatted_recommended_courses, course_search_results=formatted_top_courses, num_recommended_courses=num_recommended_courses)

    updated_recommendations, _ = await extract_structured_output_from_context(state=state, config=config, system_prompt=formatted_updated_course_recommendation_prompt, response_model=CourseRecommendations, small_context=True, model="gpt-4o", verbose=True)

    print(f"Updated recommendations: {updated_recommendations.courses}")

    # Update output
    output["updated_recommended_courses"] = updated_recommendations.courses

    # 7. Construct updated course path
    if current_course_path is None:
        course_bank = {c: construct_course(course_code=c, major=current_profile.major) for c in updated_recommendations.courses}
        new_course_path = build_course_path(updated_recommendations.courses, course_bank)
        # coursepath_agent.tools = CoursePathTools(course_path=new_course_path, major=current_profile.major)

        course_path_id = await student_db_service.save_course_path(new_course_path, config["configurable"]["user_id"])

        # Update output
        output["course_path_update_mode"] = "new"
        # No need to update config - context building queries DB live
    else:
        # Update recommended courses & must-have courses
        current_course_path.recommended_courses = updated_recommendations.courses

        # Remove windows from removed must-have courses
        for course_code in current_course_path.must_have_courses - updated_recommendations.courses:
            current_course_path.course_bank[course_code].must_have_window = None

        current_course_path.must_have_courses = current_course_path.recommended_courses & current_course_path.must_have_courses

        # Update course bank with new courses
        course_bank = current_course_path.course_bank

        for course in current_course_path.recommended_courses:

            # (Re)construct course object (important for new courses and old courses in case major has changed)
            if course not in course_bank:
                course_obj = construct_course(course_code=course, major=current_profile.major) # new course
            else:
                course_obj = course_bank[course] # keep existing course object intact but update course type if major has changed
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
                    prereq_obj.course_type = course_obj.course_type # inherit course type from parent course

                prereq_obj.is_prereq = True
                course_bank[prereq] = prereq_obj

        # Rebuild course path
        current_course_path.rebuild()
        course_path_id = await student_db_service.save_course_path(current_course_path, config["configurable"]["user_id"])

        # Update output
        output["course_path_update_mode"] = "update_existing"
        # No need to update config - context building queries DB live

    print(output)
    print(f"Saved course path with ID: {course_path_id}")

    return RebuildCoursePathOutput(**output)
    

async def main():
    student_db_service = StudentDatabaseService(get_db_connection())
    from_scratch = False
    user_id = 1

    if from_scratch:
        print("Testing with new profile...")
        # Testing with new profile
        state = DreamPathAgentState()

        student_profile = await student_db_service.load_student_profile(user_id)

        config = {
            "configurable": {
                "student_profile": student_profile,
                "course_search_tool": CourseSearchTool(),
                "student_db_service": student_db_service,
                "user_id": user_id,
            }
        }

        output = await execute_rebuild_tool(state, config)
        print(output)
        current_course_path = await student_db_service.load_course_path(user_id)
        print(current_course_path.visualize_by_term_idx())

    else:
        print("Testing with existing profile...")
        # Testing with existing course path
    
        student_profile = await student_db_service.load_student_profile(user_id)
        current_course_path = await student_db_service.load_course_path(user_id)
        example_user_career_change_intent = "I'm not really interested in SWE / ML/AI anymore as a main career path and instead want to pivot to quant research, financial modeling, or something related to that. I feel it's more lucrative and also just seems like a good option at Dartmouth."

        state = DreamPathAgentState(thread_id="1", current_user_msg=example_user_career_change_intent)

        config = {
            "configurable": {
                "student_profile": student_profile,
                "course_search_tool": CourseSearchTool(),
                "student_db_service": student_db_service,
                "user_id": user_id,
                "course_path": current_course_path,
            }
        }

        output = await execute_rebuild_tool(state, config)
        print(output)
        current_course_path = await student_db_service.load_course_path(config["configurable"]["user_id"])
        for course_code, course_obj in current_course_path.course_bank.items():
            print(f"{course_code}: {course_obj.course_title} [{course_obj.course_type}]")
            print(f"Scheduled: {course_obj.scheduled} | term_idx: {course_obj.term_idx} | must_have_window: {course_obj.must_have_window}")
            print("---")
        print(current_course_path.visualize())
        print(current_course_path.visualize_by_term_idx())

if __name__ == "__main__":
    asyncio.run(main())
    
