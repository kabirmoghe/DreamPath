import operator
from typing import Annotated, Literal

from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, constr, field_validator


class OrchestratorDecision(BaseModel):
    route: Literal["course_search", "plan_builder", "course_path", "modify_profile", "rebuild_course_path", "finalize"]
    reason: constr(max_length=200)
    handoff: str | None = Field(default=None, description="The handoff message for the next node")
    confidence: float | None = Field(default=None, description="The confidence in the routing decision")

# ================================
# Course Search Tool
# ================================
class CourseSearchParams(BaseModel):
    query: str | None = Field(default=None, description="The query to search for courses")
    department: str | None = Field(default=None, description="The department of the course")
    course_code: str | None = Field(default=None, description="The code of the course")
    num_prereqs_max: int | None = Field(default=None, description="The maximum number of prerequisites for the course")
    sort_by_level: bool | None = Field(default=False, description="Whether to sort the results by level")
    limit: int | None = Field(default=10, description="The maximum number of results to return")
    alpha: float | None = Field(default=0.5, description="The alpha value for the hybrid search")

class CourseSearchQueries(BaseModel):
    queries: list[CourseSearchParams] = Field(default_factory=list)

class CourseSearchResult(BaseModel):
    """Course search result with all relevant fields"""
    department: str
    course_code: str
    course_title: str
    description: str
    prerequisites: str
    course_url: str
    num_prereqs: int
    total_reviews: int | None = None
    global_difficulty_percentile: float | None = None
    global_difficulty_classification: str | None = None
    dept_difficulty_percentile: float | None = None
    dept_difficulty_classification: str | None = None
    difficulty_blurb: str | None = None
    global_value_percentile: float | None = None
    global_value_classification: str | None = None
    dept_value_percentile: float | None = None
    dept_value_classification: str | None = None
    learning_value_blurb: str | None = None
    target_audience_blurb: str | None = None

class CourseSearchOutput(BaseModel):
    results: list[CourseSearchResult] = Field(default_factory=list)

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
    
    # Routing
    route: Literal["orchestrator", "course_search", "plan_builder", "course_path", "modify_profile", "rebuild_course_path", "finalize"] | None = Field(default=None)
    handoff: str | None = Field(default=None)
    
    # Course path operations
    worklist: list[str] = Field(default_factory=list)
    cursor: int = 0
    current_cp_agent_outcomes: dict[str, CoursePathAgentOutput] | None = Field(default=None)
    
    # Output
    ui_reply: str | None = Field(default=None)
    
    # Interrupt handling
    pending_pre_interrupt: CoursePathAgentOutput | ModifiedStudentProfile | None = Field(default=None)
    
    # NOTE: 'messages' field inherited from MessagesState
    # Contains LangChain BaseMessage objects for service streaming    