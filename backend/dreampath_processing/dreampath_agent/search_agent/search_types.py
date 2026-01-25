import operator
import time
from typing import Annotated, Any, Literal, Union

from dreampath_processing.dreampath_agent.dreampath_types import CourseSearchOutput
from dreampath_processing.dreampath_agent.search_agent.utils.structured_output import (
    LLMManagedModel,
    llm_field,
    system_field,
)
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_validator

# Valid Dartmouth departments (from course catalog)
ValidDepartment = Literal[
    "African and African American Studies",
    "Anthropology",
    "Art History",
    "Asian Societies, Cultures, and Languages",
    "Biological Sciences",
    "Chemistry",
    "Classics",
    "Cognitive Science",
    "College Courses",
    "Comparative Literature",
    "Computer Science",
    "Divisional Courses",
    "Earth Sciences",
    "East European, Eurasian, and Russian Studies",
    "Economics",
    "Education",
    "Engineering Sciences",
    "English and Creative Writing",
    "Environmental Studies Program",
    "Film and Media Studies",
    "French and Italian Languages and Literatures",
    "Geography",
    "German Studies",
    "Government",
    "History",
    "Humanities",
    "Institute for Writing and Rhetoric",
    "Jewish Studies",
    "Latin American Latino and Caribbean Studies",
    "Linguistics",
    "Mathematics",
    "Middle Eastern Studies",
    "Music",
    "Native American and Indigenous Studies",
    "Philosophy",
    "Physics and Astronomy",
    "Psychological and Brain Sciences",
    "Quantitative Social Science",
    "Religion",
    "Sociology",
    "Spanish and Portuguese Languages and Literatures",
    "Speech",
    "Studio Art",
    "The John Sloan Dickey Center For International Understanding",
    "The Nelson A Rockefeller Center for Public Policy",
    "Theater",
    "Tuck Undergraduate",
    "Womens, Gender, and Sexuality Studies Program",
]

# Valid difficulty classifications (from review data)
ValidDifficulty = Literal["Low", "Medium", "High"]

# Valid learning value classifications (from review data)
ValidValue = Literal["Low", "Medium", "High"]

class CourseSearchParams(BaseModel):
    """
    Simplified course search parameters for Weaviate hybrid search.

    Design decisions:
    - Percentile filters removed: Classifications (Low/Medium/High) are simpler and sufficient
    - Level range filters removed: sort_by_level handles "advanced"/"upper-level" queries
    """
    # Semantic search
    query: str | None = Field(default=None, description="The semantic/keyword query to search for courses")
    alpha: float | None = Field(default=0.5, description="Hybrid search weight (0=keyword, 1=semantic)")

    # Filters - Department & Course
    department: ValidDepartment | None = Field(default=None, description="The department to filter by")
    course_code: str | None = Field(default=None, description="Specific course code to search for")

    # Filters - Prerequisites
    max_num_prereqs: int | None = Field(default=None, description="Maximum number of prerequisites")

    # Filters - Difficulty (classification only, percentiles for UI display)
    difficulty_classification: ValidDifficulty | None = Field(default=None, description="Difficulty level filter")

    # Filters - Learning Value (classification only, percentiles for UI display)
    value_classification: ValidValue | None = Field(default=None, description="Learning value classification filter")

    # Modifiers
    sort_by_level: bool | None = Field(default=False, description="Whether to sort results by course level number")
    limit: int | None = Field(default=10, description="Maximum number of results to return")

# ================================
# Agent State
# ================================

class SearchExecution(BaseModel):
    """Record of a single search execution"""
    params: CourseSearchParams # single hybrid input query params
    output: CourseSearchOutput # output course result(s)
    timestamp: float = Field(default_factory=time.time)
    iteration: int

class SearchTask(LLMManagedModel):
    """Search task with LLM visibility control"""

    # ============================================
    # SYSTEM-MANAGED (Hidden from orchestrator)
    # ============================================
    task_id: int = system_field(description="Auto-assigned task ID")

    search_executions: list[SearchExecution] = system_field(
        default_factory=list,
        description="Complete search history with params + outputs (system-managed)"
    )

    created_iteration: int = system_field(description="When task was created")
    last_updated_iteration: int = system_field(description="When last modified")

    # ============================================
    # LLM-MANAGED (Orchestrator can see and modify)
    # ============================================
    description: str = llm_field(description="What to find")

    status: Literal["not_started", "in_progress", "complete", "failed"] = llm_field(
        default="not_started",
        description="Current status"
    )

    top_results: list[str] = llm_field(
        default_factory=list,
        description="Course codes for most relevant results"
    )

    orchestrator_notes: str | None = llm_field(
        default=None,
        description="Why status was set, what to try next"
    )

