from instructor import from_openai
from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Tuple, List, Optional, Dict
import tiktoken
from dreampath_processing.dreampath_agent.types import DreamPathAgentState
from dreampath_processing.dreampath_agent.prompts import SUMMARY_SYS_PROMPT, MASTER_CONTEXT
from dreampath_processing.modules.student_profile import StudentProfile

load_dotenv()

client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

# -----------------------------------------------------
# Update Summary
# -----------------------------------------------------
def handle_summary_get_context_messages(state: DreamPathAgentState, k=20, h=10):

    # Get recent messages
    recent_start = max(len(state.messages) - k, 0)
    recent_messages = state.messages[recent_start:]

    # Get new messages to summarize
    new_messages = state.messages[state.summary_end:recent_start]
    
    state_updates = {}

    # Summarize new messages
    if len(new_messages) > h:
        print(f"Summarizing {len(new_messages)} new messages from {state.summary_end} to {recent_start}")
        new_summary = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SUMMARY_SYS_PROMPT},
                {"role": "assistant", "content": f"<summary>\n...{state.summary}\n</summary>"},
                {"role": "user", "content": f"<new_messages>\n{new_messages}\n</new_messages>"}

            ],
            response_model=str,
            temperature=0
        )
        new_summary_end = state.summary_end + len(new_messages)

        # Update state
        state_updates["summary"] = new_summary
        state_updates["summary_end"] = new_summary_end

        print(f"*Initiated updates to state summary*\n{new_summary}\n*[Ends at {new_summary_end}]*")

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
    
    # Use tiktoken's built-in function for precise token counting
    # This matches exactly how OpenAI calculates tokens for chat completions
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
    
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

# -----------------------------------------------------
# Render Context Blocks
# -----------------------------------------------------
def _render_thread_block(summary: Optional[str], recent_messages: List[Dict]) -> str:
    tail = recent_messages
    lines = []

    if summary:
        lines.append(f"Summary: {summary.strip()}")
    if tail:
        lines.append(f"Recent Messages:")
        for m in tail:
            role = m.get("role", "user")
            content = m.get("content") or ""
                    
            # Handle dictionary content (e.g., tool calls)
            if isinstance(content, dict):
                tag_name = content.get("name", role)
                content_lines = []
                for key, value in content.items():
                    if key != "name":  # Skip the name attribute since it's used as the tag
                        content_lines.append(f"* {key}: {value}")
                formatted_content = "\n".join(content_lines)
                lines.append(f"<{tag_name}>\n{formatted_content}\n</{tag_name}>")
            else:
                # Handle string content normally
                content = str(content).strip()
                lines.append(f"<{role}>\n{content}\n</{role}>")
            
    return "\n".join(lines) if lines else "None."

def _render_dreampath_context_block(student_profile: StudentProfile) -> str:
    lines = ["Dreampath Context:"]
    
    # Add student profile with HTML-like tags
    lines.append(f"<student_profile>\n{str(student_profile)}\n</student_profile>")
    
    # Add course path with HTML-like tags
    lines.append(f"<course_path>\n**Important**: student is currently in term {student_profile.course_path.curr_window_start}\n\n{str(student_profile.course_path)}\n</course_path>")
    
    return "\n".join(lines)

# -----------------------------------------------------
# Build Messages
# -----------------------------------------------------
def build_messages(state: DreamPathAgentState, prompt: str, config: dict, task_prompt: Optional[str]=None):

    # Init messages and go through summarization if needed
    msgs = [{"role": "system", "content": prompt}]
    recent_messages, state_updates = handle_summary_get_context_messages(state)

    # Render context blocks
    thread_block = _render_thread_block(state.summary, recent_messages)
    dreampath_context_block = _render_dreampath_context_block(config["configurable"]["student_profile"])
    conversation_msg = MASTER_CONTEXT.format(thread_block=thread_block, dreampath_context_block=dreampath_context_block)

    # Add task prompt if provided (i.e. for orchestrator decision)
    if task_prompt:
        conversation_msg += f"\n\n# Task\n{task_prompt}"

    # Add master context to messages
    msgs.append({"role": "user", "content": conversation_msg})

    return msgs, state_updates

# -----------------------------------------------------
# Baseline For Extracting Structured Output from Context
# -----------------------------------------------------
def extract_structured_output_from_context(state: DreamPathAgentState, config: dict, system_prompt: str, response_model: BaseModel, model="gpt-4o-mini", temperature=0, verbose=False, show_token_count=True, task_prompt: Optional[str]=None):
    messages, state_updates = build_messages(state, system_prompt, config, task_prompt)
    if verbose:
        print("=== MESSAGES SENT TO LLM ===")
        for i, msg in enumerate(messages):
            print(f"--- Message {i} [role={msg['role']}] ---")
            print(f"Content: {msg['content']}")
        print("=== END MESSAGES ===")

    if show_token_count:
        print(f"[MODEL={model} | TOKEN COUNT: {calculate_token_count(messages, model)}]")

    if model == "o3-mini":
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