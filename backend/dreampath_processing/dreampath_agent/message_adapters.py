from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, BaseMessage
from typing import Dict, List
import json
from uuid import uuid4

def generate_tool_call_id() -> str:
    """Generate unique tool call ID."""
    return f"call_{uuid4().hex[:24]}"

def dreampath_to_langchain(msg: Dict[str, str | dict]) -> BaseMessage:
    """
    Convert your dict-format message to LangChain BaseMessage.

    Handles three cases:
    1. User message: {"role": "user", "content": "text"}
    2. Assistant with tool call: {"role": "assistant", "content": {"name": "X", "arguments": {...}}}
    3. Tool result: {"role": "assistant", "content": {"name": "X", "result": "..."}}
    4. Assistant with additional_kwargs (for structured metadata): {"role": "assistant", "content": "text", "additional_kwargs": {...}}
    """
    role = msg.get("role", "user")
    content = msg.get("content", "")
    additional_kwargs = msg.get("additional_kwargs", {})

    # Case 1: User message (string content)
    if role == "user" or role == "system":
        return HumanMessage(content=str(content))

    # Case 2 & 3: Assistant message (may have nested dict)
    if role == "assistant":
        if isinstance(content, dict):
            name = content.get("name", "unknown")

            # Check if this is a tool call (has "arguments") or result (has "result")
            if "arguments" in content:
                # Tool call - convert to AIMessage with tool_calls
                tool_call_id = generate_tool_call_id()
                return AIMessage(
                    content="",  # Tool calls typically have empty content
                    tool_calls=[{
                        "name": name,
                        "args": content.get("arguments", {}),
                        "id": tool_call_id,
                        "type": "tool_call"
                    }],
                    additional_kwargs=additional_kwargs
                )
            elif "result" in content:
                # Tool result - convert to ToolMessage
                result_str = content.get("result", "")
                if not isinstance(result_str, str):
                    result_str = json.dumps(result_str)
                return ToolMessage(
                    content=result_str,
                    name=name,
                    tool_call_id=generate_tool_call_id()  # Should match original call
                )
            else:
                # Generic assistant message with dict content
                return AIMessage(content=json.dumps(content), additional_kwargs=additional_kwargs)
        else:
            # Simple assistant message with string content
            # Preserve additional_kwargs for structured metadata (interrupts, etc.)
            return AIMessage(content=str(content), additional_kwargs=additional_kwargs)

    # Fallback
    return HumanMessage(content=str(content))

def convert_turn_messages(turn_messages: List[Dict[str, str | dict]]) -> List[BaseMessage]:
    """Convert a list of your dict messages to LangChain messages."""
    return [dreampath_to_langchain(msg) for msg in turn_messages]
