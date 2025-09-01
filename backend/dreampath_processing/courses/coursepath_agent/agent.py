from instructor import from_openai
from openai import OpenAI
import os
from dotenv import load_dotenv
from dreampath_processing.courses.coursepath_agent.types import (
    CoursePathAgentState,
    CoursePathAgentOutput,
    ExtractedOpType,
    Op,
    ExecuteOpResult,
    OP_INFO,
)
from dreampath_processing.courses.coursepath_agent.operation_tools import CoursePathTools, summarize_diff
from dreampath_processing.courses.coursepath_agent.prompts import OP_EXTRACTOR_SYS, PARAM_EXTRACTOR_SYS
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.schedule_modules.course import Course, MAJOR, COMPLEMENTARY

load_dotenv()

client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

# ------------------------------------------------------------
# CONTEXT BUILDING
# ------------------------------------------------------------
def build_messages(state: CoursePathAgentState, user_input: str, prompt: str):
    # Include only short episodic summary if needed
    msgs = [{"role": "system", "content": prompt}]
    if state.summary:
        msgs.append({"role": "assistant", "content": f"Summary: ...{state.summary[-800:]}"})

    # Include last few turns for continuity
    if state.recent_messages:
        msgs.extend(state.recent_messages[-4:])

    # Current user input
    msgs.append({"role": "user", "content": user_input})

    # print(f"~~~\nSummary: {state.summary}\n~~~\n")

    return msgs

# ------------------------------------------------------------
# OPERATION TYPE / PARAMETER EXTRACTION
# ------------------------------------------------------------
def extract_op_type(state: CoursePathAgentState, user_input: str) -> ExtractedOpType:
    messages = build_messages(state=state, user_input=user_input, prompt=OP_EXTRACTOR_SYS)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        response_model=ExtractedOpType,
        temperature=0
    )
    return response

# Extract operation from user input
def extract_course_op(state: CoursePathAgentState, user_input: str, op_type: ExtractedOpType) -> Op:
    # Map op type to op class
    extraction_model = OP_INFO[op_type.type]['extraction_model']
    messages = build_messages(state=state, user_input=user_input, prompt=PARAM_EXTRACTOR_SYS.format(op_type=op_type.type))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        response_model=extraction_model,
        temperature=0.1
    )
    
    # print(f"Pending Op: {response}")
    return response

def handle_missing_fields(state: CoursePathAgentState, op: Op):
    op_type = state.pending_op_type.type
    missing_fields = [field for field in OP_INFO[op_type]['required_fields'] if not getattr(op, field)]
    alternative_fields = OP_INFO[op_type]['alternative_fields']
    for field in alternative_fields:
        if getattr(op, field):
            alternative_fields = []
            break

    missing_fields.extend(alternative_fields)
    state.missing_fields = missing_fields

# ------------------------------------------------------------
# OPERATION EXECUTION / VALIDATION
# ------------------------------------------------------------
def execute_course_op(state: CoursePathAgentState, op_type: ExtractedOpType, op: Op, tools: CoursePathTools, force_reschedule: bool=False) -> ExecuteOpResult:
    if force_reschedule:
        op.reschedule = True

    return tools.execute(op_type=op_type, op=op)

# TODO: Placeholder
def validate_op(state: CoursePathAgentState, op: Op) -> bool:
    return {"ok": True, "error": None}

# ------------------------------------------------------------
# RENDERING
# ------------------------------------------------------------
def render_confirm_msg(op: Op, target_version: int) -> str:
    # simple template; you can LLM-polish later
    return (f"Ready to apply: {op}. "
            f"Reply `CONFIRM` to proceed or `CANCEL`.")

def render_reschedule_msg(op: Op) -> str:
    return (f"To apply {op}, rescheduling is required and may disrupt prior structure. "
            f"Reply `CONFIRM RESCHEDULE` to proceed, or `CANCEL`.")

# ------------------------------------------------------------
# ROUTING NODES
# ------------------------------------------------------------
def clear_op_state(state: CoursePathAgentState):
    state.pending_op_type = None
    state.pending_op = None

def handle_user_turn(state: CoursePathAgentState, user_input: str) -> CoursePathAgentOutput:
    # 1) Extract operation type (if not already done)
    if not state.pending_op_type:
        state.pending_op_type = extract_op_type(state, user_input)
    
    # 2) Extract operation
    ex_op = extract_course_op(state, user_input, state.pending_op_type)
    handle_missing_fields(state, ex_op)

    if state.missing_fields:
        state.pending_op = ex_op  # draft
        q = f"Missing: {state.missing_fields[0]}. Please specify."
        return q

    # 3) Confirmation
    state.pending_op = ex_op

    # 4) Structure output: intent confirmation
    return CoursePathAgentOutput(
        status="ask",
        ui_text=render_confirm_msg(ex_op, target_version=state.plan_version),
        diff=None,
        error=None
    )

