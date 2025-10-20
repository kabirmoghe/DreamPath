from typing import Optional, Dict, List, Set
from pydantic import BaseModel
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY
from dreampath_processing.courses.course_relationship_handling import is_major_course, construct_course, build_prereq_tree
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.modules.student_profile import StudentProfile
from dreampath_processing.dreampath_agent.types import DreamPathAgentState, CourseSearchQueries, CourseSearchResult, RebuildCoursePathOutput
from dreampath_processing.dreampath_agent.node_helpers import modify_student_profile, format_course_search_result
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.build_prompts import PARAMETER_COURSE_SEARCH_QUERIES_SYS, UPDATE_COURSE_RECOMMENDATIONS_SYS
from dreampath_processing.dreampath_agent.context_building import extract_structured_output_from_context
from dreampath_processing.courses.schedule_modules.course_path import CoursePath

class CourseRecommendations(BaseModel):
    courses: Set[str]

def format_recommended_courses(recommended_courses: Set[str], course_search_tool: CourseSearchTool) -> str:

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

def format_deep_course_search_results(course_search_results: List[CourseSearchResult]) -> str:
    results = ""
    for result in course_search_results:
        results += f"<course>\n"
        results += format_course_search_result(result)
        results += f"</course>\n"

    return results

def execute_rebuild_tool(state: DreamPathAgentState, config: dict, parameter_weights: Optional[Dict[str, float]]=None, from_scratch: bool=True, N: int=15) -> RebuildCoursePathOutput:
    
    output = {}

    # -----------------------------------------------------
    # 1. Modify profile
    # -----------------------------------------------------
    current_profile = config["configurable"]["student_profile"]

    if not from_scratch:
        print("Modifying student profile...")
        modified_profile, _ = modify_student_profile(state, config)

        current_profile.major = modified_profile.major
        current_profile.college_interests = modified_profile.college_interests
        current_profile.post_grad_goals = modified_profile.post_grad_goals
        current_profile.career_goals = modified_profile.career_goals

        # Update output
        output["modified_profile"] = modified_profile
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
    student_name = config["configurable"]["student_profile"].name

    for parameter, _ in parameter_weights.items():
        print(f"Generating course search queries for parameter: {parameter}...")
        course_search_queries[parameter], _ = extract_structured_output_from_context(state=state, config=config, system_prompt=PARAMETER_COURSE_SEARCH_QUERIES_SYS.format(student_name=student_name, parameter=parameter.replace("_", " ").capitalize()), response_model=CourseSearchQueries, small_context=True, model="gpt-4o", verbose=True)

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

    if current_profile.course_path is None:
        recommended_courses = set()
    else:
        recommended_courses = current_profile.course_path.recommended_courses

    # Approximate number of recommended courses based on rough capacity remaining
    window_start_term = current_profile.course_path.curr_window_start if current_profile.course_path is not None else 0
    num_recommended_courses = int(20 * (12 - window_start_term) / 12)

    formatted_recommended_courses = format_recommended_courses(recommended_courses, course_search_tool)
    formatted_top_courses = format_deep_course_search_results(top_course_results)
    formatted_updated_course_recommendation_prompt = UPDATE_COURSE_RECOMMENDATIONS_SYS.format(student_name=student_name, recommended_courses=formatted_recommended_courses, course_search_results=formatted_top_courses, num_recommended_courses=num_recommended_courses)

    updated_recommendations, _ = extract_structured_output_from_context(state=state, config=config, system_prompt=formatted_updated_course_recommendation_prompt, response_model=CourseRecommendations, small_context=True, model="gpt-4o", verbose=True)

    print(f"Updated recommendations: {updated_recommendations.courses}")

    # Update output
    output["updated_recommended_courses"] = updated_recommendations.courses

    # 7. Construct updated course path
    if current_profile.course_path is None:
        course_bank = {c: construct_course(course_code=c, major=current_profile.major) for c in updated_recommendations.courses}
        new_course_path = build_course_path(updated_recommendations.courses, course_bank)
        current_profile.course_path = new_course_path

        # Update output
        output["course_path_update_mode"] = "new"
    else:
        current_course_path: CoursePath = current_profile.course_path
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

        # Update output
        output["course_path_update_mode"] = "update_existing"

    print(output)

    return RebuildCoursePathOutput(**output)
    
if __name__ == "__main__":

    # Testing with no existing course path
    # state = DreamPathAgentState()

    # config = {
    #     "configurable": {
    #         "student_profile": StudentProfile(name="Kabir Moghe", major="Computer Science", college_interests="I want to hone my skills in AI/ML and deep learning, with potental implications like social sciences. I also want to explore international relations and current events (specifically courses on Israel / Palestine, diplomacy); ", post_grad_goals="work hands on as a data scientists and engineer at a tech company or startup, be knowledgeable about data security/privacy, etc.", career_goals="Become a CDO or hands on CEO developing a b2b saas platform for data aggregation across different BI tools."),
    #         "course_search_tool": CourseSearchTool(),
    #     }
    # }

    # output = execute_rebuild_tool(state, config)
    # print(output)
    # print(config["configurable"]["student_profile"].course_path.visualize_by_term_idx())

    # Testing with existing course path
    major = 'Computer Science'
    # removed: 'COSC89.17', 'COSC89.19', 'COSC89.20', 'COSC89.28'
    major_courses = {'COSC89.27', 'COSC55', 'COSC35', 'COSC62', 'COSC69.17', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}
    
    # Construct recommended courses set and course bank
    recommended_courses = major_courses | complementary_courses
    course_bank = {c: construct_course(course_code=c, major=major) for c in recommended_courses}

    # Build initial course path + course bank updated with prereqs + scheduling info
    test_course_path = build_course_path(recommended_courses, course_bank)
    test_course_path.curr_window_start = 6 # Example

    student_profile = StudentProfile(name="Kabir Moghe", major=major, college_interests="I want to hone my skills in AI/ML and deep learning, with potental implications like social sciences. I also want to explore international relations and current events (specifically courses on Israel / Palestine, diplomacy); ", post_grad_goals="work hands on as a data scientists and engineer at a tech company or startup, be knowledgeable about data security/privacy, etc.", career_goals="Become a CDO or hands on CEO developing a b2b saas platform for data aggregation across different BI tools.", course_path=test_course_path)

    example_user_career_change_intent = "I'm not really interested in SWE / ML/AI anymore as a main career path and instead want to pivot to quant research, financial modeling, or something related to that. I feel it's more lucrative and also just seems like a good option at Dartmouth."

    state = DreamPathAgentState(thread_id="1", current_user_msg=example_user_career_change_intent)

    config = {
        "configurable": {
            "student_profile": student_profile,
            "course_search_tool": CourseSearchTool(),
        }
    }

    from_scratch = student_profile.course_path is None

    output = execute_rebuild_tool(state, config, from_scratch=from_scratch)
    print(output)
    for course_code, course_obj in config["configurable"]["student_profile"].course_path.course_bank.items():
        print(f"{course_code}: {course_obj.course_title} [{course_obj.course_type}]")
        print(f"Scheduled: {course_obj.scheduled} | term_idx: {course_obj.term_idx} | must_have_window: {course_obj.must_have_window}")
        print("---")
    print(config["configurable"]["student_profile"].course_path.visualize())
    print(config["configurable"]["student_profile"].course_path.visualize_by_term_idx())

