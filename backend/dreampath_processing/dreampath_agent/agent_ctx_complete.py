import json
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from dreampath_processing.dreampath_agent.types import DreamPathAgentState
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.helpers import (
    decide_next_route, build_operations_from_context_and_results, determine_course_search_queries, render_final_reply, modify_student_profile, determine_user_confirmation, format_course_search_output, format_aggregate_coursepath_agent_result
)
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY
from dreampath_processing.courses.coursepath_agent.agent import CoursePathAgent, CoursePathTools
from dreampath_processing.modules.student_profile import StudentProfile
from typing import Generator, Tuple, Optional

def orchestrator_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    print(f"Orchestrator thinking...")
    decision, state_updates = decide_next_route(state, config)
    print(f"--> Decision: {decision}")

    return {
        "route": decision.next,
        **state_updates,
    }

def course_search_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    course_search_tool: CourseSearchTool = config["configurable"]["course_search_tool"]
    queries, state_updates = determine_course_search_queries(state, config)
    print(f"********** CourseSearchNode: queries={queries}")

    tool_messages = []
    for query in queries.queries:

        # Build tool call
        tool_call = {
            "role": "assistant",
            "content": {
                "type": "tool_call",
                "name": "course_search",
                "arguments": {
                    "queries": json.dumps(query.model_dump()),
                }
            },
        }

        tool_messages.append(tool_call)

        # Execute tool call
        search_results = course_search_tool.structured_hybrid_search(query)
        
        tool_result = {
            "role": "assistant",
            "content": {
                "type": "tool_result",
                "name": "course_search",
                "result": format_course_search_output(search_results),
            },
        }

        tool_messages.append(tool_result)

    return {
        "messages": tool_messages,
        **state_updates,
    }
    
def plan_builder_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    ops, state_updates = build_operations_from_context_and_results(state, config)
    
    return {
        "worklist": ops.operations, # List[str], e.g., ["Add QSS41 to term 6.", "Add COSC50 to term 6."]
        "cursor": 0,
        "current_cp_agent_outcomes": {},   # start fresh for this batch
        **state_updates,
    }

def course_path_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    coursepath_agent: CoursePathAgent = config["configurable"]["coursepath_agent"]
    cursor = state.cursor
    current_op = None
    outcomes = state.current_cp_agent_outcomes
    worklist = state.worklist
    tool_messages = []

    print(f"********** CoursePathNode: worklist={worklist}, cursor={cursor}")

    # current outcomes
    print(f"********** CoursePathNode: current_cp_agent_outcomes={state.current_cp_agent_outcomes}")

    # Build tool call at start of execution
    if cursor == 0:
        tool_call = {
            "role": "assistant",
            "content": {
                "type": "tool_call",
                "name": "coursepath_agent",
                "arguments": {
                    "worklist": worklist,
                    "cursor": cursor
                }
            },
        }
        tool_messages.append(tool_call)
        print(f"********** CoursePathNode: saving previous course path")
        coursepath_agent.save_previous_course_path()

    # Execute operations one by one
    if worklist and cursor < len(worklist):
        current_op = worklist[cursor]
        out = coursepath_agent.run(current_op) # execute op

        while out.status == "ask":
            # Use interrupt() function to pause and wait for user input
            user_response = interrupt(out.ui_text)

            # Continue processing with user response
            out = coursepath_agent.run(user_response)

        outcomes[current_op] = out
        cursor += 1
        route = "course_path"
    else:
        route = "orchestrator"

        # Format aggregate outcome
        diff = coursepath_agent.get_diff_from_previous_course_path()
        aggregate_result = format_aggregate_coursepath_agent_result(state.current_cp_agent_outcomes, diff)
        tool_result = {
            "role": "assistant",
            "content": {
                "type": "tool_result",
                "name": "coursepath_agent",
                "result": aggregate_result,
            },
        }
        tool_messages.append(tool_result)
        
    # Update the config with the new course path
    modified_cp = coursepath_agent.tools.cp
    config["configurable"]["student_profile"].course_path = modified_cp

    return {
        "messages": tool_messages,
        "current_cp_agent_outcomes": outcomes,
        "worklist": worklist,
        "cursor": cursor,
        "route": route,
    }

