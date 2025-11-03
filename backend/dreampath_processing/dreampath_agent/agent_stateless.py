import asyncio
import json

from dreampath_processing.courses.coursepath_agent.agent_v3 import CoursePathAPIService
from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.database.student_service import StudentDatabaseService
from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
from dreampath_processing.dreampath_agent.debug_logger import clear_log_file
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.frontend_message_helpers import (
    extract_coursepath_operations_metadata,
    extract_profile_update_metadata,
)
from dreampath_processing.dreampath_agent.node_helpers import (
    build_operations_from_context_and_results,
    decide_next_route,
    determine_course_search_queries,
    determine_user_confirmation,
    format_aggregate_coursepath_agent_result,
    format_course_search_output,
    format_modified_student_profile,
    format_orchestrator_decision,
    format_rebuild_course_path_output,
    format_worklist,
    modify_student_profile,
    render_final_reply,
)
from dreampath_processing.dreampath_agent.rebuild_tool import execute_rebuild_tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


async def orchestrator_node(state: DreamPathAgentState, config, *, writer=None) -> DreamPathAgentState:
    from langchain_core.messages import AIMessage
    import time

    print("🎯 ORCHESTRATOR: Node called")
    start_time = time.time()

    # Create thinking status event
    thinking_event = AIMessage(
        content="",
        additional_kwargs={
            "event_type": "node_status",
            "node": "orchestrator",
            "status": "thinking",
            "message": "Thinking"
        }
    )

    # Emit thinking status IMMEDIATELY via custom event stream
    # writer is injected by LangGraph when stream_mode includes "custom"
    if writer:
        try:
            writer(thinking_event)  # Call synchronously, not async
            print(f"🎯 ORCHESTRATOR: Emitted thinking event via writer at t={time.time() - start_time:.3f}s")
        except Exception as e:
            print(f"🎯 ORCHESTRATOR: Error emitting thinking event: {e}")
    else:
        print(f"🎯 ORCHESTRATOR: No writer available (not in streaming mode)")

    # Do the actual LLM processing (this takes time)
    print("🎯 ORCHESTRATOR: Starting decide_next_route (LLM call)...")
    decision, state_updates = await decide_next_route(state, config)
    print(f"🎯 ORCHESTRATOR: Finished decide_next_route (took {time.time() - start_time:.3f}s total)")

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

    # Create completion status event
    complete_event = AIMessage(
        content="",
        additional_kwargs={
            "event_type": "node_status",
            "node": "orchestrator",
            "status": "node_info",
            "next_node": decision.route,
            "reason": decision.reason
        }
    )
    print(f"🎯 ORCHESTRATOR: Created complete event at t={time.time() - start_time:.3f}s")

    print(f"🎯 ORCHESTRATOR: Returning final state (total time: {time.time() - start_time:.3f}s)")
    print("🎯 ORCHESTRATOR: Node complete")

    # Return with routing info in messages list
    # (thinking_event was already streamed immediately via writer)
    return {
        "route": decision.route,
        "handoff": decision.handoff,
        "turn_messages": state.turn_messages + [orchestrator_decision],
        "messages": [orchestrator_msg_lc, complete_event],
        **state_updates,
    }

async def course_search_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    course_search_tool: CourseSearchTool = config["configurable"]["course_search_tool"]
    queries, _ = await determine_course_search_queries(state, config) # no state updates, only updating turn_messages
    print(f"| CourseSearchNode: queries={queries}")

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
    
async def plan_builder_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    ops, _ = await build_operations_from_context_and_results(state, config) # no state updates, only updating worklist and turn messages

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