class TaskSearch(BaseModel):
    """Wrapper linking a search to a specific task"""
    task_id: int = Field(description="Which task this search is for")
    action_type: Literal["module_search", "manual_search"] = "module_search"
    search_input: str | CourseSearchParams = Field(description="Search input: single string search descriotion module_search(search_input) or refined params for manual_search(params)")

    @field_validator('search_input')
    @classmethod
    def validate_search_input(cls, v, info):
        """Validate search_input type matches action_type"""
        action_type = info.data.get('action_type')
        if action_type == "module_search" and not isinstance(v, str):
            raise ValueError("module_search requires string search_input")
        if action_type == "manual_search" and not isinstance(v, CourseSearchParams):
            raise ValueError("manual_search requires CourseSearchParams search_input")
        return v

# ================================
# Structured Orchestrator Actions
# ================================

class SearchAction(BaseModel):
    """Execute one or more searches in parallel"""
    action_type: Literal["search"] = Field(default="search", description="Action type discriminator")
    searches: list[TaskSearch] = Field(
        min_length=1,
        max_length=5,
        description="1-5 atomic searches with task_id assignments"
    )
    reasoning: str = Field(description="Why these searches were chosen")

class TaskUpdate(BaseModel):
    """Single task update (status, top results, and notes)"""
    task_id: int
    new_status: Literal["not_started", "in_progress", "complete", "failed"]
    top_results: list[str] = Field(
        max_length=10,
        description="Course codes for most relevant results (max 10)"
    )
    orchestrator_notes: str = Field(description="Guidance for next iteration")
    # Note: search_executions updated automatically by search execution, not by LLM

class TaskUpdateAction(BaseModel):
    """Update task statuses and notes (results updated automatically by searches)"""
    action_type: Literal["update_tasks"] = Field(default="update_tasks", description="Action type discriminator")
    task_updates: list[TaskUpdate] = Field(description="Updates for each task")
    reasoning: str = Field(description="Why these updates")

class CompleteAction(BaseModel):
    """All tasks done, ready to finalize"""
    action_type: Literal["complete"] = Field(default="complete", description="Action type discriminator")
    reasoning: str = Field(description="Why search is complete")

# Union type for routing
NextAction = Union[SearchAction, TaskUpdateAction, CompleteAction]

# ================================
# Search Agent State
# ================================

class SearchAgentState(BaseModel):
    """State for search agent - execution-scoped only (no cross-execution memory)"""

    # ============================================
    # GOAL & TASK STATE
    # ============================================
    goal: str = Field(description="Original search goal for this execution")
    tasks: list[SearchTask] = Field(default_factory=list, description="Current task list")

    # ============================================
    # SEARCH TRACE (accumulates across all iterations within THIS execution)
    # ============================================
    search_trace: list[dict[str, Any]] = Field(
        default_factory=list,
        description="All orchestrator decisions + tool results across all iterations"
    )

    # =============================================
    # ITERATION COUNTER
    # ============================================
    iteration: int = Field(default=0, description="Current iteration number")

    # ============================================
    # ORCHESTRATOR OUTPUT (drives routing)
    # ============================================
    next_action: NextAction | None = Field(
        default=None,
        description="Structured action from orchestrator (search/update/complete)"
    )

    # ============================================
    # STREAMING & METADATA
    # ============================================
    messages: Annotated[list[BaseMessage], operator.add] = Field(
        default_factory=list,
        description="LangChain messages for streaming to frontend ONLY"
    )

    # ============================================
    # FINAL OUTPUT
    # ============================================
    final_summary: str | None = Field(default=None)

    # ============================================
    # OBSERVABILITY
    # ============================================
    cumulative_tokens: int = Field(default=0)
    iteration_tokens: list[int] = Field(default_factory=list)
    