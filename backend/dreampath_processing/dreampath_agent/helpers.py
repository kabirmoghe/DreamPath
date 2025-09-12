from instructor import from_openai
from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from dreampath_processing.dreampath_agent.types import OrchestratorDecision, DreamPathAgentState, CoursePathOperations, CourseSearchQueries, CourseSearchOutput
from dreampath_processing.dreampath_agent.prompts import ORCHESTRATOR_DECISION_SYS, BUILD_OPERATIONS_SYS, CRAFT_FINAL_REPLY_SYS, COURSE_SEARCH_SYS
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY
from dreampath_processing.courses.coursepath_agent.agent import CoursePathTools
from dreampath_processing.courses.coursepath_agent.agent import CoursePathAgent
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.modules.student_profile import StudentProfile

load_dotenv()

client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

# -----------------------------------------------------
# Build Context
# -----------------------------------------------------
def build_messages(state: DreamPathAgentState, prompt: str):
    msgs = [{"role": "system", "content": prompt}]
    if state.summary:
        msgs.append({"role": "assistant", "content": f"Summary: ...{state.summary[-800:]}"})
    if state.recent_messages:
        msgs.extend(state.recent_messages[-10:])

    return msgs

# -----------------------------------------------------
# Baseline For Extracting Structured Output from Context
# -----------------------------------------------------
def extract_structured_output_from_context(state: DreamPathAgentState, system_prompt: str, response_model: BaseModel, model="gpt-4o-mini", temperature=0, verbose=False):
    messages = build_messages(state, system_prompt)
    if verbose:
        print("=== MESSAGES SENT TO LLM ===")
        for i, msg in enumerate(messages):
            print(f"Message {i}: {msg['role']} - {msg['content']}")#[:200]}...")
        print("=== END MESSAGES ===")
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_model=response_model,
        temperature=temperature
    )
    return response

# -----------------------------------------------------
# ORCHESTRATOR NODE
# -----------------------------------------------------
def decide_next_route(state: DreamPathAgentState, config) -> OrchestratorDecision:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, ORCHESTRATOR_DECISION_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), OrchestratorDecision)#, verbose=True)

# -----------------------------------------------------
# PLAN BUILDER NODE
# -----------------------------------------------------
def build_operations_from_context_and_results(state: DreamPathAgentState, config) -> CoursePathOperations:
    student_profile = config["configurable"]["student_profile"]
    current_term = student_profile.course_path.curr_window_start
    return extract_structured_output_from_context(state, BUILD_OPERATIONS_SYS.format(current_term=current_term), CoursePathOperations, model="gpt-4o-mini")

# -----------------------------------------------------
# COURSE SEARCH NODE
# -----------------------------------------------------
def determine_course_search_queries(state: DreamPathAgentState, config) -> CourseSearchQueries:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, COURSE_SEARCH_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), CourseSearchQueries, model="gpt-4o-mini")#, verbose=True)

# -----------------------------------------------------
# FINAL REPLY RENDERER NODE
# -----------------------------------------------------
def render_final_reply(state: DreamPathAgentState, config) -> str:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, CRAFT_FINAL_REPLY_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), str, temperature=0.1, verbose=True)


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
        recent_messages=[
            {"role": "user", "content": "Tell me more about COSC74."},
        ]
    )

    # Ex2
    state_2 = DreamPathAgentState(
        recent_messages=[
            {"role": "user", "content": "Let's add a course on israel palestine to term 10"},
        ]
    )

    # Ex3
    state_3 = DreamPathAgentState(
        recent_messages=[
            {"role": "user", "content": "find me a course on hip hop music"},
        ]
    )

    for i in range(10):
        print(f"Query {i}: {determine_course_search_queries(state_1, config)}")

    for i in range(10):
        print(f"Query {i}: {determine_course_search_queries(state_2, config)}")

    for i in range(10):
        print(f"Query {i}: {determine_course_search_queries(state_3, config)}")