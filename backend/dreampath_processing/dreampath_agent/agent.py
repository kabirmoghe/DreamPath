import json
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from dreampath_processing.dreampath_agent.types import DreamPathAgentState, CourseSearchOutput
from dreampath_processing.dreampath_agent.helpers import decide_next_route, build_operations_from_context_and_results
from dreampath_processing.courses.semantic_course_search import get_courses_for_topic
from dreampath_processing.dreampath_agent.helpers import render_final_reply
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.schedule_modules.course import Course, MAJOR, COMPLEMENTARY
from dreampath_processing.courses.coursepath_agent.agent import CoursePathAgent, CoursePathTools

def orchestrator_node(state: DreamPathAgentState) -> DreamPathAgentState:

    print(f"Orchestrator thinking...")
    decision = decide_next_route(state)
    print(f"--> Decision: {decision}")

    return {
        "route": decision.next,
        "topics": decision.topics,
        "handoff": decision.handoff
    }

def course_search_node(state: DreamPathAgentState) -> DreamPathAgentState:

    topic = state.topics.pop(0)
    
    tool_call = {
        "role": "assistant",
        "content": json.dumps({
            "type": "tool_call",
            "name": "course_search",
            "arguments": {
                "topic": topic,
                "major": state.major,
                "num_courses": 3,
            }
        }),
    }

    majors, comps = get_courses_for_topic(topic, major=state.major, num_courses=3)
    
    # Normalize to a flat list of dicts
    search_results_dict = {"topic": topic, "results": majors + comps}
    search_results = CourseSearchOutput(**search_results_dict)
    tool_message = {
        "role": "assistant",
        "content": json.dumps({
            "type": "tool_result",
            "name": "course_search",
            "result": json.dumps(search_results.model_dump()),
        }),
    }

    return {
        "recent_messages": [tool_call, tool_message],
        "search_results": CourseSearchOutput(**search_results_dict),
        "handoff": {}
    }
    
def plan_builder_node(state: DreamPathAgentState) -> DreamPathAgentState:
    ops = build_operations_from_context_and_results(state)
    
    return {
        "worklist": ops.operations, # List[str], e.g., ["Add QSS41 to term 6.", "Add COSC50 to term 6."]
        "cursor": 0,
        "current_cp_agent_outcomes": [],   # start fresh for this batch
        "handoff": {},
    }

def course_path_node_old(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    flow: 
    - if have user_clarification (from previous run): cp_agent_input <- user_clarification
    - else: cp_agent_input = state.worklist[state.cursor]
    - then, run course_path_tool(state, cp_agent_input)


    """
    coursepath_agent: CoursePathAgent = config["configurable"]["coursepath_agent"]
    cursor = state.cursor
    outcomes = state.current_cp_agent_outcomes or []
    worklist = state.worklist

    print(f"********** CoursePathNode: worklist={worklist}, cursor={cursor}")

    tool_call = {
        "role": "assistant",
        "content": json.dumps({
            "type": "tool_call",
            "name": "course_path_agent",
            "arguments": {
                "worklist": worklist,
            }
        }),
    }

    while worklist and cursor < len(worklist):
        current_op = worklist[cursor]
        print(f"********** current_op={current_op}")
        out = coursepath_agent.run(current_op) # execyte io

        while out.status == "ask":
            # Use interrupt() function to pause and wait for user input

            print("BEFORE INTERRUPT")
            user_response = interrupt(out.ui_text)
            print(f"********** user_response={user_response}")

            # Continue processing with user response
            print("AFTER INTERRUPT")
            out = coursepath_agent.run(user_response)

        outcomes.append(out)    
        cursor += 1

    tool_messages = []
    if outcomes:
        for outcome in outcomes:
            tool_messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "type": "tool_result",
                    "name": "course_path_agent",
                    "result": json.dumps(outcome.model_dump()),
                }),
            })

    return {
        "recent_messages": [tool_call] + tool_messages,
        "current_cp_agent_outcomes": outcomes,
        "worklist": [],
        "cursor": cursor,
        "handoff": {},
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
        print(f"********** current_op={current_op}")
        out = coursepath_agent.run(current_op) # execute op

        print(f"********** out={out}")

        while out.status == "ask":
            # Use interrupt() function to pause and wait for user input
            print("BEFORE INTERRUPT")
            user_response = interrupt(out.ui_text)
            print(f"********** user_response={user_response}")

            # Continue processing with user response
            print("AFTER INTERRUPT")
            out = coursepath_agent.run(user_response)

            print(f"********** out after interrupt={out}")

        outcome = out
        cursor += 1

        if cursor < len(worklist):
            route = "course_path"
        else:
            route = "orchestrator"
    else:
        route = "orchestrator"

    print(f"********** route={route}")

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
        "handoff": {},
        "is_user_clarification": False
    }

def finalize_node(state: DreamPathAgentState) -> DreamPathAgentState:

    reply = render_final_reply(state)
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

def router(state: DreamPathAgentState):
    return state.route or "finalize"

g.add_conditional_edges("orchestrator", router, {
    "course_search": "course_search",
    "plan_builder": "plan_builder",
    "course_path": "course_path",
    "finalize": "finalize",
})

def course_path_router(state: DreamPathAgentState):
    return state.route or "orchestrator"

# workers loop back to orchestrator-style planner
g.add_edge("course_search", "orchestrator")
g.add_edge("plan_builder", "course_path")     # plan → execute directly
g.add_conditional_edges("course_path", course_path_router, {
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
    major_name = 'Computer Science'
    # removed: 'COSC89.17', 'COSC89.19', 'COSC89.20', 'COSC89.28'
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
    config = {"configurable": {"thread_id": "1", "coursepath_agent": agent}}
    state = DreamPathAgentState()

    while True:
        current_path = tools.cp
        print(f"----------\nCoursePath (@ term={current_path.curr_window_start})")
        print(current_path)
        print("----------\n")
        user = input("You: ").strip()
        if not user: break
        try:
            state_dict = app.invoke({"major": major_name, "recent_messages": [{"role": "user", "content": user}]}, config)
            
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