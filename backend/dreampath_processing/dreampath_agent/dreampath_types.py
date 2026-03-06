import operator
from typing import Annotated, Literal

from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.dreampath_agent.search_agent.types.course_types import (
    CourseSearchOutput as CourseSearchOutput,
)
from dreampath_processing.dreampath_agent.search_agent.types.course_types import (
    CourseSearchResult as CourseSearchResult,
)
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_validator


# ================================
# Build Mode Types
# ================================
class BuildPhase(BaseModel):
    name: str  # "plan_build", "update_profile", "course_search", "activity_search", "curate", "build_dreampath", "reflect", "refine", "finish"
    status: Literal["pending", "active", "complete", "skipped"] = "pending"
    guidance: str = ""  # set upfront by plan_build, read each turn for phase-specific direction
    notes: str = ""     # set by complete_phase when done, records what actually happened


class BuildPlan(BaseModel):
    phases: list[BuildPhase]  # initialized with the 8 fixed phases
    current_phase: int = 0


class ActivityRec(BaseModel):
    """Activity recommendation with parameter alignment tracking."""
    activity_slug: str
    aligned_parameters: set[Literal["interests", "post_grad", "career"]] = Field(default_factory=set)

    @field_validator("aligned_parameters", mode="before")
    @classmethod
    def convert_list_to_set(cls, v):
        if isinstance(v, list):
            return set(v)
        return v


# ================================
# Course Path Agent
# ================================
class CoursePathAgentInput(BaseModel):
    user_message: str
    thread_id: str
    plan_id: str

# Literal type with all valid Dartmouth majors
ValidMajor = Literal[
    "African and African American Studies",
    "Anthropology",
    "Art History",
    "Asian Societies, Cultures, and Languages",
    "Biological Sciences",
    "Biological Chemistry",
    "Biophysical Chemistry",
    "Chemistry",
    "Ancient History",
    "Classical Archaeology",
    "Classical Languages and Literatures",
    "Classical Studies",
    "Cognitive Science",
    "Comparative Literature",
    "Computer Science",
    "Earth Sciences",
    "Russian",
    "Russian Area Studies",
    "Economics",
    "Biomedical Engineering Sciences",
    "Engineering Physics",
    "Engineering Sciences",
    "English",
    "Film and Media Studies",
    "French",
    "French Studies",
    "Italian",
    "Italian Studies",
    "Romance Languages",
    "Geography",
    "German Studies",
    "Government",
    "History",
    "Latin American, Latino, and Caribbean Studies",
    "Linguistics",
    "Mathematics",
    "Music",
    "Native American Studies",
    "Philosophy",
    "Astronomy",
    "Physics",
    "Neuroscience",
    "Psychology",
    "Quantitative Social Science",
    "Religion",
    "Sociology",
    "Hispanic Studies",
    "Romance Studies",
    "Studio Art",
    "Theater",
    "Women's, Gender & Sexuality Studies",
]

# ================================
# Modify Profile Tool
# ================================
class ModifiedStudentProfile(BaseModel):
    major: ValidMajor  # Now uses Literal type with all valid majors
    college_interests: str
    post_grad_goals: str
    career_goals: str

# ================================
# Rebuild Course Path Tool
# ================================
class CourseRec(BaseModel):
    """Course recommendation with parameter alignment tracking."""
    course_code: str
    aligned_parameters: set[Literal["interests", "post_grad", "career"]] = Field(default_factory=set)

    @field_validator("aligned_parameters", mode="before")
    @classmethod
    def convert_list_to_set(cls, v):
        """Convert list to set if needed (handles JSON deserialization)."""
        if isinstance(v, list):
            return set(v)
        return v


class CourseRecsOutput(BaseModel):
    """Output model for LLM synthesis of course recommendations."""
    recommendations: list[CourseRec] = Field(default_factory=list)


class RebuildCoursePathOutput(BaseModel):
    modified_profile: ModifiedStudentProfile | None = Field(default=None)
    search_summary: str | None = Field(default=None)
    updated_recommended_courses: list[CourseRec] | None = Field(default=None)
    course_path_update_mode: Literal["new", "update_existing"] | None = Field(default=None)
    scheduled_courses_diff: str | None = Field(default=None, description="Summary of changes to scheduled courses")

# ================================
# DreamPath Agent
# ================================
class CoursePathOperations(BaseModel):
    operations: list[str]

class DreamPathAgentState(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    # Thread management
    thread_id: str | None = Field(default=None)
    plan_id: str | None = Field(default=None)
    
    # Historical conversation (YOUR FORMAT for context building)
    summary: str = Field(default="")
    dreampath_messages: Annotated[list[dict[str, str | dict]], operator.add] = Field(default_factory=list)
    messages: Annotated[list[BaseMessage], operator.add] = Field(default_factory=list)
    summary_end: int = 0
    
    # Current turn (YOUR FORMAT for orchestrator isolation)
    init_mode: bool | None = Field(default=False)
    require_user_confirmation: bool | None = Field(default=True)
    current_user_msg: str | None = Field(default=None)
    turn_messages: list[dict[str, str | dict]] = Field(default_factory=list)
    
    # Tool calling (orchestrator → tool_executor → target node)
    pending_tool_call: dict | None = Field(default=None)  # raw {name, arguments, tool_call_id} from orchestrator
    tool_name: str | None = Field(default=None)  # set by tool_executor after parsing
    tool_input: BaseModel | None = Field(default=None)  # typed Pydantic model, set by tool_executor
    
    # Mode
    mode: Literal["advise", "build"] = "advise"
    build_plan: BuildPlan | None = Field(default=None)
    curated_courses: list[CourseRec] = Field(default_factory=list)
    curated_activities: list[ActivityRec] = Field(default_factory=list)

    # Course path operations
    course_worklist: list[str] = Field(default_factory=list)
    course_cursor: int = 0
    current_cp_agent_outcomes: dict[str, CoursePathAgentOutput] | None = Field(default=None)

    # Club path operations (ClubPathOperation objects stored after first entry)
    club_worklist: list = Field(default_factory=list)
    club_cursor: int = 0

    # Output
    ui_reply: str | None = Field(default=None)

    # Interrupt handling
    pending_pre_interrupt: CoursePathAgentOutput | ModifiedStudentProfile | None = Field(default=None)
    
    # NOTE: 'messages' field inherited from MessagesState
    # Contains LangChain BaseMessage objects for service streaming    