import os

from dotenv import load_dotenv
from dreampath_processing.dreampath_agent.context_building import (
    build_complete_context,
    calculate_token_count,
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.nodes.prompts import CRAFT_FINAL_REPLY_SYS
from langchain_core.messages import AIMessageChunk
from openai import AsyncOpenAI

load_dotenv()


async def render_final_reply(state: DreamPathAgentState, config) -> tuple[str, dict]:
    """Render the final reply to the user (blocking version)."""
    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name


    return await extract_structured_output_from_context(
        state=state,
        config=config,
        system_prompt=CRAFT_FINAL_REPLY_SYS.format(student_name=student_name),
        small_context=False,
        model="gpt-4o",
    )


async def render_final_reply_streaming(state: DreamPathAgentState, config, writer) -> tuple[str, dict]:
    """
    Streaming version of render_final_reply that emits tokens via writer callback.
    Uses native OpenAI ASYNC streaming instead of Instructor to enable token-by-token emission.
    """
    import time

    # Query fresh profile from DB
    student_profile = await config["configurable"]["student_db_service"].load_student_profile(
        config["configurable"]["user_id"]
    )
    student_name = student_profile.name
    system_prompt = CRAFT_FINAL_REPLY_SYS.format(student_name=student_name)

    # Build context
    messages, state_updates = await build_complete_context(state, system_prompt, config)

    # Log context to file for debugging
    with open("finalize_context.txt", "w") as f:
        f.write("=" * 80 + "\n")
        f.write("FINALIZE NODE - MESSAGE CONTEXT\n")
        f.write("=" * 80 + "\n\n")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            f.write(f"\n[{i}] ROLE: {role}\n")
            f.write("-" * 40 + "\n")
            f.write(f"{content}\n")
            f.write("\n")
    print("  ✓ Logged context to finalize_context.txt")

    # Log token count
    model = "gpt-4o"
    print(f"[ MODEL={model} | TOKEN COUNT: {calculate_token_count(messages, model)} ]")

    # Use ASYNC OpenAI client for streaming (bypass Instructor)
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Make ASYNC streaming call
    stream = await openai_client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True
    )

    # Accumulate complete response
    full_response = ""

    # Emit tokens via writer
    start_time = time.time()
    token_count = 0

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_response += token
            token_count += 1

            # Emit AIMessageChunk
            if writer:
                chunk_msg = AIMessageChunk(content=token)
                writer(chunk_msg)

    elapsed = time.time() - start_time
    if token_count > 0:
        print(f"🟡 FINALIZE: Streamed {token_count} tokens in {elapsed:.2f}s")

    return full_response, state_updates


async def finalize_node(state: DreamPathAgentState, config, *, writer=None) -> DreamPathAgentState:
    """
    Finalize node that synthesizes the final response to the user.

    Handles:
    - General conversation
    - Summarizing search results
    - Wrapping up course path modifications
    - Offering next steps
    """
    # Use streaming version if writer is available, otherwise use blocking version
    if writer:
        reply, _ = await render_final_reply_streaming(state, config, writer)
    else:
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
        "init_mode": False,
        "require_user_confirmation": True,
    }
