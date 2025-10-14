from instructor import from_openai
from openai import OpenAI
from dotenv import load_dotenv
import os
from typing import Tuple, Dict, List
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.dreampath_agent.types import (
    OrchestratorDecision, DreamPathAgentState, CoursePathOperations, CourseSearchQueries, CourseSearchOutput, ModifiedStudentProfile
)
from dreampath_processing.dreampath_agent.chat_prompts import (
    ORCHESTRATOR_DECISION_SYS, BUILD_OPERATIONS_SYS, CRAFT_FINAL_REPLY_SYS, COURSE_SEARCH_SYS, MODIFY_PROFILE_SYS, DETERMINE_USER_CONFIRMATION_SYS
)
from dreampath_processing.dreampath_agent.context_building import extract_structured_output_from_context
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY
from dreampath_processing.courses.coursepath_agent.agent_v2 import CoursePathTools
from dreampath_processing.courses.coursepath_agent.agent_v2 import CoursePathAgent
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.modules.student_profile import StudentProfile

load_dotenv()

# -----------------------------------------------------
# ORCHESTRATOR NODE
# -----------------------------------------------------
def decide_next_route(state: DreamPathAgentState, config) -> Tuple[OrchestratorDecision, dict]:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state=state, config=config, system_prompt=ORCHESTRATOR_DECISION_SYS.format(student_name=student_name), response_model=OrchestratorDecision, small_context=False, model="o4-mini", task_prompt="What should happen next?")

# -----------------------------------------------------
# COURSE SEARCH NODE
# -----------------------------------------------------
def determine_course_search_queries(state: DreamPathAgentState, config) -> Tuple[CourseSearchQueries, dict]:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state=state, config=config, system_prompt=COURSE_SEARCH_SYS.format(student_name=student_name), response_model=CourseSearchQueries, small_context=True, model="gpt-4o")

# -----------------------------------------------------
# PLAN BUILDER NODE
# -----------------------------------------------------
def build_operations_from_context_and_results(state: DreamPathAgentState, config) -> Tuple[CoursePathOperations, dict]:
    student_profile = config["configurable"]["student_profile"]
    current_term = student_profile.course_path.curr_window_start
    return extract_structured_output_from_context(state=state, config=config, system_prompt=BUILD_OPERATIONS_SYS.format(current_term=current_term), response_model=CoursePathOperations, small_context=True, model="gpt-4o")

# -----------------------------------------------------
# MODIFY PROFILE NODE
# -----------------------------------------------------
def modify_student_profile(state: DreamPathAgentState, config) -> Tuple[ModifiedStudentProfile, dict]:
    print("CALLING MODIFY PROFILE NODE")
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state=state, config=config, system_prompt=MODIFY_PROFILE_SYS.format(student_name=student_name), response_model=ModifiedStudentProfile, small_context=True, model="gpt-4o", temperature=0.1)

# -----------------------------------------------------
# FINAL REPLY RENDERER NODE
# -----------------------------------------------------
def render_final_reply(state: DreamPathAgentState, config) -> Tuple[str, dict]:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state=state, config=config, system_prompt=CRAFT_FINAL_REPLY_SYS.format(student_name=student_name), response_model=str, small_context=False, model="gpt-4o", temperature=0.1)

# -----------------------------------------------------
# DETERMINE USER CONFIRMATION (MINI-HELPER)
# -----------------------------------------------------
def determine_user_confirmation(user_response: str) -> Tuple[bool, dict]:

    client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": user_response}],
        response_model=bool,
        temperature=0
    )
    return response