async def course_path_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    service: CoursePathAPIService = CoursePathAPIService(config["configurable"]["conn"])
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    major = student_profile.major
    # coursepath_agent = service.
    # coursepath_agent.require_user_confirmation = state.require_user_confirmation
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
        # coursepath_agent.save_previous_course_path() TODO: implement this

    # Execute operations one by one
    if worklist and cursor < len(worklist):
        current_op = worklist[cursor]

        # If we have a pending pre-interrupt, use it
        if state.pending_pre_interrupt is not None:
            print("| * Using cached pre-interrupt output (avoiding re-execution)")
            cp_agent_output = state.pending_pre_interrupt
        else:
            print("| * Executing operation for the first time")
            cp_agent_output = await service.run_stateless(user_id=config['configurable']['user_id'], message=current_op, major=major, require_user_confirmation=state.require_user_confirmation) # execute op

        if cp_agent_output.status == "ask":
            # Extract structured metadata for frontend rendering
            structured_metadata = extract_coursepath_operations_metadata(cp_agent_output)
            print(f"🔍 DEBUG: structured_metadata = {structured_metadata}")

            # Use clean message when we have structured data for visual rendering
            # Include op_string for operation type display (e.g., "ADD COSC78")
            if structured_metadata:
                interrupt_text = ""  # Empty - let the card render everything
                if cp_agent_output.op_string:
                    structured_metadata['op_string'] = cp_agent_output.op_string
            else:
                # Fallback to detailed text if no structured data
                interrupt_text = cp_agent_output.ui_text

            # Use interrupt() function to pause and wait for user input
            user_response = interrupt({
                "pending_pre_interrupt": cp_agent_output,
                "text": interrupt_text,
                **structured_metadata  # Add event_type, operations, and op_string for visual rendering
            })

            # Continue processing with user response
            cp_agent_output = await service.run_stateless(user_id=config['configurable']['user_id'], message=user_response, major=major, require_user_confirmation=state.require_user_confirmation)

        outcomes[current_op] = cp_agent_output
        cursor += 1
        route = "course_path"
    else:
        route = "orchestrator"

        # Format aggregate outcome
        #diff = coursepath_agent.get_diff_from_previous_course_path() TODO: implement this
        aggregate_result = format_aggregate_coursepath_agent_result(state.current_cp_agent_outcomes)#, diff)
        tool_result = {
            "role": "assistant",
            "content": {
                "name": "course_path_agent",
                "result": aggregate_result,
            },
        }
        tool_messages.append(tool_result)

        # Don't send aggregate result to frontend - user already saw structured cards during interrupts
        # The aggregate result stays in turn_messages for LLM context only

    # No need to update config - context building now queries DB live for fresh data

    return {
        "turn_messages": state.turn_messages + tool_messages,
        "pending_pre_interrupt": None,
        "current_cp_agent_outcomes": outcomes,
        "worklist": worklist,
        "cursor": cursor,
        "route": route,
        "messages": langchain_messages,
    }

async def modify_profile_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    # Check if we already computed the modified profile (to avoid re-computing on interrupt resume)
    print("| → ProfileModifier")

    langchain_messages = []

    if state.pending_pre_interrupt is not None:
        print("| * Using cached modified profile (avoiding re-computation)")
        modified_profile = state.pending_pre_interrupt
    else:
        print("| * Computing modified profile for the first time")
        modified_profile, _ = await modify_student_profile(state, config) # no state updates, only updating turn messages

    # Verify modified profile with user
    if state.require_user_confirmation:
        # Load current profile from DB for comparison
        student_db_service = config["configurable"]["student_db_service"]
        current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

        # Extract structured metadata for frontend rendering
        structured_metadata = extract_profile_update_metadata(modified_profile, current_profile)

        # Use clean message when we have structured data for visual rendering
        if structured_metadata:
            interrupt_text = ""  # Empty - let the card render everything
        else:
            # Fallback to detailed text if no structured data
            interrupt_text = f"How do you feel about the modified profile? {modified_profile.__str__()}"

        user_response = interrupt({
            "pending_pre_interrupt": modified_profile,
            "text": interrupt_text,
            **structured_metadata  # Add event_type and changes for visual rendering
        })
    if state.require_user_confirmation and determine_user_confirmation(user_response):
        # Reload profile to ensure we have latest data
        student_db_service = config["configurable"]["student_db_service"]
        current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

        # Update only the modifiable fields from ModifiedStudentProfile
        current_profile.major = modified_profile.major
        current_profile.college_interests = modified_profile.college_interests
        current_profile.post_grad_goals = modified_profile.post_grad_goals
        current_profile.career_goals = modified_profile.career_goals

        print(f"| → ProfileModifier: user confirmed, updated_profile={current_profile}")

        formatted_result = format_modified_student_profile(modified_profile)
        tool_result = {
            "role": "assistant",
            "content": {
                "name": "modify_profile",
                "result": formatted_result,
            },
        }

        # Don't send formatted result to frontend - user already saw structured card during interrupt
        # The formatted result stays in turn_messages for LLM context only

        # Save the complete StudentProfile back to the database
        await student_db_service.save_student_profile(current_profile, config["configurable"]["user_id"])

        return {
            "turn_messages": state.turn_messages + [tool_result],
            "pending_pre_interrupt": None,
            "messages": langchain_messages,
        }
    else:
        return {}

