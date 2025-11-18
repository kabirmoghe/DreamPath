import os
import json
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from dreampath_processing.dreampath_agent.rebuild_tool import execute_rebuild_tool
from dreampath_processing.dreampath_agent.debug_logger import clear_log_file
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.node_helpers import (
    decide_next_route, build_operations_from_context_and_results, determine_course_search_queries, modify_student_profile, determine_user_confirmation, 
    format_orchestrator_decision, format_course_search_output, format_aggregate_coursepath_agent_result, format_worklist, format_modified_student_profile, 
    format_rebuild_course_path_output, render_final_reply
)
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY
from dreampath_processing.courses.coursepath_agent.agent_v2 import CoursePathAgent, CoursePathTools
from dreampath_processing.courses.schedule_modules.course_path import CoursePath
from dreampath_processing.modules.student_profile import StudentProfile
from typing import Generator, Tuple, Optional
from dreampath_processing.database.connection import get_db_connection
import asyncio
from dreampath_processing.database.student_service import StudentDatabaseService

def orchestrator_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    print(f"Orchestrator thinking...")

    decision, state_updates = decide_next_route(state, config)

    print(f"| → Decision: {decision.route} | Reason: {decision.reason} | Confidence: {decision.confidence}")
    if decision.handoff:
        print(f"| + Handoff: {decision.handoff}")

    orchestrator_decision = {
        "role": "assistant",
        "content": {
            "name": "orchestrator",
            "result": format_orchestrator_decision(decision),
        },
    }

    orchestrator_msg_lc = dreampath_to_langchain(orchestrator_decision)

    return {
        "route": decision.route,
        "handoff": decision.handoff,
        "turn_messages": state.turn_messages + [orchestrator_decision],
        "messages": [orchestrator_msg_lc],
        **state_updates,
    }

def course_search_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    course_search_tool: CourseSearchTool = config["configurable"]["course_search_tool"]
    queries, _ = determine_course_search_queries(state, config) # no state updates, only updating turn_messages
    # print(f"********** CourseSearchNode: queries={queries}")

    tool_messages = []
    langchain_messages = []

    for query in queries.queries:

        # Build tool call
        tool_call = {
            "role": "assistant",
            "content": {
                "name": "course_search",
                "arguments": {
                    "queries": json.dumps(query.model_dump()),
                }
            },
        }

        tool_messages.append(tool_call)
        langchain_messages.append(dreampath_to_langchain(tool_call))

        # Execute tool call
        search_results = course_search_tool.structured_hybrid_search(query)
        
        tool_result = {
            "role": "assistant",
            "content": {
                "name": "course_search",
                "result": format_course_search_output(search_results),
            },
        }

        tool_messages.append(tool_result)
        langchain_messages.append(dreampath_to_langchain(tool_result))

    return {
        "turn_messages": state.turn_messages + tool_messages,
        "messages": langchain_messages,
    }
    
def plan_builder_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    ops, _ = build_operations_from_context_and_results(state, config) # no state updates, only updating worklist and turn messages

    tool_result = {
        "role": "assistant",
        "content": {
            "name": "plan_builder",
            "result": format_worklist(ops.operations),
        },
    }

    tool_result_lc = dreampath_to_langchain(tool_result)

    return {
        "worklist": ops.operations, # List[str], e.g., ["Add QSS41 to term 6.", "Add COSC50 to term 6."]
        "cursor": 0,
        "current_cp_agent_outcomes": {},   # start fresh for this batch
        "turn_messages": state.turn_messages + [tool_result],
        "messages": [tool_result_lc],
    }

def course_path_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    coursepath_agent: CoursePathAgent = config["configurable"]["coursepath_agent"]
    coursepath_agent.require_user_confirmation = state.require_user_confirmation
    cursor = state.cursor
    current_op = None
    outcomes = state.current_cp_agent_outcomes
    worklist = state.worklist
    tool_messages = []
    langchain_messages = []

    print(f"| → CoursePathAgent: worklist={worklist}, cursor={cursor}")

    # Build tool call at start of execution
    if cursor == 0:
        tool_call = {
            "role": "assistant",
            "content": {
                "name": "course_path_agent",
                "arguments": {
                    "worklist": worklist,
                    "cursor": cursor
                }
            },
        }
        tool_messages.append(tool_call)
        langchain_messages.append(dreampath_to_langchain(tool_call))
        coursepath_agent.save_previous_course_path()

    # Execute operations one by one
    if worklist and cursor < len(worklist):
        current_op = worklist[cursor]

        # If we have a pending pre-interrupt, use it
        if state.pending_pre_interrupt is not None:
            print("| * Using cached pre-interrupt output (avoiding re-execution)")
            cp_agent_output = state.pending_pre_interrupt
        else:   
            print("| * Executing operation for the first time")
            cp_agent_output = coursepath_agent.run(current_op) # execute op

        if cp_agent_output.status == "ask":
            # Use interrupt() function to pause and wait for user input
            user_response = interrupt({
                "pending_pre_interrupt": cp_agent_output,
                "text": cp_agent_output.ui_text
            })

            # Continue processing with user response
            cp_agent_output = coursepath_agent.run(user_response)

        outcomes[current_op] = cp_agent_output
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
                "name": "course_path_agent",
                "result": aggregate_result,
            },
        }
        tool_messages.append(tool_result)
        langchain_messages.append(dreampath_to_langchain(tool_result))
        
    # Update the config with the new course path | TODO: separate profile and course path
    modified_cp = coursepath_agent.tools.cp


    # TODO: asynchronously save the student profile + course path to the database

    return {
        "turn_messages": state.turn_messages + tool_messages,
        "pending_pre_interrupt": None,
        "current_cp_agent_outcomes": outcomes,
        "worklist": worklist,
        "cursor": cursor,
        "route": route,
        "messages": langchain_messages,
    }

