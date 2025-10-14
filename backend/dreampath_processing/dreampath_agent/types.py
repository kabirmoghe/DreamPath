from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Annotated
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
import operator

class OrchestratorDecision(BaseModel):
    next: Literal["course_search", "plan_builder", "course_path", "modify_profile", "finalize"]
    handoff: Optional[str] = Field(default=None, description="The handoff message for the next node")

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
    department: str
    department_id: str
    course_code: str
    course_title: str
    description: str
    prerequisites: str
    course_url: str

class CourseSearchOutput(BaseModel):
    results: List[CourseSearchResult] = Field(default_factory=list)

# ================================
# Course Path Agent
# ================================
class CoursePathAgentInput(BaseModel):
    user_message: str
    thread_id: str
    plan_id: str

# ================================
# Modify Profile Tool
# ================================
class ModifiedStudentProfile(BaseModel):
    major: str
    college_interests: str
    post_grad_goals: str
    career_goals: str

# ================================
# DreamPath Agent
# ================================
class CoursePathOperations(BaseModel):
    operations: List[str]

class DreamPathAgentState(BaseModel):
    model_config = {'arbitrary_types_allowed': True}
    
    thread_id: Optional[str] = Field(default=None)
    plan_id: Optional[str] = Field(default=None)
    major: Optional[str] = Field(default=None)

    # Historical conversation state
    summary: str = Field(default="")
    messages: Annotated[List[Dict[str, str | dict]], operator.add] = Field(default_factory=list)
    summary_end: int = 0

    # Current conversation state
    current_user_msg: Optional[str] = Field(default=None)
    turn_messages: List[Dict[str, str | dict]] = Field(default_factory=list)

    # Routing
    route: Optional[Literal["orchestrator", "course_search", "plan_builder", "course_path", "modify_profile", "finalize"]] = Field(default=None)
    handoff: Optional[str] = Field(default=None)

    # Search + planning
    topics: Optional[Dict[str, int]] = Field(default_factory=dict)
    search_results: Optional[CourseSearchOutput] = Field(default=None)
    worklist: List[str] = Field(default_factory=list)
    cursor: int = 0
    
    # Current CoursePath Agent outcome + reply
    current_cp_agent_outcomes: Optional[Dict[str, CoursePathAgentOutput]] = Field(default=None)
    ui_reply: Optional[str] = Field(default=None)
    
    # Pending profile modification (used to avoid re-computing on interrupt resume)
    pending_profile_modification: Optional["ModifiedStudentProfile"] = Field(default=None)