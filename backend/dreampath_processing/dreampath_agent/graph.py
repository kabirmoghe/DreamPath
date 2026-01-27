"""
DreamPath Agent Graph

This module contains the StateGraph builder and DreampathAgent class.
The agent uses a node-based orchestration pattern with handoff routing.
"""

import asyncio
from datetime import datetime

from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.database.student_service import StudentDatabaseService
from dreampath_processing.dreampath_agent.debug_logger import clear_log_file
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.nodes import (
    course_path_node,
    course_search_node,
    finalize_node,
    modify_profile_node,
    orchestrator_node,
    plan_builder_node,
    rebuild_course_path_node,
)
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


def build_dreampath_graph(
    checkpointer: BaseCheckpointSaver | None = None,
    generate_diagram: bool = False,
    diagram_path: str = "dreampath_agent_graph.png",
):
    """
    Build the DreamPath agent graph.

    This is the single source of truth for the graph structure.
    Both the DreampathAgent class and the service layer use this function.

    Args:
        checkpointer: Optional checkpointer for conversation persistence.
                     If None, compiles without checkpointer (service layer provides at runtime).
        generate_diagram: Whether to generate a visual diagram of the graph.
        diagram_path: Path to save the diagram if generate_diagram is True.

    Returns:
        Compiled LangGraph CompiledStateGraph
    """
    g = StateGraph(DreamPathAgentState)

    # Add nodes
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("course_search", course_search_node)
    g.add_node("plan_builder", plan_builder_node)
    g.add_node("course_path", course_path_node)
    g.add_node("modify_profile", modify_profile_node)
    g.add_node("rebuild_course_path", rebuild_course_path_node)
    g.add_node("finalize", finalize_node)

    # Entry point
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

    # Sub-nodes loop back to orchestrator
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

    # Compile with or without checkpointer
    compiled = g.compile(checkpointer=checkpointer)

    # Generate diagram if requested
    if generate_diagram:
        try:
            png_graph = compiled.get_graph().draw_mermaid_png()
            with open(diagram_path, "wb") as f:
                f.write(png_graph)
        except Exception as e:
            print(f"Warning: Could not generate graph diagram: {e}")

    return compiled


class DreampathAgent:
    """
    A conversational agent for course path planning and academic advising.

    This agent can help students with:
    - Course search and recommendations
    - Course path modifications (add, remove, move courses)
    - Profile updates (major, interests, goals)
    - Academic planning and scheduling
    """

    def __init__(self, user_id: str, thread_id: str = "default", generate_diagram: bool = False):
        """
        Initialize the DreampathAgent.

        Args:
            user_id: User ID for database operations
            thread_id: Unique identifier for the conversation thread
            generate_diagram: Whether to generate a visual diagram of the graph

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

        # Build the graph
        self._build_graph(generate_diagram=generate_diagram)

        # Initialize state
        self.state = DreamPathAgentState()

        # Initialize config - only infrastructure, no mutable state
        self.config = {
            "configurable": {
                "thread_id": self.thread_id,
                "user_id": self.user_id,
                "conn": db_conn,
                "student_db_service": self.student_db_service
            }
        }

    def _build_graph(self, generate_diagram: bool = False):
        """Build the LangGraph state graph for the agent."""
        checkpointer = InMemorySaver()
        self.app = build_dreampath_graph(
            checkpointer=checkpointer,
            generate_diagram=generate_diagram,
        )

    async def run(self, user_input: str, init_mode: bool = False):
        """
        Process user input and return an async generator that yields conversation turns.

        This method handles the full conversation flow including interrupts for user
        confirmations and clarifications.

        Args:
            user_input: The user's message/question
            init_mode: Whether this is an initialization run

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
                    Command(
                        resume=user_response,
                        update={
                            "turn_messages": state_dict.get("turn_messages", []) + messages_to_add,
                            "pending_pre_interrupt": pending_pre_interrupt,
                            "messages": messages_to_add_lc
                        }
                    ),
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
        student_profile = await self.student_db_service.load_student_profile(self.user_id)
        return str(student_profile)


def clear_langchain_messages():
    """Clear the LangChain messages log file."""
    file = "current_LC_messages.txt"
    with open(file, "w") as f:
        f.write("Cleared at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def log_langchain_messages(messages: list[BaseMessage]):
    """Log LangChain messages to file."""
    file = "current_LC_messages.txt"
    with open(file, "w") as f:
        for msg in messages:
            f.write(f"💬 {msg.type}: {msg.content}\n")


async def main():
    """Main entry point for testing the agent directly."""
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