def modify_profile_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    modified_profile, state_updates = modify_student_profile(state, config)

    # Verify modified profile with user
    user_response = interrupt(f"How do you feel about the modified profile? {modified_profile.__str__()}")
    if determine_user_confirmation(user_response):

        print(f"********** ProfileModifierNode: user confirmed modified profile")

        # Get the current student profile from config
        current_profile = config["configurable"]["student_profile"]
        
        # Create a new StudentProfile by merging modified fields with existing profile
        updated_profile = StudentProfile(
            name=current_profile.name,
            major=modified_profile.major, 
            college_interests=modified_profile.college_interests,
            post_grad_goals=modified_profile.post_grad_goals,
            career_goals=modified_profile.career_goals,
            course_path=current_profile.course_path,
            minors=current_profile.minors,
            clubs=current_profile.clubs,
            career=current_profile.career,
        )
        
        # Update the config with the new profile
        config["configurable"]["student_profile"] = updated_profile

        print(f"********** ProfileModifierNode: updated_profile={updated_profile}")

        tool_call = {
            "role": "assistant",
            "content": {
                "type": "tool_call",
                "name": "modify_profile",
                "arguments": {
                    "modified_profile": json.dumps(modified_profile.model_dump()),
                }
            },
        }

        return {
            "messages": [tool_call],
            **state_updates,
        }
    else:
        return {
            **state_updates
        }

def finalize_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    reply, state_updates = render_final_reply(state, config)
    return {
        "ui_reply": reply,
        "current_cp_agent_outcomes": {},
        "search_results": None,
        "messages": [{"role": "assistant", "content": reply}],
        **state_updates,
    }

# ------------------------------------------------------------
# DREAMPATH AGENT CLASS
# ------------------------------------------------------------

