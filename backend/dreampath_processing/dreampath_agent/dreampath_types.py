from pydantic import BaseModel, Field, constr
from typing import Optional, List, Dict, Literal, Annotated, Set
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
import operator
from langchain_core.messages import BaseMessage

class OrchestratorDecision(BaseModel):
    route: Literal["course_search", "plan_builder", "course_path", "modify_profile", "rebuild_course_path", "finalize"]
    reason: constr(max_length=200)
    handoff: Optional[str] = Field(default=None, description="The handoff message for the next node")
    confidence: Optional[float] = Field(default=None, description="The confidence in the routing decision")

# ================================
# Course Search Tool
# ================================
class CourseSearchParams(BaseModel):
    query: Optional[str] = Field(default=None, description="The query to search for courses")
    department: Optional[str] = Field(default=None, description="The department of the course")
    course_code: Optional[str] = Field(default=None, description="The code of the course")
    num_prereqs_max: Optional[int] = Field(default=None, description="The maximum number of prerequisites for the course")
    sort_by_level: Optional[bool] = Field(default=False, description="Whether to sort the results by level")
    limit: Optional[int] = Field(default=10, description="The maximum number of results to return")
    alpha: Optional[float] = Field(default=0.5, description="The alpha value for the hybrid search")

class CourseSearchQueries(BaseModel):
    queries: List[CourseSearchParams] = Field(default_factory=list)

class CourseSearchResult(BaseModel):
    """Course search result with all relevant fields"""
    department: str
    course_code: str
    course_title: str
    description: str
    prerequisites: str
    course_url: str
    num_prereqs: int
    total_reviews: Optional[int] = None
    global_difficulty_percentile: Optional[float] = None
    global_difficulty_classification: Optional[str] = None
    dept_difficulty_percentile: Optional[float] = None
    dept_difficulty_classification: Optional[str] = None
    difficulty_blurb: Optional[str] = None
    global_value_percentile: Optional[float] = None
    global_value_classification: Optional[str] = None
    dept_value_percentile: Optional[float] = None
    dept_value_classification: Optional[str] = None
    learning_value_blurb: Optional[str] = None
    target_audience_blurb: Optional[str] = None

class CourseSearchOutput(BaseModel):
    results: List[CourseSearchResult] = Field(default_factory=list)

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
class RebuildCoursePathOutput(BaseModel):
    modified_profile: Optional[ModifiedStudentProfile] = Field(default=None)
    course_search_queries_by_parameter: Optional[Dict[str, CourseSearchQueries]] = Field(default=None)
    updated_recommended_courses: Optional[Set[str]] = Field(default=None)
    course_path_update_mode: Optional[Literal["new", "update_existing"]] = Field(default=None)

# ================================
# DreamPath Agent
# ================================
class CoursePathOperations(BaseModel):
    operations: List[str]

class DreamPathAgentState(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    # Thread management
    thread_id: Optional[str] = Field(default=None)
    plan_id: Optional[str] = Field(default=None)
    
    # Historical conversation (YOUR FORMAT for context building)
    summary: str = Field(default="")
    dreampath_messages: Annotated[List[Dict[str, str | dict]], operator.add] = Field(default_factory=list)
    messages: Annotated[List[BaseMessage], operator.add] = Field(default_factory=list)
    summary_end: int = 0
    
    # Current turn (YOUR FORMAT for orchestrator isolation)
    init_mode: Optional[bool] = Field(default=False)
    require_user_confirmation: Optional[bool] = Field(default=True)
    current_user_msg: Optional[str] = Field(default=None)
    turn_messages: List[Dict[str, str | dict]] = Field(default_factory=list)
    
    # Routing
    route: Optional[Literal["orchestrator", "course_search", "plan_builder", 
                            "course_path", "modify_profile", "rebuild_course_path", "finalize"]] = Field(default=None)
    handoff: Optional[str] = Field(default=None)
    
    # Course path operations
    worklist: List[str] = Field(default_factory=list)
    cursor: int = 0
    current_cp_agent_outcomes: Optional[Dict[str, CoursePathAgentOutput]] = Field(default=None)
    
    # Output
    ui_reply: Optional[str] = Field(default=None)
    
    # Interrupt handling
    pending_pre_interrupt: Optional[CoursePathAgentOutput | ModifiedStudentProfile] = Field(default=None)
    
    # NOTE: 'messages' field inherited from MessagesState
    # Contains LangChain BaseMessage objects for service streaming
