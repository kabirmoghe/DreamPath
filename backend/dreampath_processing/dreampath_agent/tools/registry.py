"""Tool registry mapping tool names to input models and LangGraph node names.

Provides helpers to generate OpenAI tool definitions and route tool calls.
"""


from pydantic import BaseModel

from .schemas import (
    CareerSearchInput,
    CoursePathInput,
    CourseSearchInput,
    ModifyProfileInput,
    PlanBuilderInput,
    RebuildCoursePathInput,
    RespondInput,
)

# Each entry: (tool_name, input_model, langgraph_node_name)
_REGISTRY: list[tuple[str, type[BaseModel], str]] = [
    ("course_search", CourseSearchInput, "course_search"),
    ("career_search", CareerSearchInput, "career_search"),
    ("plan_builder", PlanBuilderInput, "plan_builder"),
    ("course_path", CoursePathInput, "course_path"),
    ("modify_profile", ModifyProfileInput, "modify_profile"),
    ("rebuild_course_path", RebuildCoursePathInput, "rebuild_course_path"),
    ("respond", RespondInput, "finalize"),
]

_TOOL_TO_MODEL = {name: model for name, model, _ in _REGISTRY}
_TOOL_TO_NODE = {name: node for name, _, node in _REGISTRY}


def get_openai_tools() -> list[dict]:
    """Generate the `tools` list for an OpenAI chat completions call.

    Uses strict mode so OpenAI guarantees output matches the schema exactly.
    This requires additionalProperties=false and all properties in required.
    """
    tools = []
    for name, model, _ in _REGISTRY:
        schema = model.model_json_schema()
        # Remove pydantic metadata keys that OpenAI doesn't need
        schema.pop("title", None)
        schema.pop("description", None)
        # Strict mode requires additionalProperties: false
        schema["additionalProperties"] = False

        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": model.__doc__.strip() if model.__doc__ else "",
                "parameters": schema,
                "strict": True,
            },
        })
    return tools


def get_node_for_tool(tool_name: str) -> str:
    """Map a tool name to the corresponding LangGraph node name."""
    if tool_name not in _TOOL_TO_NODE:
        raise ValueError(f"Unknown tool: {tool_name!r}. Valid tools: {list(_TOOL_TO_NODE)}")
    return _TOOL_TO_NODE[tool_name]


def get_input_model(tool_name: str) -> type[BaseModel]:
    """Return the Pydantic model class for a given tool name."""
    if tool_name not in _TOOL_TO_MODEL:
        raise ValueError(f"Unknown tool: {tool_name!r}. Valid tools: {list(_TOOL_TO_MODEL)}")
    return _TOOL_TO_MODEL[tool_name]


def get_all_tool_names() -> list[str]:
    """Return all registered tool names."""
    return [name for name, _, _ in _REGISTRY]
