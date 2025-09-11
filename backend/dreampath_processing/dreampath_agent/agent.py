import json
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from dreampath_processing.dreampath_agent.types import DreamPathAgentState
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.helpers import decide_next_route, build_operations_from_context_and_results, determine_course_search_queries
from dreampath_processing.dreampath_agent.helpers import render_final_reply
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY
from dreampath_processing.courses.coursepath_agent.agent import CoursePathAgent, CoursePathTools
from dreampath_processing.modules.student_profile import StudentProfile

def orchestrator_node(state: DreamPathAgentState, config) -> DreamPathAgentState:

    # print(f"Orchestrator thinking...")
    decision = decide_next_route(state, config)
    # print(f"--> Decision: {decision}")

    return {
        "route": decision.next,
    }

def course_search_node(state: DreamPathAgentState, config) -> DreamPathAgentState:

    course_search_tool: CourseSearchTool = config["configurable"]["course_search_tool"]
    queries = determine_course_search_queries(state, config)
    print(f"********** CourseSearchNode: queries={queries}")

    tool_messages = []
    for query in queries.queries:

        # Build tool call
        tool_call = {
            "role": "assistant",
            "content": json.dumps({
                "type": "tool_call",
                "name": "course_search",
                "arguments": {
                    "queries": json.dumps(query.model_dump()),
                }
            }),
        }

        tool_messages.append(tool_call)

        # Execute tool call
        search_results = course_search_tool.structured_hybrid_search(query)
        
        tool_message = {
            "role": "assistant",
            "content": json.dumps({
                "type": "tool_result",
                "name": "course_search",
                "result": json.dumps(search_results.model_dump()),
            }),
        }

        tool_messages.append(tool_message)

    return {
        "recent_messages": tool_messages,
    }
    
def plan_builder_node(state: DreamPathAgentState) -> DreamPathAgentState:
    ops = build_operations_from_context_and_results(state)
    
    return {
        "worklist": ops.operations, # List[str], e.g., ["Add QSS41 to term 6.", "Add COSC50 to term 6."]
        "cursor": 0,
        "current_cp_agent_outcomes": [],   # start fresh for this batch
    }

def course_path_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    flow: 
    - if have user_clarification (from previous run): cp_agent_input <- user_clarification
    - else: cp_agent_input = state.worklist[state.cursor]
    - then, run course_path_tool(state, cp_agent_input)


    """
    coursepath_agent: CoursePathAgent = config["configurable"]["coursepath_agent"]
    cursor = state.cursor
    outcome = None
    worklist = state.worklist

    print(f"********** CoursePathNode: worklist={worklist}, cursor={cursor}")

    tool_call = {
        "role": "assistant",
        "content": json.dumps({
            "type": "tool_call",
            "name": "course_path_agent",
            "arguments": {
                "worklist": worklist,
                "cursor": cursor
            }
        }),
    }

    if worklist and cursor < len(worklist):
        current_op = worklist[cursor]
        out = coursepath_agent.run(current_op) # execute op

        while out.status == "ask":
            # Use interrupt() function to pause and wait for user input
            user_response = interrupt(out.ui_text)

            # Continue processing with user response
            out = coursepath_agent.run(user_response)

        outcome = out
        cursor += 1

        if cursor < len(worklist):
            route = "course_path"
        else:
            route = "orchestrator"
    else:
        route = "orchestrator"

    tool_message = None
    if outcome:
        tool_message = {
                "role": "assistant",
                "content": json.dumps({
                    "type": "tool_result",
                    "name": "course_path_agent",
                    "result": json.dumps(outcome.model_dump()),
                }),
            }

    return {
        "recent_messages": [tool_call, tool_message],
        "current_cp_agent_outcomes": [outcome],
        "worklist": worklist,
        "cursor": cursor,
        "route": route,
    }

def finalize_node(state: DreamPathAgentState, config) -> DreamPathAgentState:

    reply = render_final_reply(state, config)
    return {
        "ui_reply": reply,
        "current_cp_agent_outcomes": [],
        "search_results": None,
        "recent_messages": [{"role": "assistant", "content": reply}],
    }

# ------------------------------------------------------------
# MAIN GRAPH
# ------------------------------------------------------------

g = StateGraph(DreamPathAgentState)
g.add_node("orchestrator", orchestrator_node)
g.add_node("course_search", course_search_node)
g.add_node("plan_builder", plan_builder_node)
g.add_node("course_path", course_path_node)
g.add_node("finalize", finalize_node)

g.add_edge(START, "orchestrator")

# Orchestrator to sub-nodes
def router(state: DreamPathAgentState):
    return state.route or "finalize"

g.add_conditional_edges("orchestrator", router, {
    "course_search": "course_search",
    "plan_builder": "plan_builder",
    "course_path": "course_path",
    "finalize": "finalize",
})

# Sub-nodes loop back to orchestrator-style planner
def sub_node_router(state: DreamPathAgentState):
    return state.route or "orchestrator"

g.add_edge("course_search", "orchestrator")
g.add_edge("plan_builder", "course_path")     # plan → execute directly
g.add_conditional_edges("course_path", sub_node_router, {
    "course_path": "course_path",
    "orchestrator": "orchestrator",
})

g.add_edge("finalize", END)

checkpointer = InMemorySaver()
app = g.compile(checkpointer=checkpointer)

png_graph = app.get_graph().draw_mermaid_png()
with open("my_graph.png", "wb") as f:
    f.write(png_graph)

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
    state = DreamPathAgentState()

    while True:
        current_path = tools.cp
        print(f"----------\nCoursePath (@ term={current_path.curr_window_start})")
        print(current_path.visualize())
        print("----------\n")
        user = input("You: ").strip()
        if not user: break
        try:
            state_dict = app.invoke({"major": major, "recent_messages": [{"role": "user", "content": user}]}, config)
            
            # Check if there was an interrupt
            while '__interrupt__' in state_dict:
                interrupt_info = state_dict['__interrupt__']
                # print(interrupt_info)
                interrupt_msg = interrupt_info[0].value

                # Simulate communication
                print(f"💬 ASSISTANT: {interrupt_msg}")
                user_for_interrupt = input("You: ").strip()

                # Update state (remove interrupt, add messages)
                messages_to_add = [{"role": "assistant", "content": interrupt_msg},
                                   {"role": "user", "content": user_for_interrupt}]

                state_dict = app.invoke(Command(resume=user_for_interrupt, update={"recent_messages": messages_to_add}), config)

            state = DreamPathAgentState(**state_dict)
            
            print(f"💬 ASSISTANT: {state.ui_reply or '(ok)'}")

        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()