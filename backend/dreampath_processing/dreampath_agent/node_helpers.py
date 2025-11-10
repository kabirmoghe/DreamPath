import os

from dotenv import load_dotenv
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.courses.coursepath_agent.agent_v2 import CoursePathAgent, CoursePathTools
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.courses.schedule_modules.course import COMPLEMENTARY, MAJOR
from dreampath_processing.dreampath_agent.chat_prompts import (
    BUILD_OPERATIONS_SYS,
    COURSE_SEARCH_SYS,
    CRAFT_FINAL_REPLY_SYS,
    MODIFY_PROFILE_SYS,
    ORCHESTRATOR_DECISION_SYS,
)
from dreampath_processing.dreampath_agent.context_building import (
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.dreampath_types import (
    CoursePathOperations,
    CourseSearchOutput,
    CourseSearchQueries,
    CourseSearchResult,
    DreamPathAgentState,
    ModifiedStudentProfile,
    OrchestratorDecision,
    RebuildCoursePathOutput,
)
from dreampath_processing.modules.student_profile import StudentProfile
from instructor import from_openai
from openai import OpenAI

load_dotenv()

# -----------------------------------------------------
# ORCHESTRATOR NODE
# -----------------------------------------------------
async def decide_next_route(state: DreamPathAgentState, config) -> tuple[OrchestratorDecision, dict]:
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    return await extract_structured_output_from_context(state=state, config=config, system_prompt=ORCHESTRATOR_DECISION_SYS.format(student_name=student_name), response_model=OrchestratorDecision, small_context=False, model="o4-mini", task_prompt="What should happen next?", verbose=True)

# -----------------------------------------------------
# COURSE SEARCH NODE
# -----------------------------------------------------
async def determine_course_search_queries(state: DreamPathAgentState, config) -> tuple[CourseSearchQueries, dict]:
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    return await extract_structured_output_from_context(state=state, config=config, system_prompt=COURSE_SEARCH_SYS.format(student_name=student_name), response_model=CourseSearchQueries, small_context=True, model="gpt-4o")

# -----------------------------------------------------
# PLAN BUILDER NODE
# -----------------------------------------------------
async def build_operations_from_context_and_results(state: DreamPathAgentState, config) -> tuple[CoursePathOperations, dict]:
    return await extract_structured_output_from_context(state=state, config=config, system_prompt=BUILD_OPERATIONS_SYS, response_model=CoursePathOperations, small_context=True, model="gpt-4o")

# -----------------------------------------------------
# MODIFY PROFILE NODE
# -----------------------------------------------------
async def modify_student_profile(state: DreamPathAgentState, config) -> tuple[ModifiedStudentProfile, dict]:
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    return await extract_structured_output_from_context(state=state, config=config, system_prompt=MODIFY_PROFILE_SYS.format(student_name=student_name), response_model=ModifiedStudentProfile, small_context=True, model="gpt-4o", temperature=0.1)

# -----------------------------------------------------
# FINAL REPLY RENDERER NODE
# -----------------------------------------------------
async def render_final_reply(state: DreamPathAgentState, config) -> tuple[str, dict]:
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    return await extract_structured_output_from_context(state=state, config=config, system_prompt=CRAFT_FINAL_REPLY_SYS.format(student_name=student_name), response_model=str, small_context=False, model="gpt-4o", temperature=0.1)

async def render_final_reply_streaming(state: DreamPathAgentState, config, writer) -> tuple[str, dict]:
    """
    Streaming version of render_final_reply that emits tokens via writer callback.
    Uses native OpenAI ASYNC streaming instead of Instructor to enable token-by-token emission.
    """
    from langchain_core.messages import AIMessageChunk
    from dreampath_processing.dreampath_agent.context_building import build_complete_context, calculate_token_count
    from openai import AsyncOpenAI

    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    system_prompt = CRAFT_FINAL_REPLY_SYS.format(student_name=student_name)

    # Build context (same as extract_structured_output_from_context)
    messages, state_updates = await build_complete_context(state, system_prompt, config, task_prompt=None)

    # Log token count
    model = "gpt-4o"
    print(f"[ MODEL={model} | TOKEN COUNT: {calculate_token_count(messages, model)} ]")

    # Use ASYNC OpenAI client for streaming (bypass Instructor)
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Make ASYNC streaming call
    stream = await openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        stream=True
    )

    # Accumulate complete response
    full_response = ""

    # Emit tokens via writer
    import time
    start_time = time.time()
    token_count = 0

    print(f"🟡 FINALIZE: Starting ASYNC token emission loop")
    async for chunk in stream:  # ← ASYNC iteration
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_response += token
            token_count += 1

            # Show each token as it arrives
            print(f"🟡 FINALIZE: Token #{token_count} at t={time.time() - start_time:.3f}s: {repr(token)}")

            # Emit AIMessageChunk
            if writer:
                chunk_msg = AIMessageChunk(content=token)
                writer(chunk_msg)
                print(f"    ↳ writer() called")

    elapsed = time.time() - start_time
    print(f"🟡 FINALIZE: ASYNC loop completed at t={elapsed:.3f}s (emitted {token_count} tokens)")
    print(f"🟡 FINALIZE: Returning from render_final_reply_streaming()")

    return full_response, state_updates

