import inspect
import json
import logging
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from langchain_core._api import LangChainBetaWarning
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse  # type: ignore[import-untyped]
from langfuse.callback import CallbackHandler  # type: ignore[import-untyped]
from langgraph.types import Command, Interrupt
from langsmith import Client as LangsmithClient

from agents import DEFAULT_AGENT, AgentGraph, get_agent, get_all_agent_info, load_agent
from core import settings
from memory import initialize_database, initialize_store
from dreampath_processing.database.student_service import StudentDatabaseService
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from schema import (
    ChatHistory,
    ChatHistoryInput,
    ChatMessage,
    Feedback,
    FeedbackResponse,
    ServiceMetadata,
    StreamInput,
    UserInput,
)
from service.utils import (
    convert_message_content_to_string,
    langchain_to_chat_message,
    remove_tool_calls,
)

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
logger = logging.getLogger(__name__)

# Global database service (initialized in lifespan)
student_db_service: StudentDatabaseService | None = None


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate idiomatic operation IDs for OpenAPI client generation."""
    return route.name


def verify_bearer(
    http_auth: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(description="Please provide AUTH_SECRET api key.", auto_error=False)),
    ],
) -> None:
    if not settings.AUTH_SECRET:
        return
    auth_secret = settings.AUTH_SECRET.get_secret_value()
    if not http_auth or http_auth.credentials != auth_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Configurable lifespan that initializes the appropriate database checkpointer, store,
    and agents with async loading - for example for starting up MCP clients.
    """
    global student_db_service
    
    try:
        # Initialize both checkpointer (for short-term memory) and store (for long-term memory)
        async with initialize_database() as saver, initialize_store() as store:
            # Set up both components
            if hasattr(saver, "setup"):  # ignore: union-attr
                await saver.setup()
            # Only setup store for Postgres as InMemoryStore doesn't need setup
            if hasattr(store, "setup"):  # ignore: union-attr
                await store.setup()

            # NEW: Initialize student database service
            # print(f"[DEBUG] Initializing student_db_service...")
            # print(f"[DEBUG] Saver type: {type(saver)}")

            # Create DatabaseConnection using our custom class
            from dreampath_processing.database.connection import get_db_connection
            db_connection = get_db_connection()

            # Initialize the pool if not already done
            if db_connection.pool is None:
                # print(f"[DEBUG] Initializing database connection pool...")
                await db_connection.init_pool()
                # print(f"[DEBUG] Database pool initialized")

            student_db_service = StudentDatabaseService(db_connection)
            logger.info("Student database service initialized")
            # print(f"[DEBUG] student_db_service created successfully")

            # Configure agents with both memory components and async loading
            agents = get_all_agent_info()
            for a in agents:
                try:
                    await load_agent(a.key)
                    logger.info(f"Agent loaded: {a.key}")
                except Exception as e:
                    logger.error(f"Failed to load agent {a.key}: {e}")
                    # Continue with other agents rather than failing startup

                agent = get_agent(a.key)
                # Set checkpointer for thread-scoped memory (conversation history)
                agent.checkpointer = saver
                # Set store for long-term memory (cross-conversation knowledge)
                agent.store = store
            yield

            # Cleanup on shutdown
            logger.info("Shutting down: cleaning up database connections...")
            if student_db_service:
                # Close the database connection pool
                from dreampath_processing.database.connection import get_db_connection
                db_connection = get_db_connection()
                if db_connection.pool:
                    await db_connection.close_pool()
                    logger.info("Database connection pool closed")
    except Exception as e:
        logger.error(f"Error during database/store/agents initialization: {e}")
        raise


app = FastAPI(lifespan=lifespan, generate_unique_id_function=custom_generate_unique_id)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://dreampath.live",  # Production custom domain
        "https://www.dreampath.live",  # Production custom domain (www)
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel deployments
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