def modify_profile_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    # Check if we already computed the modified profile (to avoid re-computing on interrupt resume)
    print(f"| → ProfileModifier")

    langchain_messages = []

    if state.pending_pre_interrupt is not None:
        print("| * Using cached modified profile (avoiding re-computation)")
        modified_profile = state.pending_pre_interrupt
    else:
        print("| * Computing modified profile for the first time")
        modified_profile, _ = modify_student_profile(state, config) # no state updates, only updating turn messages

    # Verify modified profile with user
    if state.require_user_confirmation:
        user_response = interrupt({
            "pending_pre_interrupt": modified_profile,
            "text": f"How do you feel about the modified profile? {modified_profile.__str__()}"
        })
    if state.require_user_confirmation and determine_user_confirmation(user_response):
        # Get the current student profile from config
        current_profile = config["configurable"]["student_profile"]
        
        # Update the existing profile object's attributes
        current_profile.major = modified_profile.major
        current_profile.college_interests = modified_profile.college_interests
        current_profile.post_grad_goals = modified_profile.post_grad_goals
        current_profile.career_goals = modified_profile.career_goals

        # Update the config with the new profile
        print(f"| → ProfileModifier: user confirmed, updated_profile={current_profile}")

        tool_result = {
            "role": "assistant",
            "content": {
                "name": "modify_profile",
                "result": format_modified_student_profile(modified_profile),
            },
        }

        langchain_messages.append(dreampath_to_langchain(tool_result))

        # TODO: asynchronously save the student profile to the database

        return {
            "turn_messages": state.turn_messages + [tool_result],
            "pending_pre_interrupt": None,
        }
    else:
        return {}

def rebuild_course_path_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    # Workhorse func to rebuild the course path
    output = execute_rebuild_tool(state, config)
    
    # If we created a new course path, 'execute_rebuild_tool' will have created a new coursepath_agent with tools
    tool_result = {
        "role": "assistant",
        "content": {
            "name": "rebuild_course_path",
            "result": format_rebuild_course_path_output(output),
        },
    }

    tool_result_lc = dreampath_to_langchain(tool_result)

    # TODO: asynchronously save the student profile + course path to the database
    modified_profile = config["configurable"]["student_profile"]
    course_path = config["configurable"]["coursepath_agent"].tools.cp
    user_id = config["configurable"]["user_id"]
    student_db_service = config["configurable"]["student_db_service"]
    
    # Run async database operations in sequence
    async def save_to_db():
        # Save profile first (this sets active_profile_id in users table)
        await student_db_service.save_student_profile(modified_profile, user_id)
        # Then save course path (depends on active_profile_id being set)
        await student_db_service.save_course_path(course_path, user_id)
    
    # Execute the async function
    asyncio.run(save_to_db())

    return {
        "turn_messages": state.turn_messages + [tool_result],
        "require_user_confirmation": False,
        "messages": [tool_result_lc],
    }

