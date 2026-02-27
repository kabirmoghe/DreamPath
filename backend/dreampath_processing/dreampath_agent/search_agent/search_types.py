import operator
import time
from typing import Annotated, Any, Literal

from dreampath_processing.dreampath_agent.search_agent.types.base import (
    SearchOutput,
    SearchParams,
    SearchResult,
)
from dreampath_processing.dreampath_agent.search_agent.types.course_types import (
    CourseSearchOutput,
    CourseSearchParams,
    CourseSearchResult,
)
from dreampath_processing.dreampath_agent.search_agent.utils.structured_output import (
    LLMManagedModel,
    llm_field,
    system_field,
)
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Discriminator, Field

# Max iterations safety limit (shared across graph.py and summarize.py)
MAX_ITERATIONS = 20

# Re-export for backwards compatibility
__all__ = [
    "MAX_ITERATIONS",
    "SearchParams", "SearchResult", "SearchOutput",
    "CourseSearchParams", "CourseSearchResult", "CourseSearchOutput",
    "SearchExecution", "SearchTask", "TaskSearch",
    "SearchAction", "TaskUpdate", "TaskUpdateAction", "CompleteAction",
    "NextAction", "OrchestratorResult",
    "TaskSummary", "FinalSearchSummary", "SearchAgentState",
]

# ================================
# Agent State
# ================================

class SearchExecution(BaseModel):
    """Record of a single search execution"""
    params: SearchParams  # generalized from CourseSearchParams
    output: SearchOutput  # generalized from CourseSearchOutput
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

    result_index: dict[str, SearchResult] = system_field(
        default_factory=dict,
        description="id → SearchResult lookup (populated incrementally by search execution)"
    )

    created_iteration: int = system_field(description="When task was created")
    last_updated_iteration: int = system_field(description="When last modified")

    # ============================================
    # LLM-MANAGED (Orchestrator can see and modify)
    # ============================================
    description: str = llm_field(description="What to find")

    status: Literal["not_started", "in_progress", "partially_complete", "complete", "failed"] = llm_field(
        default="not_started",
        description="Current status"
    )

    top_results: list[str] = llm_field(
        default_factory=list,
        description="IDs for most relevant results"
    )

    orchestrator_notes: str | None = llm_field(
        default=None,
        description="Why status was set, what to try next"
    )

    # Backwards-compat property
    @property
    def course_index(self) -> dict[str, SearchResult]:
        """Alias for result_index (backwards compatibility)."""
        return self.result_index

class TaskSearch(BaseModel):
    """Wrapper linking a search description to a specific task.

    The orchestrator emits natural language search descriptions.
    The domain strategy's query generator translates them into optimized search params.
    """
    task_id: int = Field(description="Which task this search is for")
    search_description: str = Field(description="Atomic search description (natural language)")

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
    new_status: Literal["not_started", "in_progress", "partially_complete", "complete", "failed"]
    top_results: list[str] = Field(
        max_length=10,
        description="IDs for most relevant results (max 10)"
    )
    orchestrator_notes: str = Field(description="Guidance for next iteration")

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
NextAction = Annotated[
    SearchAction | TaskUpdateAction | CompleteAction,
    Discriminator('action_type')
]

# ================================
# OrchestratorResult (domain-agnostic)
# ================================
# The orchestrator emits search descriptions (natural language), not domain-specific params.
# A single OrchestratorResult schema works for all domains.

class OrchestratorResult(BaseModel):
    """OrchestratorResult wrapper for OpenAI structured output.

    Note: plain union (no Discriminator) is intentional - Pydantic generates anyOf
    for plain unions, which OpenAI structured output supports."""
    action: SearchAction | TaskUpdateAction | CompleteAction

# ================================
# Final Summary Types
# ================================

class TaskSummary(BaseModel):
    """Structured summary for a single task"""
    task_id: int
    description: str
    status: str
    top_results: list[str] = Field(description="Orchestrator-curated result IDs")
    all_results: list[SearchResult] = Field(description="All unique results found")
    search_attempt_count: int
    total_results_found: int  # Before deduplication across searches
    unique_results_found: int  # After deduplication
    orchestrator_notes: str


class FinalSearchSummary(BaseModel):
    """Complete structured summary of search execution"""
    goal: str
    domain: str = Field(default="course", description="Search domain (course, activity)")
    total_tasks: int
    completed_tasks: int
    partially_completed_tasks: int
    failed_tasks: int
    total_iterations: int
    task_summaries: list[TaskSummary]
    total_unique_results: int
    completion_reasoning: str = Field(default="", description="Orchestrator reasoning for completing search")


# ================================
# Search Agent State
# ================================

class SearchAgentState(BaseModel):
    """State for search agent - execution-scoped only (no cross-execution memory)"""

    # ============================================
    # GOAL & TASK STATE
    # ============================================
    goal: str = Field(description="Original search goal for this execution")
    domain: str = Field(default="course", description="Search domain (course, activity)")
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
    latest_reasoning: str = Field(
        default="",
        description="Most recent orchestrator reasoning (overwritten each iteration)"
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
    structured_summary: FinalSearchSummary | None = Field(default=None)

    # ============================================
    # OBSERVABILITY
    # ============================================
    cumulative_tokens: int = Field(default=0)
    iteration_tokens: list[int] = Field(default_factory=list)

    # ============================================
    # GUARDRAILS
    # ============================================
    system_warning: bool = Field(default=False, description="Whether to warn the system that the search is incomplete")
