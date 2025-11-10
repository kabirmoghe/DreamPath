import os

import tiktoken
from dotenv import load_dotenv
from dreampath_processing.dreampath_agent.chat_prompts import (
    MASTER_CONTEXT,
    MASTER_CONTEXT_SHORT,
    SUMMARY_SYS_PROMPT,
)
from dreampath_processing.dreampath_agent.debug_logger import log_messages_to_file
from dreampath_processing.dreampath_agent.dreampath_types import DreamPathAgentState
from instructor import from_openai
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()
client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
SUMMARIZATION_MODEL = "gpt-4o-mini" #"gpt-5-nano"

# -----------------------------------------------------
# Update Summary
# -----------------------------------------------------
def handle_summary_get_context_messages(state: DreamPathAgentState, k=20, h=10):

    # Get recent messages from YOUR format
    recent_start = max(len(state.dreampath_messages) - k, 0)
    recent_messages = state.dreampath_messages[recent_start:]

    # Get new messages to summarize
    new_messages = state.dreampath_messages[state.summary_end:recent_start]
    
    state_updates = {}

    # Summarize new messages
    if len(new_messages) > h:
        print(f"| Summarizing {len(new_messages)} new messages from {state.summary_end} to {recent_start}")
        new_summary = client.chat.completions.create(
            model=SUMMARIZATION_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYS_PROMPT},
                {"role": "assistant", "content": f"<summary>\n...{state.summary}\n</summary>"},
                {"role": "user", "content": f"<new_messages>\n{new_messages}\n</new_messages>"}

            ],
            response_model=str
        )
        new_summary_end = state.summary_end + len(new_messages)

        # Update state
        state_updates["summary"] = new_summary
        state_updates["summary_end"] = new_summary_end

        print(f"| *Initiated updates to state summary*\n{new_summary}\n*[Ends at {new_summary_end}]*")

    return recent_messages, state_updates