async def rebuild_course_path_node(state: DreamPathAgentState, config, *, writer=None) -> DreamPathAgentState:
    # Workhorse func to rebuild the course path
    output = await execute_rebuild_tool(state, config, writer=writer)

    # If we created a new course path, 'execute_rebuild_tool' will have created a new coursepath_agent with tools
    tool_result = {
        "role": "assistant",
        "content": {
            "name": "rebuild_course_path",
            "result": format_rebuild_course_path_output(output),
        },
    }

    tool_result_lc = dreampath_to_langchain(tool_result)

    return {
        "turn_messages": state.turn_messages + [tool_result],
        "require_user_confirmation": False,
        "messages": [tool_result_lc],
    }

async def finalize_node(state: DreamPathAgentState, config) -> DreamPathAgentState:

    # Add turn messages to state's messages
    reply, _ = await render_final_reply(state, config)

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
    
    def __init__(self, user_id: int, thread_id: str = "default", generate_diagram: bool=False):
        """
        Initialize the DreampathAgent.

        Args:
            user_id: User ID for database operations
            thread_id: Unique identifier for the conversation thread

        Note:
            Both student profile and course path are queried live from the database
            during context building and node execution, ensuring fresh data and
            avoiding stale config issues.
        """
        self.thread_id = thread_id
        self.user_id = user_id

        # Initialize database service
        db_conn = get_db_connection()
        self.student_db_service = StudentDatabaseService(db_conn)

        # Initialize components
        self.course_search_tool = CourseSearchTool()

        # Build the graph
        self._build_graph(generate_diagram=generate_diagram)

        # Initialize state
        self.state = DreamPathAgentState()

        # Initialize config - only infrastructure, no mutable state
        self.config = {
            "configurable": {
                "thread_id": self.thread_id,
                "user_id": self.user_id,
                "course_search_tool": self.course_search_tool,
                "conn": db_conn,
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
    
    async def run(self, user_input: str, init_mode: bool=False):
        """
        Process user input and return an async generator that yields conversation turns.

        This method handles the full conversation flow including interrupts for user
        confirmations and clarifications.

        Args:
            user_input: The user's message/question

        Yields:
            Tuple[str, Optional[str]]: (assistant_message, interrupt_request)
            - assistant_message: The agent's response
            - interrupt_request: If not None, a question requiring user response
            - When interrupt_request is None, conversation is complete
        """

        try:
            # Query fresh profile from DB to get major
            student_profile = await self.student_db_service.load_student_profile(self.user_id)

            # Invoke the graph with the user input
            state_dict = await self.app.ainvoke({
                "major": student_profile.major,
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

                state_dict = await self.app.ainvoke(
                    Command(resume=user_response, update={"turn_messages": state_dict.get("turn_messages", []) + messages_to_add, "pending_pre_interrupt": pending_pre_interrupt, "messages": messages_to_add_lc}),
                    self.config
                )

            # Update internal state
            self.state = DreamPathAgentState(**state_dict)

            # Yield final response with None as interrupt_request to signal completion
            final_response = self.state.ui_reply or "(ok)"
            yield (final_response, None)

        except Exception as e:
            error_msg = f"❌ ERROR: {type(e).__name__}: {e}"
            yield (error_msg, None)
    
    async def init_course_path(self) -> str:
        """
        Initialize the course path for a new student.

        Returns:
            str: The final response from the initialization process
        """
        init_message = "Student completed their profile for the first time. Please build a course path for them."
        conversation = self.run(user_input=init_message, init_mode=True)

        # Consume the async generator to completion
        final_response = None
        try:
            async for assistant_msg, interrupt_request in conversation:
                if interrupt_request is None:
                    # Conversation complete
                    final_response = assistant_msg
                    break
                # If there's an interrupt during init, this shouldn't happen
                # but we'll handle it gracefully
                print(f"Unexpected interrupt during init: {interrupt_request}")
        except Exception as e:
            final_response = f"Error during initialization: {e}"

        return final_response or "(Initialization completed)"
    
    async def get_course_path_visualization(self) -> str:
        """Get a visualization of the current course path."""
        current_path = await self.student_db_service.load_course_path(self.user_id)
        if current_path is None:
            return "No course path created yet."
        return f"CoursePath (@ term={current_path.curr_window_start})\n{current_path.visualize_by_term_idx()}"
    
    async def get_student_profile_summary(self) -> str:
        """Get a summary of the student profile."""
        student_profile = await (self.student_db_service.load_student_profile(self.user_id))
        return str(student_profile)

from datetime import datetime

from langchain_core.messages import BaseMessage


def clear_langchain_messages():
    file = "current_LC_messages.txt"
    with open(file, "w") as f:
        f.write("Cleared at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def log_langchain_messages(messages: list[BaseMessage]):
    file = "current_LC_messages.txt"
    with open(file, "w") as f:
        for msg in messages:
            f.write(f"💬 {msg.type}: {msg.content}\n")

async def main():
    
    test_from_scratch = True

    if not test_from_scratch:
        # major = 'Computer Science'
        # removed: 'COSC89.17', 'COSC89.19', 'COSC89.20', 'COSC89.28'
        # major_courses = {'COSC89.27', 'COSC55', 'COSC35', 'COSC62', 'COSC69.17', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
        # complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}
        
        # # Construct recommended courses set and course bank
        # recommended_courses = major_courses | complementary_courses
        # course_bank = {c: construct_course(course_code=c, hardcoded_type=MAJOR if c in major_courses else COMPLEMENTARY) for c in recommended_courses}

        # # Build initial course path + course bank updated with prereqs + scheduling info
        # test_course_path = build_course_path(recommended_courses, course_bank)
        # test_course_path.curr_window_start = 6 # Example

        
        # Create user and get user_id
        # user_id = asyncio.run(create_test_user())
        # print(f"Created user with ID: {user_id}")
        pass

    user_id = 1
    # Create the agent - profile will be queried from DB as needed
    agent = DreampathAgent(user_id=user_id, thread_id="1")
    clear_log_file()
    clear_langchain_messages()

    # Initialize course path
    init_response = await agent.init_course_path()
    print(f"💬 ASSISTANT: {init_response}")

    print("DreampathAgent ready. Type 'quit' to exit.\n")

    while True:
        log_langchain_messages(agent.state.messages)

        # Show current course path
        print(f"----------\n{await agent.get_course_path_visualization()}\n----------")
        print(f"Student profile: {await agent.get_student_profile_summary()}")
        
        user = input("You: ").strip()
        if not user or user.lower() in ('quit', 'exit'):
            break
            
        # Use the agent's run method
        conversation = agent.run(user)

        try:
            # Get the first yield
            assistant_msg, interrupt_request = await anext(conversation)

            while interrupt_request is not None:
                # Need user input for interrupt
                print(f"💬 ASSISTANT: {assistant_msg}")
                user_response = input("You: ").strip()

                # Send response and get next yield
                assistant_msg, interrupt_request = await conversation.asend(user_response)

            # Final response
            print(f"💬 ASSISTANT: {assistant_msg}")

        except StopAsyncIteration as e:
            # Conversation completed
            if hasattr(e, 'value') and e.value:
                print(f"💬 ASSISTANT: {e.value}")

if __name__ == "__main__":
    asyncio.run(main())