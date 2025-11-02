from instructor import from_openai
from openai import OpenAI
import os
from typing import Optional
from dotenv import load_dotenv
from dreampath_processing.courses.coursepath_agent.types import (
    CoursePathAgentState,
    CoursePathAgentOutput,
    ExtractedOpType,
    Op,
    ExecuteOpResult,
    OP_INFO,
)
from dreampath_processing.courses.coursepath_agent.operation_tools import CoursePathTools, compute_diff, summarize_diff, snapshot_path
from dreampath_processing.courses.coursepath_agent.prompts import OP_EXTRACTOR_SYS, PARAM_EXTRACTOR_SYS
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY
from dreampath_processing.courses.course_relationship_handling import construct_course

load_dotenv()

client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

# ------------------------------------------------------------
# CONTEXT BUILDING
# ------------------------------------------------------------
def build_messages(state: CoursePathAgentState, user_input: str, prompt: str):
    # Include only short episodic summary if needed
    msgs = [{"role": "system", "content": prompt}]
    if state.history:
        msgs.append({"role": "assistant", "content": f"Summary: ...{state.history[-800:]}"})

    # Include last few turns for continuity
    if state.recent_messages:
        msgs.extend(state.recent_messages[-5:])

    # Current user input
    msgs.append({"role": "user", "content": user_input})


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
    print(f"| CPAgent Ctx:\n{messages}")
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
def render_confirm_msg(op: Op, summarized_diff: str) -> str:
    # simple template; can LLM-polish later
    return (f"Ready to apply: {op}."
            f"{summarized_diff}\n"
            f"Reply `CONFIRM` to proceed or `CANCEL`.")

def render_reschedule_msg(op: Op, summarized_diff: str) -> str:
    return (f"To apply {op}, rescheduling is required and may disrupt prior structure:"
            f"{summarized_diff}\n"
            f"Reply `CONFIRM` to proceed or `CANCEL`.")

def render_success_msg(op: Op, summarized_diff: str) -> str:
    return (f"Successfully applied: {op}."
            f"{summarized_diff}")
# ------------------------------------------------------------
# ROUTING NODES
# ------------------------------------------------------------
def clear_op_state(state: CoursePathAgentState):
    state.pending_op_type = None
    state.pending_op = None
    state.recent_messages = []
    state.trial_op_execution = None

def create_fallback_course_path(config: dict, tools: CoursePathTools):
    config["fallback_cp"] = snapshot_path(tools.cp)

def revert_to_fallback_course_path(config: dict, tools: CoursePathTools):
    tools.cp = config["fallback_cp"]

def handle_user_turn(state: CoursePathAgentState, config: dict, tools: CoursePathTools, user_input: str, require_user_confirmation: bool=True) -> CoursePathAgentOutput:
    # 1) Extract operation type (if not already done)
    if not state.pending_op_type:
        state.pending_op_type = extract_op_type(state, user_input)
    
    # 2) Extract operation
    ex_op = extract_course_op(state, user_input, state.pending_op_type)
    handle_missing_fields(state, ex_op)

    if state.missing_fields and require_user_confirmation:
        state.pending_op = ex_op  # draft
        q = f"Missing: {state.missing_fields[0]}. Please specify."
        return CoursePathAgentOutput(
            status="ask",
            ui_text=q,
            diff=None,
            error=None
        )

    # 3) Confirmation
    state.pending_op = ex_op

    # 4) If trial execution has already been performed, skip to step 5
    if state.trial_op_execution is None:
        create_fallback_course_path(config, tools)
        state.trial_op_execution = execute_course_op(state=state, op_type=state.pending_op_type, op=state.pending_op, tools=tools, force_reschedule=False)

    # 5) Trial execution of operation
    if state.trial_op_execution.ok:
        if require_user_confirmation:
            return CoursePathAgentOutput(
                status="ask",
                ui_text=render_confirm_msg(state.pending_op, summarize_diff(state.trial_op_execution.diff)),
                op_string=str(state.pending_op),
                diff=state.trial_op_execution.diff,
                error=None
            )
        else: # Simulate user confirmation for non-confirmation-required cases
            return on_user_confirm(state)

    # 6) If requires rescheduling, execute operation with force_reschedule=True
    elif state.trial_op_execution.error and state.trial_op_execution.error.get("code") == "REQUIRES_RESCHEDULE":
        state.trial_op_execution = execute_course_op(state=state, op_type=state.pending_op_type, op=state.pending_op, tools=tools, force_reschedule=True)

        if state.trial_op_execution.ok:
            if require_user_confirmation:
                return CoursePathAgentOutput(
                    status="ask",
                    ui_text=render_reschedule_msg(state.pending_op, summarize_diff(state.trial_op_execution.diff)),
                    op_string=str(state.pending_op),
                    diff=state.trial_op_execution.diff,
                    error=None
                )
            else:
                return on_user_confirm(state)
        else:
            state.history += f"\nExecution failed for {state.pending_op_type.type}: {state.trial_op_execution.error}"
            output = CoursePathAgentOutput(
                status="error",
                ui_text=f"Cannot apply {state.pending_op_type.type} | [{state.trial_op_execution.error.get('code','EXEC_FAIL')}]: {state.trial_op_execution.error}",
                diff=None,
                error=state.trial_op_execution.error
            )
            clear_op_state(state)
            return output
    else:
        state.history += f"\nExecution failed for {state.pending_op_type.type}: {state.trial_op_execution.error}"
        output = CoursePathAgentOutput(
            status="error",
            ui_text=f"Error [{state.trial_op_execution.error.get('code','EXEC_FAIL')}]: {state.trial_op_execution.error}",
            diff=None,
            error=state.trial_op_execution.error
        )
        clear_op_state(state)
        return output