# -----------------------------------------------------
# DETERMINE USER CONFIRMATION (MINI-HELPER)
# -----------------------------------------------------
def determine_user_confirmation(user_response: str) -> tuple[bool, dict]:

    client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": user_response}],
        response_model=bool,
        temperature=0
    )
    return response

# -----------------------------------------------------
# FORMAT ORCHESTRATOR DECISION
# -----------------------------------------------------
def format_orchestrator_decision(decision: OrchestratorDecision) -> str:
    return f"route: {decision.route}\nreason: {decision.reason}\nconfidence: {decision.confidence}\nhandoff: {decision.handoff}"

# -----------------------------------------------------
# FORMAT COURSE SEARCH OUTPUT
# -----------------------------------------------------
def format_course_search_result(course_obj: CourseSearchResult) -> str:
    course_str = f"Code: {course_obj.course_code}\n"
    course_str += f"Title: {course_obj.course_title}\n"
    course_str += f"Description: {course_obj.description}\n"
    course_str += f"Prereqs: {course_obj.prerequisites}\n"
    course_str += f"Dept: {course_obj.department}\n"
    course_str += f"URL: {course_obj.course_url}\n"

    return course_str

def format_course_search_output(output: CourseSearchOutput) -> str:

    output_str = ""

    for result in output.results:
        output_str += f"<course_search_result>\n{format_course_search_result(result)}\n</course_search_result>\n"

    return output_str

# -----------------------------------------------------
# FORMAT WORKLIST (COURSE PATH MODIFICATION OPERATIONS)
# -----------------------------------------------------
def format_worklist(worklist: list[str]) -> str:
    output_str = "<worklist>\n"
    for op in worklist:
        output_str += "Ops. awaiting execution:\n"
        output_str += f"<op>{op}</op>\n"
    output_str += "</worklist>"
    return output_str

# -----------------------------------------------------
# FORMAT AGGREGATE COURSEPATH AGENT RESULT
# -----------------------------------------------------
def format_aggregate_coursepath_agent_result(outcomes: dict[str, CoursePathAgentOutput], diff: str | None=None) -> str:
    outcomes_str = ""

    for op, outcome in outcomes.items():
        outcomes_str += f"<op_result>\n* For op '{op}': {outcome.ui_text}\n</op_result>\n"

    if diff:
        diff_str = f"<aggregate_diff>{diff}\n</aggregate_diff>"
    else:
        diff_str = ""

    return f"{outcomes_str}{diff_str}"

# -----------------------------------------------------
# FORMAT MODIFIED STUDENT PROFILE
# -----------------------------------------------------
def format_modified_student_profile(modified_profile: ModifiedStudentProfile) -> str:
    modified_profile_content = f"major: {modified_profile.major}\n"
    modified_profile_content += f"college_interests: {modified_profile.college_interests}\n"
    modified_profile_content += f"post_grad_goals: {modified_profile.post_grad_goals}\n"
    modified_profile_content += f"career_goals: {modified_profile.career_goals}\n"
    return f"<mod_result>\n{modified_profile_content}</mod_result>"

# -----------------------------------------------------
# FORMAT REBUILD COURSE PATH OUTPUT
# -----------------------------------------------------
def format_rebuild_course_path_output(output: RebuildCoursePathOutput) -> str:
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