# -----------------------------------------------------
# FORMAT COURSE SEARCH OUTPUT
# -----------------------------------------------------
def format_course_search_output(output: CourseSearchOutput) -> str:
    output_str = "<course_search_results>\n"

    for result in output.results:
        output_str += f"<course_search_result>\n"
        output_str += f"Course Code: {result.course_code}\n"
        output_str += f"Course Title: {result.course_title}\n"
        output_str += f"Description: {result.description}\n"
        output_str += f"Prerequisites: {result.prerequisites}\n"
        output_str += f"Department: {result.department}\n"
        output_str += f"Course URL: {result.course_url}\n"
        output_str += f"</course_search_result>\n"

    output_str += "</course_search_results>"

    return output_str

# -----------------------------------------------------
# FORMAT WORKLIST (COURSE PATH MODIFICATION OPERATIONS)
# -----------------------------------------------------
def format_worklist(worklist: List[str]) -> str:
    output_str = "<plan_builder_worklist>\n"
    for op in worklist:
        output_str += "Awaiting execution:"
        output_str += f"<operation>\n{op}\n</operation>\n"
    output_str += "</plan_builder_worklist>"
    return output_str

# -----------------------------------------------------
# FORMAT AGGREGATE COURSEPATH AGENT RESULT
# -----------------------------------------------------
def format_aggregate_coursepath_agent_result(outcomes: Dict[str, CoursePathAgentOutput], diff: str) -> str:
    outcomes_str = ""

    for op, outcome in outcomes.items():
        outcomes_str += f"<operation_outcome>\n* For operation '{op}': {outcome.ui_text}\n</operation_outcome>\n"

    diff_str = f"<aggregate_diff>\n{diff}\n</aggregate_diff>\n"

    return f"<coursepath_agent_result>\n{outcomes_str}\n{diff_str}\n</coursepath_agent_result>"

if __name__ == "__main__":
    # Set up course path agent
    major = 'Computer Science'
    # removed: 'COSC89.17', 'COSC89.19', 'COSC89.20', 'COSC89.28'
    major_courses = {'COSC89.27', 'COSC55', 'COSC35', 'COSC62', 'COSC69.17', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}
    
    # Construct recommended courses set and course bank
    recommended_courses = major_courses | complementary_courses
    course_bank = {c: construct_course(course_code=c, hardcoded_type=MAJOR if c in major_courses else COMPLEMENTARY) for c in recommended_courses}

    # Build initial course path + course bank updated with prereqs + scheduling info
    test_course_path = build_course_path(recommended_courses, course_bank)
    test_course_path.curr_window_start = 6 # Example

    # Build agent
    tools = CoursePathTools(course_path=test_course_path, major=major)
    agent = CoursePathAgent(tools=tools)
    course_search_tool = CourseSearchTool()

    student_profile = StudentProfile(
        name="Kabir Moghe",
        major="Computer Science",
        college_interests="I want to focus on international relations and current events (specifically courses on Israel / Palestine, diplomacy); I want to dabble in AI and data science for social sciences",
        post_grad_goals="work hands on as a data scientists and engineer at a tech company or startup, be knowledgeable about data security/privacy, etc.",
        career_goals="Become a CDO or hands on CEO developing a b2b saas platform for data aggregation across different BI tools.",
        course_path=tools.cp,
    )
    config = {"configurable": {"thread_id": "1", "coursepath_agent": agent, "student_profile": student_profile, "course_search_tool": course_search_tool}}

    # Ex1
    state_1 = DreamPathAgentState(
        messages=[
            {"role": "user", "content": "Can you tell me more about cosc62"},
        ]
    )

    # Ex2
    state_2 = DreamPathAgentState(
        messages=[
            {"role": "user", "content": "Let's add a course on israel palestine to term 10"},
        ]
    )

    # Ex3
    state_3 = DreamPathAgentState(
        messages=[
            {"role": "user", "content": "find me a course on hip hop music"},
        ]
    )

    for i in range(10):
        print(f"Query {i}: {determine_course_search_queries(state_1, config)}")

    for i in range(10):
        print(f"Query {i}: {determine_course_search_queries(state_2, config)}")

    for i in range(10):
        print(f"Query {i}: {determine_course_search_queries(state_3, config)}")