def on_user_confirm(state: CoursePathAgentState) -> CoursePathAgentOutput:
    # Optimistic lock
    op = state.pending_op
    attempt = state.trial_op_execution
    
    # Assume at this point attempt.ok is True because we already checked in handle_user_turn
    state.history += f"\nApplied: {op}."
    clear_op_state(state)

    return CoursePathAgentOutput(
        status="execute",
        ui_text=render_success_msg(op, summarize_diff(attempt.diff)),
        diff=attempt.diff,
        error=None
    )

def on_user_cancel(state: CoursePathAgentState, config: dict, tools: CoursePathTools) -> CoursePathAgentOutput:
    revert_to_fallback_course_path(config, tools)
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
    def __init__(self, tools: Optional[CoursePathTools]=None, require_user_confirmation: bool=True, config: Optional[dict]={}):
        self.state = CoursePathAgentState()
        self.config = config
        self.tools = tools
        self.require_user_confirmation = require_user_confirmation

    def save_previous_course_path(self):
        self.tools.previous_cp = snapshot_path(self.tools.cp)

    def revert_to_previous_course_path(self):
        self.tools.cp = self.tools.previous_cp

    def get_diff_from_previous_course_path(self) -> str:
        diff = compute_diff(self.tools.previous_cp, self.tools.cp)
        return summarize_diff(diff)

    def run(self, text: str) -> CoursePathAgentOutput:
        print(f"Recent messages: {self.state.recent_messages}")

        # Route based on whether we’re waiting for a confirm
        if self.state.pending_op and text.strip().upper() == "CONFIRM":
            out = on_user_confirm(state=self.state)
        elif self.state.pending_op and text.strip().upper() == "CANCEL":
            out = on_user_cancel(state=self.state, config=self.config, tools=self.tools)
        else:
            out = handle_user_turn(state=self.state, config=self.config, tools=self.tools, user_input=text, require_user_confirmation=self.require_user_confirmation)

        # update tiny conversational memory 
        self.state.recent_messages.append({"role":"user", "content": text})
        self.state.recent_messages.append({"role":"assistant", "content": out.ui_text})
        # TODO: persist state (plan_id, plan_version, pending_op, etc.)
        
        return out
    
if __name__ == "__main__":
    major = 'Computer Science'
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

    # Run agent
    print("CoursePathAgent ready. Type 'quit' to exit.\n")

    current_path = tools.cp
    print(current_path.visualize_by_term_idx())

    # --- Main Loop ---
    while True:
        print(f"----------\nCoursePath (@ term={test_course_path.curr_window_start})")
        # print("Recommended courses: ", current_path.recommended_courses)
        # print("Prereq Graph: ", current_path.prereq_graph)
        # print("Lingering courses: ", current_path.lingering_courses)
        print("----------\n")

        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break

        # Pass input to agent, get back a response
        response = agent.run(user_input)
        print(f"Agent: {response.ui_text}")
        
        current_path = tools.cp
        if response.status != "ask":
            # print(current_path.visualize())
            print(current_path.visualize_by_term_idx())