# Add validation error handler for debugging
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors for debugging."""
    print(f"[VALIDATION ERROR] Request path: {request.url.path}")
    print(f"[VALIDATION ERROR] Request body: {await request.body()}")
    print(f"[VALIDATION ERROR] Errors: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


router = APIRouter(dependencies=[Depends(verify_bearer)])


@router.get("/info")
async def info() -> ServiceMetadata:
    models = list(settings.AVAILABLE_MODELS)
    models.sort()
    return ServiceMetadata(
        agents=get_all_agent_info(),
        models=models,
        default_agent=DEFAULT_AGENT,
        default_model=settings.DEFAULT_MODEL,
    )


async def _initialize_dreampath_config(
    thread_id: str,
    user_id: str,
    config: RunnableConfig
) -> None:
    """
    Initialize dreampath-specific configuration.

    Only sets up infrastructure (tools, services, connections).
    Student profile and course path are queried live from DB as needed.
    """
    global student_db_service

    # print(f"[DEBUG] _initialize_dreampath_config called")

    # Check if already initialized
    if "student_db_service" in config["configurable"]:
        # print(f"[DEBUG] Already initialized, skipping")
        return

    if student_db_service is None:
        print(f"[ERROR] student_db_service is None!")
        raise HTTPException(
            status_code=500,
            detail="Student database service not initialized"
        )

    # Get database connection from the global service
    # print(f"[DEBUG] Getting DB connection...")
    from dreampath_processing.database.connection import get_db_connection
    conn = get_db_connection()
    # print(f"[DEBUG] DB connection obtained")

    # Update config with ONLY infrastructure
    # print(f"[DEBUG] Updating config with infrastructure...")
    # Use user_id as-is (UUID string from Supabase)
    config["configurable"].update({
        "user_id": user_id,  # ← Store as UUID string for database queries
        "conn": conn,
        "student_db_service": student_db_service
    })
    # print(f"[DEBUG] Config updated successfully with user_id={user_id}")


async def _handle_input(user_input: UserInput, agent: AgentGraph) -> tuple[dict[str, Any], UUID]:
    """
    Parse user input and handle any required interrupt resumption.
    Returns kwargs for agent invocation and the run_id.
    """
    run_id = uuid4()
    thread_id = user_input.thread_id or str(uuid4())
    user_id = user_input.user_id or str(uuid4())

    configurable = {"thread_id": thread_id, "user_id": user_id}
    if user_input.model is not None:
        configurable["model"] = user_input.model

    callbacks = []
    if settings.LANGFUSE_TRACING:
        # Initialize Langfuse CallbackHandler for Langchain (tracing)
        langfuse_handler = CallbackHandler()

        callbacks.append(langfuse_handler)


    if user_input.agent_config:
        # Check for reserved keys (including 'model' even if not in configurable)
        reserved_keys = {"thread_id", "user_id", "model"}
        if overlap := reserved_keys & user_input.agent_config.keys():
            raise HTTPException(
                status_code=422,
                detail=f"agent_config contains reserved keys: {overlap}",
            )
        configurable.update(user_input.agent_config)

    config = RunnableConfig(
        configurable=configurable,
        run_id=run_id,
        callbacks=callbacks,
        recursion_limit=75,  # Increase from default 25 to handle complex multi-step operations
    )

    # NEW: Initialize dreampath config if this is the dreampath agent
    if hasattr(agent, 'name') and agent.name == "dreampath-agent":
        try:
            await _initialize_dreampath_config(thread_id, user_id, config)
        except Exception as e:
            print(f"[ERROR] Failed to initialize dreampath config: {e}")
            import traceback
            traceback.print_exc()
            raise

    # Check for interrupts that need to be resumed
    state = await agent.aget_state(config=config)
    interrupted_tasks = [
        task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts
    ]

    # NEW: Adapt input for dreampath agent
    input: Command | dict[str, Any]
    if hasattr(agent, 'name') and agent.name == "dreampath-agent":
        if interrupted_tasks:
            # Extract interrupt value (contains both "text" and "pending_pre_interrupt")
            interrupt_value = interrupted_tasks[0].interrupts[0].value

            # Prepare update dict with pending_pre_interrupt to avoid recomputation
            update_dict: dict[str, Any] = {}

            if isinstance(interrupt_value, dict):
                # Custom DreamPath interrupt format
                pending_pre_interrupt = interrupt_value.get("pending_pre_interrupt")
                interrupt_text = interrupt_value.get("text", "")

                if pending_pre_interrupt is not None:
                    update_dict["pending_pre_interrupt"] = pending_pre_interrupt

                # Add interrupt exchange to turn_messages for DreamPath format
                # Preserve structured metadata so it's available in history
                assistant_message = {"role": "assistant", "content": interrupt_text}

                # Extract and preserve structured metadata
                if "event_type" in interrupt_value:
                    assistant_message["additional_kwargs"] = {}
                    assistant_message["additional_kwargs"]["event_type"] = interrupt_value["event_type"]

                    # Preserve event-specific metadata
                    if interrupt_value["event_type"] == "coursepath_operations":
                        if "operations" in interrupt_value:
                            assistant_message["additional_kwargs"]["operations"] = interrupt_value["operations"]
                        if "op_string" in interrupt_value:
                            assistant_message["additional_kwargs"]["op_string"] = interrupt_value["op_string"]
                    elif interrupt_value["event_type"] == "profile_update":
                        if "changes" in interrupt_value:
                            assistant_message["additional_kwargs"]["changes"] = interrupt_value["changes"]

                messages_to_add = [
                    assistant_message,
                    {"role": "user", "content": user_input.message}
                ]

                # Convert to LangChain format and add to both turn_messages and messages
                messages_to_add_lc = [dreampath_to_langchain(msg) for msg in messages_to_add]

                # Get current turn_messages from state
                current_turn_messages = state.values.get("turn_messages", [])
                update_dict["turn_messages"] = current_turn_messages + messages_to_add
                update_dict["messages"] = messages_to_add_lc


            # Create Command with resume and update
            input = Command(resume=user_input.message, update=update_dict if update_dict else None)
        else:
            is_init = getattr(user_input, 'init_mode', False)
            human_msg = HumanMessage(
                content=user_input.message,
                additional_kwargs={"is_init_message": True} if is_init else {}
            )
            input = {
                "current_user_msg": user_input.message,
                "init_mode": is_init,
                "messages": [human_msg]
            }
    else:
        if interrupted_tasks:
            # assume user input is response to resume agent execution from interrupt
            input = Command(resume=user_input.message)
        else:
            input = {"messages": [HumanMessage(content=user_input.message)]}

    kwargs = {
        "input": input,
        "config": config,
    }

    return kwargs, run_id


@router.post("/{agent_id}/invoke", operation_id="invoke_with_agent_id")
@router.post("/invoke")
async def invoke(user_input: UserInput, agent_id: str = DEFAULT_AGENT) -> ChatMessage:
    """
    Invoke an agent with user input to retrieve a final response.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.
    """
    # NOTE: Currently this only returns the last message or interrupt.
    # In the case of an agent outputting multiple AIMessages (such as the background step
    # in interrupt-agent, or a tool step in research-assistant), it's omitted. Arguably,
    # you'd want to include it. You could update the API to return a list of ChatMessages
    # in that case.
    agent: AgentGraph = get_agent(agent_id)
    # print(f"[DEBUG] Got agent: {agent_id}")

    kwargs, run_id = await _handle_input(user_input, agent)
    # print(f"[DEBUG] Input kwargs prepared: input keys = {kwargs['input'].keys() if isinstance(kwargs['input'], dict) else type(kwargs['input'])}")

    try:
        # print(f"[DEBUG] Invoking agent...")
        response_events: list[tuple[str, Any]] = await agent.ainvoke(**kwargs, stream_mode=["updates", "values"])  # type: ignore # fmt: skip
        # print(f"[DEBUG] Agent invoked successfully, processing response...")
        response_type, response = response_events[-1]
        if response_type == "values":
            # Normal response, the agent completed successfully
            output = langchain_to_chat_message(response["messages"][-1])
        elif response_type == "updates" and "__interrupt__" in response:
            # The last thing to occur was an interrupt
            interrupt_value = response["__interrupt__"][0].value

            # Handle custom interrupt format (for DreamPath agent)
            if isinstance(interrupt_value, dict) and "text" in interrupt_value:
                # Extract the text field from custom interrupt format
                interrupt_content = interrupt_value["text"]
            else:
                # Standard interrupt format
                interrupt_content = interrupt_value

            output = langchain_to_chat_message(
                AIMessage(content=interrupt_content)
            )
        else:
            raise ValueError(f"Unexpected response type: {response_type}")

        output.run_id = str(run_id)
        return output
    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        print(f"[ERROR] Exception during agent invocation:")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def message_generator(
    user_input: StreamInput, agent_id: str = DEFAULT_AGENT
) -> AsyncGenerator[str, None]:
    """
    Generate a stream of messages from the agent.

    This is the workhorse method for the /stream endpoint.
    """
    agent: AgentGraph = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent)

    try:
        # Process streamed events from the graph and yield messages over the SSE stream.
        import time
        service_start = time.time()
        token_receive_count = 0

        async for stream_event in agent.astream(
            **kwargs, stream_mode=["updates", "messages", "custom"], subgraphs=True
        ):
            if not isinstance(stream_event, tuple):
                continue
            # Handle different stream event structures based on subgraphs
            if len(stream_event) == 3:
                # With subgraphs=True: (node_path, stream_mode, event)
                _, stream_mode, event = stream_event
            else:
                # Without subgraphs: (stream_mode, event)
                stream_mode, event = stream_event

            # Track when custom events arrive (summary only)
            if stream_mode == "custom":
                token_receive_count += 1
                elapsed = time.time() - service_start
                if token_receive_count == 1:
                    print(f"🟢 SERVICE: First custom event received at t={elapsed:.3f}s")
            new_messages = []
            if stream_mode == "updates":
                for node, updates in event.items():
                    # A simple approach to handle agent interrupts.
                    # In a more sophisticated implementation, we could add
                    # some structured ChatMessage type to return the interrupt value.
                    if node == "__interrupt__":
                        interrupt: Interrupt
                        for interrupt in updates:
                            # Handle custom interrupt format (for DreamPath agent)
                            interrupt_value = interrupt.value
                            print(f"🔍 DEBUG SERVICE: interrupt_value = {interrupt_value}")
                            if isinstance(interrupt_value, dict) and "text" in interrupt_value:
                                # Extract the text field from custom interrupt format
                                interrupt_content = interrupt_value["text"]

                                # Check for structured metadata (event_type, operations, changes)
                                ai_message = AIMessage(content=interrupt_content)
                                if "event_type" in interrupt_value:
                                    # Add structured metadata directly to additional_kwargs
                                    # (langchain_to_chat_message copies all of additional_kwargs to custom_data)
                                    ai_message.additional_kwargs["event_type"] = interrupt_value["event_type"]

                                    if interrupt_value["event_type"] == "coursepath_operations":
                                        if "operations" in interrupt_value:
                                            ai_message.additional_kwargs["operations"] = interrupt_value["operations"]
                                        if "op_string" in interrupt_value:
                                            ai_message.additional_kwargs["op_string"] = interrupt_value["op_string"]
                                    elif interrupt_value["event_type"] == "profile_update" and "changes" in interrupt_value:
                                        ai_message.additional_kwargs["changes"] = interrupt_value["changes"]

                                new_messages.append(ai_message)
                            else:
                                # Standard interrupt format
                                interrupt_content = interrupt_value
                                new_messages.append(AIMessage(content=interrupt_content))
                        continue
                    updates = updates or {}
                    update_messages = updates.get("messages", [])
                    # special cases for using langgraph-supervisor library
                    if "supervisor" in node or "sub-agent" in node:
                        # the only tools that come from the actual agent are the handoff and handback tools
                        if isinstance(update_messages[-1], ToolMessage):
                            if "sub-agent" in node and len(update_messages) > 1:
                                # If this is a sub-agent, we want to keep the last 2 messages - the handback tool, and it's result
                                update_messages = update_messages[-2:]
                            else:
                                # If this is a supervisor, we want to keep the last message only - the handoff result. The tool comes from the 'agent' node.
                                update_messages = [update_messages[-1]]
                        else:
                            update_messages = []
                    new_messages.extend(update_messages)

            if stream_mode == "custom":
                # Handle token streaming from custom events
                if isinstance(event, AIMessageChunk) and user_input.stream_tokens:
                    content = remove_tool_calls(event.content)
                    if content:
                        token_content = convert_message_content_to_string(content)
                        yield f"data: {json.dumps({'type': 'token', 'content': token_content})}\n\n"
                    continue  # Skip normal message processing for tokens
                new_messages = [event]

            # LangGraph streaming may emit tuples: (field_name, field_value)
            # e.g. ('content', <str>), ('tool_calls', [ToolCall,...]), ('additional_kwargs', {...}), etc.
            # We accumulate only supported fields into `parts` and skip unsupported metadata.
            # More info at: https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_messages/
            processed_messages = []
            current_message: dict[str, Any] = {}
            for message in new_messages:
                if isinstance(message, tuple):
                    key, value = message
                    # Store parts in temporary dict
                    current_message[key] = value
                else:
                    # Add complete message if we have one in progress
                    if current_message:
                        processed_messages.append(_create_ai_message(current_message))
                        current_message = {}
                    processed_messages.append(message)

            # Add any remaining message parts
            if current_message:
                processed_messages.append(_create_ai_message(current_message))

            for message in processed_messages:
                try:
                    chat_message = langchain_to_chat_message(message)
                    chat_message.run_id = str(run_id)
                except Exception as e:
                    logger.error(f"Error parsing message: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Unexpected error'})}\n\n"
                    continue
                # LangGraph re-sends the input message, which feels weird, so drop it
                if chat_message.type == "human" and chat_message.content == user_input.message:
                    continue
                yield f"data: {json.dumps({'type': 'message', 'content': chat_message.model_dump()})}\n\n"

            if stream_mode == "messages":
                if not user_input.stream_tokens:
                    continue
                msg, metadata = event
                if "skip_stream" in metadata.get("tags", []):
                    continue
                # For some reason, astream("messages") causes non-LLM nodes to send extra messages.
                # Drop them.
                if not isinstance(msg, AIMessageChunk):
                    continue
                content = remove_tool_calls(msg.content)
                if content:
                    # Empty content in the context of OpenAI usually means
                    # that the model is asking for a tool to be invoked.
                    # So we only print non-empty content.
                    token_content = convert_message_content_to_string(content)
                    yield f"data: {json.dumps({'type': 'token', 'content': token_content})}\n\n"
    except Exception as e:
        logger.error(f"Error in message generator: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error'})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


def _create_ai_message(parts: dict) -> AIMessage:
    sig = inspect.signature(AIMessage)
    valid_keys = set(sig.parameters)
    filtered = {k: v for k, v in parts.items() if k in valid_keys}
    return AIMessage(**filtered)


def _sse_response_example() -> dict[int | str, Any]:
    return {
        status.HTTP_200_OK: {
            "description": "Server Sent Event Response",
            "content": {
                "text/event-stream": {
                    "example": "data: {'type': 'token', 'content': 'Hello'}\n\ndata: {'type': 'token', 'content': ' World'}\n\ndata: [DONE]\n\n",
                    "schema": {"type": "string"},
                }
            },
        }
    }


@router.post(
    "/{agent_id}/stream",
    response_class=StreamingResponse,
    responses=_sse_response_example(),
    operation_id="stream_with_agent_id",
)
@router.post("/stream", response_class=StreamingResponse, responses=_sse_response_example())
async def stream(user_input: StreamInput, agent_id: str = DEFAULT_AGENT) -> StreamingResponse:
    """
    Stream an agent's response to a user input, including intermediate messages and tokens.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to all messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.

    Set `stream_tokens=false` to return intermediate messages but not token-by-token.
    """
    print(f"[STREAM DEBUG] Received request - agent_id={agent_id}, user_input={user_input}")

    return StreamingResponse(
        message_generator(user_input, agent_id),
        media_type="text/event-stream",
    )


class InitRequest(BaseModel):
    """Request body for initializing a course path."""
    user_id: str


@router.post("/init", response_class=StreamingResponse, responses=_sse_response_example())
async def initialize_course_path(request: InitRequest) -> StreamingResponse:
    """
    Initialize course path for a new user.

    Validates that:
    - User profile exists
    - Course path doesn't already exist

    Then streams the init process using existing infrastructure.
    """
    global student_db_service
    user_id = request.user_id

    if student_db_service is None:
        raise HTTPException(
            status_code=500,
            detail="Student database service not initialized"
        )

    # Validate profile exists
    try:
        # user_id is now a UUID string from Supabase
        profile = await student_db_service.load_student_profile(user_id)
        if not profile:
            raise HTTPException(
                status_code=400,
                detail="Profile must exist before initialization"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user or profile: {str(e)}"
        )

    # Validate coursepath doesn't exist (prevent double-init)
    try:
        coursepath = await student_db_service.load_course_path(user_id)
        if coursepath:
            raise HTTPException(
                status_code=400,
                detail="User already initialized"
            )
    except Exception as e:
        # If error is "not found", that's fine - means no coursepath exists yet
        pass

    # Create thread for init
    thread_id = str(uuid4())

    # Hardcode init message (same as old init_course_path method)
    init_message = "Student completed their profile for the first time. Please build a course path for them."

    # Create StreamInput with init_mode flag
    user_input = StreamInput(
        message=init_message,
        user_id=user_id,
        thread_id=thread_id,
        stream_tokens=False,  # Don't stream tokens during init
        init_mode=True  # Enable init mode
    )

    # Wrap message_generator to include thread_id at the end and save thread to database
    async def init_generator():
        init_complete = False
        async for chunk in message_generator(user_input, "dreampath-agent"):
            if chunk == "data: [DONE]\n\n":
                # Save thread to database before sending [DONE]
                if not init_complete:
                    try:
                        from dreampath_processing.database.connection import get_db_connection
                        from dreampath_processing.database.thread_service import ThreadDatabaseService

                        db = get_db_connection()
                        thread_service = ThreadDatabaseService(db)
                        await thread_service.create_thread(
                            thread_id=thread_id,
                            user_id=user_id,
                            name=None  # Use auto-generated label
                        )
                        init_complete = True
                    except Exception as e:
                        logger.error(f"Failed to save thread to database: {e}")
                        # Continue anyway - thread metadata is not critical

                # Send thread_id before [DONE]
                yield f"data: {json.dumps({'type': 'thread_id', 'content': thread_id})}\n\n"
            yield chunk

    return StreamingResponse(
        init_generator(),
        media_type="text/event-stream"
    )


@router.post("/feedback")
async def feedback(feedback: Feedback) -> FeedbackResponse:
    """
    Record feedback for a run to LangSmith.

    This is a simple wrapper for the LangSmith create_feedback API, so the
    credentials can be stored and managed in the service rather than the client.
    See: https://api.smith.langchain.com/redoc#tag/feedback/operation/create_feedback_api_v1_feedback_post
    """
    client = LangsmithClient()
    kwargs = feedback.kwargs or {}
    client.create_feedback(
        run_id=feedback.run_id,
        key=feedback.key,
        score=feedback.score,
        **kwargs,
    )
    return FeedbackResponse()


@router.post("/history")
async def history(input: ChatHistoryInput) -> ChatHistory:
    """
    Get chat history.
    """
    # TODO: Hard-coding DEFAULT_AGENT here is wonky
    agent: AgentGraph = get_agent(DEFAULT_AGENT)
    try:
        state_snapshot = await agent.aget_state(
            config=RunnableConfig(configurable={"thread_id": input.thread_id})
        )
        messages: list[AnyMessage] = state_snapshot.values.get("messages", [])

        # Filter out internal messages that shouldn't be displayed to users
        filtered_messages = []
        for msg in messages:
            # Skip ToolMessages (internal routing, worklist, plan_builder results)
            if isinstance(msg, ToolMessage):
                continue

            # Skip init messages (hardcoded system prompt for initialization)
            if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('is_init_message'):
                continue

            # Skip node_status messages (transient routing decisions)
            if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('event_type') == 'node_status':
                continue

            # Skip empty AI messages without any metadata (likely artifacts)
            if isinstance(msg, AIMessage):
                has_content = msg.content and str(msg.content).strip()
                has_metadata = hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('event_type')
                if not has_content and not has_metadata:
                    continue

            # Keep everything else (human messages, AI responses, structured interrupts)
            filtered_messages.append(msg)

        chat_messages: list[ChatMessage] = [langchain_to_chat_message(m) for m in filtered_messages]
        return ChatHistory(messages=chat_messages)
    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")


@app.get("/health")
async def health_check():
    """Health check endpoint."""

    health_status = {"status": "ok"}

    if settings.LANGFUSE_TRACING:
        try:
            langfuse = Langfuse()
            health_status["langfuse"] = "connected" if langfuse.auth_check() else "disconnected"
        except Exception as e:
            logger.error(f"Langfuse connection error: {e}")
            health_status["langfuse"] = "disconnected"

    return health_status


# Include additional routers
from service.coursepath_routes import router as coursepath_router
from service.profile_routes import router as profile_router
from service.majors_routes import router as majors_router
from service.thread_routes import router as thread_router

app.include_router(coursepath_router)
app.include_router(profile_router)
app.include_router(majors_router)
app.include_router(thread_router)
app.include_router(router)