def finalize_node(state: DreamPathAgentState, config) -> DreamPathAgentState:

    # Add turn messages to state's messages
    reply, _ = render_final_reply(state, config)

    usr_msg_dict = {
        "role": "system" if state.init_mode else "user",
        "content": state.current_user_msg
    }
    reply_msg_dict = {
        "role": "assistant",
        "content": reply
    }
    compiled_turn_messages = [usr_msg_dict] + state.turn_messages + [reply_msg_dict]
    
    # Convert reply to LangChain format for streaming
    reply_msg_lc = dreampath_to_langchain(reply_msg_dict)

    return {
        "ui_reply": reply,
        "current_cp_agent_outcomes": {},
        "dreampath_messages": compiled_turn_messages,
        "messages": [reply_msg_lc],
        "current_user_msg": None,
        "turn_messages": [],
        "init_mode": False, # Default: not in init mode
        "require_user_confirmation": True, # Default: user confirmation required
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
    
    def __init__(self, user_id: str, thread_id: str = "default", generate_diagram: bool=False, student_profile: Optional[StudentProfile] = None, course_path: Optional[CoursePath] = None):
        """
        Initialize the DreampathAgent.
        
        Args:
            user_id: User ID for database operations
            thread_id: Unique identifier for the conversation thread
            student_profile: Optional StudentProfile (if None, loads from database)
            course_path: Optional CoursePath (if None, loads from database)
        """
        self.thread_id = thread_id
        self.user_id = user_id
        
        # Initialize database service
        db_conn = get_db_connection()
        self.student_db_service = StudentDatabaseService(db_conn)
        
        # Load or use provided data
        if student_profile is None:
            # Load from database
            self.student_profile = asyncio.run(self.student_db_service.load_student_profile(user_id))
            if self.student_profile is None:
                raise ValueError(f"No student profile found for user {user_id}")
        else:
            self.student_profile = student_profile
            
        if course_path is None:
            # Load from database
            self.course_path = asyncio.run(self.student_db_service.load_course_path(user_id))
        else:
            self.course_path = course_path
        
        # Initialize components
        self.course_search_tool = CourseSearchTool()
        
        # Set up coursepath agent
        if self.course_path is not None:
            coursepath_tools = CoursePathTools(
                course_path=self.course_path, 
                major=self.student_profile.major
            )
        else:
            coursepath_tools = None
        
        self.coursepath_agent = CoursePathAgent(tools=coursepath_tools)
        
        # Build the graph
        self._build_graph(generate_diagram=generate_diagram)
        
        # Initialize state
        self.state = DreamPathAgentState()

        # Initialize config
        self.config = {
            "configurable": {
                "thread_id": self.thread_id,
                "user_id": self.user_id,
                "coursepath_agent": self.coursepath_agent,
                "student_profile": self.student_profile,
                "course_search_tool": self.course_search_tool,
                "student_db_service": self.student_db_service
            }
        }
        
    def _build_graph(self, generate_diagram: bool=False):
        """Build the LangGraph state graph for the agent."""
        g = StateGraph(DreamPathAgentState)
        g.add_node("orchestrator", orchestrator_node)
        g.add_node("course_search", course_search_node)
        g.add_node("plan_builder", plan_builder_node)
        g.add_node("course_path", course_path_node)
        g.add_node("modify_profile", modify_profile_node)
        g.add_node("rebuild_course_path", rebuild_course_path_node)
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
            "rebuild_course_path": "rebuild_course_path",
            "finalize": "finalize",
        })

        # Sub-nodes loop back to orchestrator-style planner
        def sub_node_router(state: DreamPathAgentState):
            return state.route or "orchestrator"

        g.add_edge("course_search", "orchestrator")
        g.add_edge("plan_builder", "orchestrator")
        g.add_conditional_edges("course_path", sub_node_router, {
            "course_path": "course_path",
            "orchestrator": "orchestrator",
        })
        g.add_edge("modify_profile", "orchestrator")
        g.add_edge("rebuild_course_path", "orchestrator")
        g.add_edge("finalize", END)

        checkpointer = InMemorySaver()
        self.app = g.compile(checkpointer=checkpointer)

        # Generate diagram
        if generate_diagram:
            png_graph = self.app.get_graph().draw_mermaid_png()
            with open("my_graph.png", "wb") as f:
                f.write(png_graph)
    
    def run(self, user_input: str, init_mode: bool=False) -> Generator[Tuple[str, Optional[str]], str, str]:
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

        try:
            # Invoke the graph with the user input
            state_dict = self.app.invoke({
                "major": self.config["configurable"]["student_profile"].major,
                "current_user_msg": user_input,
                "init_mode": init_mode,
            }, self.config)
            
            # Handle interrupts in a loop
            while '__interrupt__' in state_dict:
                interrupt_info = state_dict['__interrupt__'][0]

                # Get (1) pending pre-interrupt, (2) interrupt message
                pending_pre_interrupt = interrupt_info.value["pending_pre_interrupt"]
                interrupt_msg = interrupt_info.value["text"]
                
                # Yield the interrupt message and wait for user response
                user_response = yield (interrupt_msg, interrupt_msg)
                
                # Continue with user response
                messages_to_add = [
                    {"role": "assistant", "content": interrupt_msg},
                    {"role": "user", "content": user_response}
                ]

                # Convert messages to LangChain format
                messages_to_add_lc = [dreampath_to_langchain(msg) for msg in messages_to_add]
                
                state_dict = self.app.invoke(
                    Command(resume=user_response, update={"turn_messages": state_dict.get("turn_messages", []) + messages_to_add, "pending_pre_interrupt": pending_pre_interrupt, "messages": messages_to_add_lc}), 
                    self.config
                )
            
            # Update internal state
            self.state = DreamPathAgentState(**state_dict)
            
            # Return final response
            final_response = self.state.ui_reply or "(ok)"
            return final_response
            
        except Exception as e:
            error_msg = f"❌ ERROR: {type(e).__name__}: {e}"
            return error_msg
    
    def init_course_path(self) -> str:
        """
        Initialize the course path for a new student.
        
        Returns:
            str: The final response from the initialization process
        """
        init_message = "Student completed their profile for the first time. Please build a course path for them."
        conversation = self.run(user_input=init_message, init_mode=True)
        
        # Consume the generator to completion
        final_response = None
        try:
            while True:
                assistant_msg, interrupt_request = next(conversation)
                if interrupt_request is None:
                    final_response = assistant_msg
                    break
                # If there's an interrupt, we shouldn't reach here for init
                # but if we do, we'll just continue
        except StopIteration as e:
            final_response = e.value if hasattr(e, 'value') and e.value else assistant_msg
        
        return final_response or "(Initialization completed)"
    
    def get_course_path_visualization(self) -> str:
        """Get a visualization of the current course path."""
        current_path = self.config["configurable"]["coursepath_agent"].tools.cp
        if current_path is None:
            return "No course path created yet."
        return f"CoursePath (@ term={current_path.curr_window_start})\n{current_path.visualize_by_term_idx()}"
    
    def get_student_profile_summary(self) -> str:
        """Get a summary of the student profile."""
        return str(self.config["configurable"]["student_profile"])

