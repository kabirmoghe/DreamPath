"""Tool registry mapping tool names to input models and LangGraph node names.

Provides helpers to generate OpenAI tool definitions and route tool calls.
Supports mode-aware filtering (advise vs build).
"""


from pydantic import BaseModel

from .schemas import (
    ActivitySearchInput,
    BuildDreampathInput,
    CareerSearchInput,
    ChangeModeInput,
    ClubPathInput,
    CompletePhaseInput,
    CoursePathInput,
    CourseSearchInput,
    CurateInput,
    ModifyProfileInput,
    PlanBuildInput,
    RespondInput,
)

# Each entry: (tool_name, input_model, langgraph_node_name, available_modes)
_REGISTRY: list[tuple[str, type[BaseModel], str, set[str]]] = [
    ("course_search", CourseSearchInput, "course_search", {"advise", "build"}),
    ("activity_search", ActivitySearchInput, "activity_search", {"advise", "build"}),
    ("career_search", CareerSearchInput, "career_search", {"advise", "build"}),
    ("course_path", CoursePathInput, "course_path", {"advise", "build"}),
    ("club_path", ClubPathInput, "club_path", {"advise", "build"}),
    ("modify_profile", ModifyProfileInput, "modify_profile", {"advise", "build"}),
    ("respond", RespondInput, "finalize", {"advise", "build"}),
    ("change_mode", ChangeModeInput, "change_mode", {"advise", "build"}),
    ("plan_build", PlanBuildInput, "plan_build", {"build"}),
    ("curate", CurateInput, "curate", {"build"}),
    ("build_dreampath", BuildDreampathInput, "build_dreampath", {"build"}),
    ("complete_phase", CompletePhaseInput, "complete_phase", {"build"}),
]

_TOOL_TO_MODEL = {name: model for name, model, _, _ in _REGISTRY}
_TOOL_TO_NODE = {name: node for name, _, node, _ in _REGISTRY}


def get_openai_tools(mode: str = "advise") -> list[dict]:
    """Generate the `tools` list for an OpenAI chat completions call.

    Uses strict mode so OpenAI guarantees output matches the schema exactly.
    Filters tools by the current agent mode.
    """
    tools = []
    for name, model, _, modes in _REGISTRY:
        if mode not in modes:
            continue

        schema = model.model_json_schema()
        # Remove pydantic metadata keys that OpenAI doesn't need
        schema.pop("title", None)
        schema.pop("description", None)
        # Strict mode requires additionalProperties: false at every level
        # and all properties in 'required' (no defaults allowed)
        schema["additionalProperties"] = False
        schema["required"] = list(schema.get("properties", {}).keys())
        for prop in schema.get("properties", {}).values():
            prop.pop("default", None)
        for def_schema in schema.get("$defs", {}).values():
            def_schema.pop("title", None)
            def_schema["additionalProperties"] = False
            if "properties" in def_schema:
                def_schema["required"] = list(def_schema["properties"].keys())
                for prop in def_schema["properties"].values():
                    prop.pop("default", None)

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
    return [name for name, _, _, _ in _REGISTRY]
