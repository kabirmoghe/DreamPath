"""SearchStrategy protocol and resolution for domain-agnostic search agent.

Each domain (course, activity) implements the SearchStrategy protocol.
Nodes resolve the strategy from `state.domain` via `get_strategy()`.
"""

from typing import Protocol, runtime_checkable

from dreampath_processing.dreampath_agent.search_agent.types.base import (
    SearchOutput,
    SearchParams,
    SearchResult,
)
from pydantic import BaseModel


@runtime_checkable
class SearchStrategy(Protocol):
    """Protocol that each search domain must implement."""

    domain_name: str  # "course" or "activity"
    params_type: type[SearchParams]
    result_type: type[SearchResult]
    output_type: type[SearchOutput]

    async def execute_search(self, search_description: str) -> tuple[SearchParams, SearchOutput]:
        """Execute a search from a natural language description.

        The strategy internally uses a query generator to translate the description
        into optimized domain-specific params, then executes the search.

        Returns (params_used, output).
        """
        ...

    def get_orchestrator_prompt_sections(self) -> dict[str, str]:
        """Return domain-specific prompt sections for the orchestrator.

        Keys: search_guidelines, task_guidelines, example
        """
        ...

    def get_orchestrator_result_schema(self) -> type[BaseModel]:
        """Return the domain-specific OrchestratorResult schema for structured output."""
        ...

    def render_result(self, result: dict, compact: bool = False) -> list[str]:
        """Render a single search result.

        compact=True: minimal (code: title) for old iterations.
        compact=False: full details for recent iterations.
        """
        ...

    def render_result_for_summary(self, result: SearchResult, verbosity: int) -> list[str]:
        """Render a single result for the final summary markdown."""
        ...

    def render_task_top_result(self, result_id: str, result_index: dict) -> str:
        """Render a single top_result entry for the task state block."""
        ...

    def get_result_id(self, result: SearchResult) -> str:
        """Extract the canonical ID from a result (e.g., course_code)."""
        ...

    def build_tool_result_entry(self, result: SearchResult) -> dict:
        """Build the dict stored in tool result additional_kwargs for one result."""
        ...


def get_strategy(domain: str) -> SearchStrategy:
    """Resolve a strategy instance from a domain name."""
    from dreampath_processing.dreampath_agent.search_agent.strategies.course_strategy import (
        CourseSearchStrategy,
    )

    strategies: dict[str, type] = {
        "course": CourseSearchStrategy,
        # "activity": ActivitySearchStrategy,  # Phase 2
    }

    if domain not in strategies:
        raise KeyError(f"Unknown search domain '{domain}'. Available: {list(strategies.keys())}")
    return strategies[domain]()