class DreampathAgent:
    """
    A conversational agent for course path planning and academic advising.
    
    This agent can help students with:
    - Course search and recommendations
    - Course path modifications (add, remove, move courses)
    - Profile updates (major, interests, goals)
    - Academic planning and scheduling
    """
    
    def __init__(self, student_profile: StudentProfile, thread_id: str = "default"):
        """
        Initialize the DreampathAgent.
        
        Args:
            student_profile: StudentProfile containing student information and course path
            thread_id: Unique identifier for the conversation thread
        """
        self.student_profile = student_profile
        self.thread_id = thread_id
        
        # Initialize components
        self.course_search_tool = CourseSearchTool()
        
        # Set up coursepath agent
        coursepath_tools = CoursePathTools(
            course_path=student_profile.course_path, 
            major=student_profile.major
        )
        self.coursepath_agent = CoursePathAgent(tools=coursepath_tools)
        
        # Build the graph
        self._build_graph()
        
        # Initialize state
        self.state = DreamPathAgentState()
        
    def _build_graph(self):
        """Build the LangGraph state graph for the agent."""
        g = StateGraph(DreamPathAgentState)
        g.add_node("orchestrator", orchestrator_node)
        g.add_node("course_search", course_search_node)
        g.add_node("plan_builder", plan_builder_node)
        g.add_node("course_path", course_path_node)
        g.add_node("modify_profile", modify_profile_node)
        g.add_node("finalize", finalize_node)

        g.add_edge(START, "orchestrator")

        # Orchestrator to sub-nodes
        def router(state: DreamPathAgentState):
            return state.route or "finalize"

        g.add_conditional_edges("orchestrator", router, {
            "course_search": "course_search",
            "plan_builder": "plan_builder",
            "modify_profile": "modify_profile",
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
        g.add_edge("modify_profile", "orchestrator")
        g.add_edge("finalize", END)

        checkpointer = InMemorySaver()
        self.app = g.compile(checkpointer=checkpointer)
        
    def _get_config(self):
        """Get the configuration for the graph execution."""
        return {
            "configurable": {
                "thread_id": self.thread_id,
                "coursepath_agent": self.coursepath_agent,
                "student_profile": self.student_profile,
                "course_search_tool": self.course_search_tool
            }
        }
    
    def run(self, user_input: str) -> Generator[Tuple[str, Optional[str]], str, str]:
        """
        Process user input and return a generator that yields conversation turns.
        
        This method handles the full conversation flow including interrupts for user
        confirmations and clarifications.
        
        Args:
            user_input: The user's message/question
            
        Yields:
            Tuple[str, Optional[str]]: (assistant_message, interrupt_request)
            - assistant_message: The agent's response
            - interrupt_request: If not None, a question requiring user response
            
        Returns:
            str: The final assistant response when conversation is complete
        """
        config = self._get_config()
        
        try:
            # Invoke the graph with the user input
            state_dict = self.app.invoke({
                "major": self.student_profile.major,
                "messages": [{"role": "user", "content": user_input}]
            }, config)
            
            # Handle interrupts in a loop
            while '__interrupt__' in state_dict:
                interrupt_info = state_dict['__interrupt__']
                interrupt_msg = interrupt_info[0].value
                
                # Yield the interrupt message and wait for user response
                user_response = yield (interrupt_msg, interrupt_msg)
                
                # Continue with user response
                messages_to_add = [
                    {"role": "assistant", "content": interrupt_msg},
                    {"role": "user", "content": user_response}
                ]

                print(f"********** Messages to add: {messages_to_add}")
                
                state_dict = self.app.invoke(
                    Command(resume=user_response, update={"messages": messages_to_add}), 
                    config
                )
            
            # Update internal state
            self.state = DreamPathAgentState(**state_dict)
            
            # Return final response
            final_response = self.state.ui_reply or "(ok)"
            print(f"********** Final response: {final_response}")
            return final_response
            
        except Exception as e:
            error_msg = f"❌ ERROR: {type(e).__name__}: {e}"
            return error_msg
    
    def get_course_path_visualization(self) -> str:
        """Get a visualization of the current course path."""
        current_path = self.student_profile.course_path
        return f"CoursePath (@ term={current_path.curr_window_start})\n{current_path.visualize()}"
    
    def get_student_profile_summary(self) -> str:
        """Get a summary of the student profile."""
        return str(self.student_profile)

# ------------------------------------------------------------
# MAIN GRAPH (for backwards compatibility)
# ------------------------------------------------------------

g = StateGraph(DreamPathAgentState)
g.add_node("orchestrator", orchestrator_node)
g.add_node("course_search", course_search_node)
g.add_node("plan_builder", plan_builder_node)
g.add_node("course_path", course_path_node)
g.add_node("modify_profile", modify_profile_node)
g.add_node("finalize", finalize_node)

g.add_edge(START, "orchestrator")

# Orchestrator to sub-nodes
def router(state: DreamPathAgentState):
    return state.route or "finalize"

g.add_conditional_edges("orchestrator", router, {
    "course_search": "course_search",
    "plan_builder": "plan_builder",
    "course_path": "course_path",
    "modify_profile": "modify_profile",
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
g.add_edge("modify_profile", "orchestrator")
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

    student_profile = StudentProfile(
        name="Kabir Moghe",
        major="Computer Science",
        college_interests="I want to focus on international relations and current events (specifically courses on Israel / Palestine, diplomacy); I want to dabble in AI and data science for social sciences",
        post_grad_goals="work hands on as a data scientists and engineer at a tech company or startup, be knowledgeable about data security/privacy, etc.",
        career_goals="Become a CDO or hands on CEO developing a b2b saas platform for data aggregation across different BI tools.",
        course_path=test_course_path,
    )
    
    # Create the agent
    agent = DreampathAgent(student_profile=student_profile, thread_id="1")

    print("DreampathAgent ready. Type 'quit' to exit.\n")

    while True:
        # Show current course path
        print(f"----------\n{agent.get_course_path_visualization()}\n----------\n")
        print(f"********** Student profile: {agent.get_student_profile_summary()}")
        
        user = input("You: ").strip()
        if not user or user.lower() in ('quit', 'exit'):
            break
            
        # Use the agent's run method
        conversation = agent.run(user)
        
        try:
            # Get the first yield
            assistant_msg, interrupt_request = next(conversation)
            
            while interrupt_request is not None:
                # Need user input for interrupt
                print(f"💬 ASSISTANT: {assistant_msg}")
                user_response = input("You: ").strip()
                
                # Send response and get next yield
                assistant_msg, interrupt_request = conversation.send(user_response)
            
            # Final response
            print(f"💬 ASSISTANT: {assistant_msg}")
                    
        except StopIteration as e:
            # Conversation completed
            if hasattr(e, 'value') and e.value:
                print(f"💬 ASSISTANT: {e.value}")