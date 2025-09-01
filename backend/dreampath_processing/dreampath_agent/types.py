from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Annotated
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.courses.coursepath_agent.agent import CoursePathAgent
import operator

class OrchestratorDecision(BaseModel):

    next: Literal["plan_builder", "course_search", "course_path", "finalize"]
    # handoff is small and text-first; NO structured op fields
    topics: Optional[List[str]] = Field(default_factory=list)
    handoff: Optional[Dict[str, Any]] = Field(default_factory=dict)
    

# ================================
# Course Search Tool
# ================================
class CourseSearchInput(BaseModel):
    topic: str
    limit: int = 8

class CourseSearchOutput(BaseModel):
    topic: str
    results: List[str] = Field(default_factory=list)

# ================================
# Course Path Agent
# ================================
class CoursePathAgentInput(BaseModel):
    user_message: str
    thread_id: str
    plan_id: str

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

    # Conversation state
    summary: str = Field(default="")
    recent_messages: Annotated[List[Dict[str, str]], operator.add] = Field(default_factory=list)

    # Routing
    route: Optional[Literal["orchestrator", "plan_builder", "course_search", "course_path", "finalize"]] = Field(default=None)
    handoff: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Search + planning
    topics: Optional[List[str]] = Field(default_factory=list)
    search_results: Optional[CourseSearchOutput] = Field(default=None)
    worklist: List[str] = Field(default_factory=list)
    cursor: int = 0
    
    # Last worker outcome + reply
    current_cp_agent_outcomes: Optional[List[CoursePathAgentOutput]] = Field(default=None)
    ui_reply: Optional[str] = Field(default=None)