# ------------------------------------------------------------
# MAIN GRAPH (for backwards compatibility)
# ------------------------------------------------------------

from langchain_core.messages import BaseMessage
from typing import List
from datetime import datetime

def clear_langchain_messages():
    file = "current_LC_messages.txt"
    with open(file, "w") as f:
        f.write("Cleared at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def log_langchain_messages(messages: List[BaseMessage]):
    file = "current_LC_messages.txt"
    with open(file, "w") as f:
        for msg in messages:
            f.write(f"💬 {msg.type}: {msg.content}\n")

if __name__ == "__main__":
    
    # Set up course path agent
    major = 'Computer Science'
    # removed: 'COSC89.17', 'COSC89.19', 'COSC89.20', 'COSC89.28'
    # major_courses = {'COSC89.27', 'COSC55', 'COSC35', 'COSC62', 'COSC69.17', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    # complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}
    
    # Construct recommended courses set and course bank
    # recommended_courses = major_courses | complementary_courses
    # course_bank = {c: construct_course(course_code=c, hardcoded_type=MAJOR if c in major_courses else COMPLEMENTARY) for c in recommended_courses}

    # # Build initial course path + course bank updated with prereqs + scheduling info
    # test_course_path = build_course_path(recommended_courses, course_bank)
    # test_course_path.curr_window_start = 6 # Example

    student_profile = StudentProfile(
        name="Kabir Moghe",
        major=major,
        college_interests="I want to focus on international relations and current events (specifically courses on Israel / Palestine, diplomacy); I want to dabble in AI and data science for social sciences",
        post_grad_goals="work hands on as a data scientists and engineer at a tech company or startup, be knowledgeable about data security/privacy, etc.",
        career_goals="Become a CDO or hands on CEO developing a b2b saas platform for data aggregation across different BI tools.",
    )
    
    # Create a user in the database first
    async def create_test_user():
        db_conn = get_db_connection()
        student_service = StudentDatabaseService(db_conn)
        
        # Create user
        await student_service.db.execute_command(
            "INSERT INTO users (email, name) VALUES ($1, $2) ON CONFLICT (email) DO NOTHING",
            "kabir@test.com", "Kabir Moghe"
        )
        
        # Get the user ID
        user_result = await student_service.db.execute_one(
            "SELECT id FROM users WHERE email = $1", "kabir@test.com"
        )
        return user_result['id']
    
    # Create user and get user_id
    user_id = asyncio.run(create_test_user())
    print(f"Created user with ID: {user_id}")
    
    # Create the agent
    agent = DreampathAgent(student_profile=student_profile, thread_id="1", user_id=user_id)
    clear_log_file()
    clear_langchain_messages()

    # Initialize course path
    init_response = agent.init_course_path()
    print(f"💬 ASSISTANT: {init_response}")

    print("DreampathAgent ready. Type 'quit' to exit.\n")

    while True:
        log_langchain_messages(agent.state.messages)

        # Show current course path
        print(f"----------\n{agent.get_course_path_visualization()}\n----------")
        print(f"Student profile: {agent.get_student_profile_summary()}")
        
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