def on_user_confirm(state: CoursePathAgentState, tools: CoursePathTools, user_input: str) -> CoursePathAgentOutput:
    # Optimistic lock
    op_type = state.pending_op_type
    op = state.pending_op
    attempt = execute_course_op(state=state, op_type=op_type, op=op, tools=tools, force_reschedule=False)
    
    if attempt.ok:
        state.summary += f"\nApplied: {op}."
        clear_op_state(state)

        return CoursePathAgentOutput(
            status="execute",
            ui_text=summarize_diff(attempt.diff),
            diff=attempt.diff,
            error=None
        )

    if attempt.error and attempt.error.get("code") == "REQUIRES_RESCHEDULE":
        state.summary += f"\nAttempted to apply but rescheduling required: {op}."

        return CoursePathAgentOutput(
            status="ask",
            ui_text=render_reschedule_msg(op),
            diff=None,
            error=None
        )

    clear_op_state(state)
    state.summary += f"\nExecution failed for {op_type.type}: {attempt.error}"
    return CoursePathAgentOutput(
        status="error",
        ui_text=f"Error [{attempt.error.get('code','EXEC_FAIL')}]: {attempt.error}",
        diff=None,
        error=attempt.error
    )

def on_user_force(state: CoursePathAgentState, tools: CoursePathTools, user_input: str) -> CoursePathAgentOutput:
    op_type = state.pending_op_type
    op = state.pending_op
    op.reschedule = True
    forced = execute_course_op(state=state, op_type=op_type, op=op, tools=tools, force_reschedule=True)

    if forced.ok:
        state.pending_op_type = None
        state.pending_op = None
        state.summary += f"\nApplied via force: {op}."
        return CoursePathAgentOutput(
            status="execute",
            ui_text=summarize_diff(forced.diff),
            diff=forced.diff,
            error=None
        )

    clear_op_state(state)
    return CoursePathAgentOutput(
        status="error",
        ui_text=f"Error [{forced.error.get('code','FORCE_EXEC_FAIL')}]: {forced.error}",
        diff=None,
        error=forced.error
    )

def on_user_cancel(state: CoursePathAgentState, tools: CoursePathTools, user_input: str) -> str:
    clear_op_state(state)
    return CoursePathAgentOutput(
        status="cancel",
        ui_text="Operation cancelled.",
        diff=None,
        error=None
    )

# ------------------------------------------------------------
# MAIN CONTROLLER
# ------------------------------------------------------------
class CoursePathAgent:
    def __init__(self, tools: CoursePathTools):
        self.state = CoursePathAgentState(thread_id="", plan_id="", plan_version=0, pending_op=None, facts={}, summary="", recent_messages=[])
        self.tools = tools

    def run(self, text: str) -> CoursePathAgentOutput:
        # Route based on whether we’re waiting for a confirm
        if self.state.pending_op and text.strip().upper() == "CONFIRM":
            out = on_user_confirm(state=self.state, tools=self.tools, user_input=text)
        elif self.state.pending_op and text.strip().upper() == "CONFIRM RESCHEDULE":
            out = on_user_force(state=self.state, tools=self.tools, user_input=text)
        elif self.state.pending_op and text.strip().upper() == "CANCEL":
            out = on_user_cancel(state=self.state, tools=self.tools, user_input=text)
        else:
            out = handle_user_turn(state=self.state, user_input=text)

        # update tiny conversational memory if you want
        self.state.recent_messages.append({"role":"user", "content": text})
        self.state.recent_messages.append({"role":"assistant", "content": out.ui_text})
        # persist state (plan_id, plan_version, pending_op, etc.)
        return out
    
if __name__ == "__main__":
    major_name = 'Computer Science'
    major_courses = {'COSC89.27', 'COSC55', 'COSC35', 'COSC62', 'COSC69.17', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}
    
    # Construct recommended courses set and course bank
    recommended_courses = major_courses | complementary_courses
    course_bank = {c: Course(course_code=c, course_type=MAJOR if c in major_courses else COMPLEMENTARY) for c in recommended_courses}

    # Build initial course path + course bank updated with prereqs + scheduling info
    test_course_path = build_course_path(recommended_courses, course_bank)
    test_course_path.curr_window_start = 6 # Example

    # Build agent
    tools = CoursePathTools(course_path=test_course_path, major_name=major_name)
    agent = CoursePathAgent(tools=tools)

    # Run agent
    print("CoursePathAgent ready. Type 'quit' to exit.\n")

    # --- Main Loop ---
    while True:
        print(f"----------\nCoursePath (@ term={test_course_path.curr_window_start})")
        current_path = tools.cp
        print(current_path)
        print("----------\n")

        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break

        # Pass input to agent, get back a response
        response = agent.run(user_input)
        print(f"Agent: {response.ui_text}")