from instructor import from_openai
from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Tuple, List
import tiktoken
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.dreampath_agent.types import (
    OrchestratorDecision, DreamPathAgentState, CoursePathOperations, CourseSearchQueries, CourseSearchOutput, ModifiedStudentProfile
)
from dreampath_processing.dreampath_agent.prompts import (
    SUMMARY_SYS_PROMPT, ORCHESTRATOR_DECISION_SYS_V2, BUILD_OPERATIONS_SYS, CRAFT_FINAL_REPLY_SYS, COURSE_SEARCH_SYS, MODIFY_PROFILE_SYS, DETERMINE_USER_CONFIRMATION_SYS
)
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
# Update Summary
# -----------------------------------------------------
def handle_summary_get_context_messages(state: DreamPathAgentState, k=20, h=10):

    # Get recent messages
    recent_start = max(len(state.messages) - k, 0)
    recent_messages = state.messages[recent_start:]

    # Get new messages to summarize
    new_messages = state.messages[state.summary_end:recent_start]
    
    state_updates = {}

    # Summarize new messages
    if len(new_messages) > h:
        print(f"Summarizing {len(new_messages)} new messages from {state.summary_end} to {recent_start}")
        new_summary = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SUMMARY_SYS_PROMPT},
                {"role": "assistant", "content": f"<summary>\n...{state.summary[-1200:]}\n</summary>"},
                {"role": "user", "content": f"<new_messages>\n{new_messages}\n</new_messages>"}

            ],
            response_model=str,
            temperature=0
        )
        new_summary_end = state.summary_end + len(new_messages)

        # Update state
        state_updates["summary"] = new_summary
        state_updates["summary_end"] = new_summary_end

        print(f"*Initiated updates to state summary*\n{new_summary}\n*[Ends at {new_summary_end}]*")

    return recent_messages, state_updates

# -----------------------------------------------------
# Build Context
# -----------------------------------------------------
def calculate_token_count(messages: list[dict], model="gpt-4o-mini"):
    """Calculate token count for messages using tiktoken's precise method that matches OpenAI's billing."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print(f"Warning: {model} is not a supported model for tiktoken. Using cl100k_base instead.")
        # Fallback to cl100k_base encoding for newer models
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # Use tiktoken's built-in function for precise token counting
    # This matches exactly how OpenAI calculates tokens for chat completions
    tokens_per_message = 3  # every message follows <|start|>{role/name}\n{content}<|end|>\n
    tokens_per_name = 1     # if there's a name, the role is omitted
    
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            if isinstance(value, str):
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
    
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

def build_messages(state: DreamPathAgentState, prompt: str):

    msgs = [{"role": "system", "content": prompt}]
    recent_messages, state_updates = handle_summary_get_context_messages(state)

    if state.summary:
        msgs.append({"role": "assistant", "content": f"Summary: ...{state.summary[-1200:]}"})

    msgs.extend(recent_messages)

    return msgs, state_updates

# -----------------------------------------------------
# Baseline For Extracting Structured Output from Context
# -----------------------------------------------------
def extract_structured_output_from_context(state: DreamPathAgentState, system_prompt: str, response_model: BaseModel, model="gpt-4o-mini", temperature=0, verbose=False, show_token_count=True):
    messages, state_updates = build_messages(state, system_prompt)
    if verbose:
        print("=== MESSAGES SENT TO LLM ===")
        for i, msg in enumerate(messages):
            print(f"Message {i}: {msg['role']} - {msg['content']}")
        print("=== END MESSAGES ===")

    if show_token_count:
        print(f"[MODEL={model} | TOKEN COUNT: {calculate_token_count(messages, model)}]")

    if model == "o3-mini":
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
        )
    else:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
            temperature=temperature
        )
    return response, state_updates

# -----------------------------------------------------
# ORCHESTRATOR NODE
# -----------------------------------------------------
def decide_next_route(state: DreamPathAgentState, config) -> Tuple[OrchestratorDecision, dict]:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, ORCHESTRATOR_DECISION_SYS_V2.format(student_name=student_name, student_profile=student_profile.__str__()), OrchestratorDecision, model="gpt-4o")

# -----------------------------------------------------
# COURSE SEARCH NODE
# -----------------------------------------------------
def determine_course_search_queries(state: DreamPathAgentState, config) -> Tuple[CourseSearchQueries, dict]:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, COURSE_SEARCH_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), CourseSearchQueries, model="gpt-4o")

# -----------------------------------------------------
# PLAN BUILDER NODE
# -----------------------------------------------------
def build_operations_from_context_and_results(state: DreamPathAgentState, config) -> Tuple[CoursePathOperations, dict]:
    student_profile = config["configurable"]["student_profile"]
    current_term = student_profile.course_path.curr_window_start
    return extract_structured_output_from_context(state, BUILD_OPERATIONS_SYS.format(current_term=current_term, student_profile=student_profile.__str__()), CoursePathOperations)

# -----------------------------------------------------
# MODIFY PROFILE NODE
# -----------------------------------------------------
def modify_student_profile(state: DreamPathAgentState, config) -> Tuple[ModifiedStudentProfile, dict]:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, MODIFY_PROFILE_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), ModifiedStudentProfile, model="gpt-4o", temperature=0.1)

# -----------------------------------------------------
# FINAL REPLY RENDERER NODE
# -----------------------------------------------------
def render_final_reply(state: DreamPathAgentState, config) -> Tuple[str, dict]:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, CRAFT_FINAL_REPLY_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), str, model="gpt-4o", temperature=0.1, verbose=True)

# -----------------------------------------------------
# DETERMINE USER CONFIRMATION (MINI-HELPER)
# -----------------------------------------------------
def determine_user_confirmation(user_response: str) -> Tuple[bool, dict]:
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
# FORMAT AGGREGATE COURSEPATH AGENT RESULT
# -----------------------------------------------------
def format_aggregate_coursepath_agent_result(outcomes: List[CoursePathAgentOutput], diff: str) -> str:
    outcomes_str = ""

    for outcome in outcomes:
        outcomes_str += f"<operation_outcome>\n{outcome.ui_text}\n</operation_outcome>\n"

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