# -----------------------------------------------------
# Build Context
# -----------------------------------------------------
def calculate_token_count(messages: list[dict], model="gpt-4o-mini"):
    """Calculate token count for messages using tiktoken's precise method that matches OpenAI's billing."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print(f"Warning: {model} is not a supported model for tiktoken. Using cl100k_base instead.")
        # Fallback to cl100k_base encoding for newer models
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # Use tiktoken's built-in function for precise token counting | matches exactly how OpenAI calculates tokens for chat completions
    tokens_per_message = 3  # every message follows <|start|>{role/name}\n{content}<|end|>\n
    tokens_per_name = 1     # if there's a name, the role is omitted
    
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            if isinstance(value, str):
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
    
    num_tokens += 3  # every reply primed with <|start|>assistant<|message|>
    return num_tokens

# -----------------------------------------------------
# Render Context Blocks
# -----------------------------------------------------
def _render_thread_block(summary: str | None, recent_messages: list[dict]) -> str:
    tail = recent_messages
    lines = []

    if summary:
        lines.append(f"Summary: {summary.strip()}")
    if tail:
        lines.append("Recent Messages Prior to Current Turn:")
        for m in tail:
            role = m.get("role", "user")
            content = m.get("content", "")
                    
            # Handle dictionary content (e.g., tool calls)
            if isinstance(content, dict):
                tag_name = content.get("name", role)
                content_lines = []
                for key, value in content.items():
                    if key != "name":  # Skip the name attribute since it's used as the tag
                        content_lines.append(f"{value}")
                formatted_content = "\n".join(content_lines)
                lines.append(f"<{tag_name}>\n{formatted_content}\n</{tag_name}>")
            else:
                # Handle string content normally
                content = str(content).strip()
                lines.append(f"<{role}>\n{content}\n</{role}>")
            
    return "\n".join(lines) if lines else "None."

def _render_turn_block(current_user_msg: str, turn_messages: list[dict], init_mode: bool=False) -> str:
    lines = []
    if init_mode:
        lines.append(f"<init_message>\n{current_user_msg}\n</init_message>")
    else:
        lines.append(f"<user_msg_for_current_turn>\n{current_user_msg}\n</user_msg_for_current_turn>")
    
    if turn_messages:
        for m in turn_messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            
            if isinstance(content, dict):
                tag_name = content.get("name", role)
                content_lines = []
                for key, value in content.items():
                    if key != "name":  # Skip the name attribute since it's used as the tag
                        content_lines.append(f"{value}")
                formatted_content = "\n".join(content_lines)
                lines.append(f"<{tag_name}>\n{formatted_content}\n</{tag_name}>")
            else:
                # Handle string content normally
                content = str(content).strip()
                lines.append(f"<{role}>\n{content}\n</{role}>")
        
    return "\n".join(lines)

async def _render_dreampath_context_block(user_id: str, student_db_service) -> str:
    """
    Render the DreamPath context block by querying fresh data from the database.

    This ensures we always have the latest student profile and course path,
    avoiding stale data issues with config-based caching.
    """
    # Query fresh data from DB (single source of truth)
    student_profile = await student_db_service.load_student_profile(user_id)
    course_path = await student_db_service.load_course_path(user_id)

    lines = []

    # Add student profile with HTML-like tags
    lines.append(f"<student_profile>\n{str(student_profile)}\n</student_profile>")

    # Add course path with HTML-like tags
    if course_path is not None:
        lines.append(f"<course_path>\n**Important**: student is currently in term {course_path.curr_window_start}\n\n{str(course_path)}\n</course_path>")
    else:
        lines.append("<course_path>\nNo course path yet.\n</course_path>")

    return "\n".join(lines)

# -----------------------------------------------------
# Build Messages
# -----------------------------------------------------
async def build_complete_context(state: DreamPathAgentState, prompt: str, config: dict, task_prompt: str | None=None, init_mode: bool=False):

    # Init messages and go through summarization if needed
    msgs = [{"role": "system", "content": prompt}]
    recent_messages, state_updates = handle_summary_get_context_messages(state)

    # Render context blocks

    # 1) Thread Block (prior to current turn)
    thread_block = _render_thread_block(state.summary, recent_messages)

    # 2) Turn Block (current turn)
    turn_block = _render_turn_block(state.current_user_msg, state.turn_messages, init_mode)

    # 3) Dreampath Context Block - query fresh data from DB
    dreampath_context_block = await _render_dreampath_context_block(
        user_id=config["configurable"]["user_id"],
        student_db_service=config["configurable"]["student_db_service"]
    )

    # 4) Combine all blocks
    conversation_msg = MASTER_CONTEXT.format(thread_block=thread_block, turn_block=turn_block, dreampath_context_block=dreampath_context_block)

    # Add task prompt if provided (i.e. for orchestrator decision)
    if task_prompt:
        conversation_msg += f"\n\n# Task\n{task_prompt}"

    # Add master context to messages
    msgs.append({"role": "system", "content": conversation_msg})

    return msgs, state_updates

async def build_small_context(state: DreamPathAgentState, prompt: str, config: dict, handoff: str, init_mode: bool=False):
    msgs = [{"role": "system", "content": prompt}]

    # 1) Turn Block (current turn)
    turn_block = _render_turn_block(state.current_user_msg, state.turn_messages, init_mode)

    # 2) Dreampath Context Block - query fresh data from DB
    dreampath_context_block = await _render_dreampath_context_block(
        user_id=config["configurable"]["user_id"],
        student_db_service=config["configurable"]["student_db_service"]
    )

    # 3) Combine all blocks
    conversation_msg = MASTER_CONTEXT_SHORT.format(turn_block=turn_block, dreampath_context_block=dreampath_context_block, task=handoff)
    msgs.append({"role": "system", "content": conversation_msg})
    return msgs

# -----------------------------------------------------
# Baseline For Extracting Structured Output from Context
# -----------------------------------------------------
async def extract_structured_output_from_context(state: DreamPathAgentState, config: dict, system_prompt: str, response_model: BaseModel, small_context: bool=False, model="gpt-4o-mini", temperature=0, show_token_count=True, task_prompt: str | None=None, verbose=False):
    if small_context:
        messages = await build_small_context(state, system_prompt, config, state.handoff)
        state_updates = {}
    else:
        messages, state_updates = await build_complete_context(state, system_prompt, config, task_prompt)

    if verbose:
        log_messages_to_file(messages)

    if show_token_count:
        print(f"[ MODEL={model} | TOKEN COUNT: {calculate_token_count(messages, model)} ]")

    if model == "o3-mini" or model == "o4-mini":
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
        )
    else:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=response_model,
            temperature=temperature
        )
    return response, state_updates