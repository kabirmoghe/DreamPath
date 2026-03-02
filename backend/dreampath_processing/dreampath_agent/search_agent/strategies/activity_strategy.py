"""Activity search strategy implementation.

Bundles all activity-specific logic: search execution (with query generator),
prompt sections, rendering, and type mappings.
"""

import asyncio
import os

from dreampath_processing.dreampath_agent.search_agent.search_types import (
    OrchestratorResult,
)
from dreampath_processing.dreampath_agent.search_agent.types.activity_types import (
    ActivitySearchOutput,
    ActivitySearchParams,
    ActivitySearchResult,
)
from dreampath_processing.dreampath_agent.search_agent.types.base import (
    SearchOutput,
    SearchParams,
    SearchResult,
)
from pydantic import BaseModel

# ============================================
# Query Generator Singleton
# ============================================

_query_generator = None


def _get_activity_query_generator():
    """Lazy initialization of activity query generator with async client."""
    global _query_generator

    if _query_generator is None:
        from dreampath_processing.dreampath_agent.search_agent.tools.activity_query_generator import (
            ActivityQueryGenerator,
        )
        from openai import AsyncOpenAI, OpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not set - required for activity search")

        sync_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        _query_generator = ActivityQueryGenerator(sync_client, async_client=async_client)
        _query_generator.configure(model="gpt-4o-mini")

    return _query_generator


class ActivitySearchStrategy:
    """Strategy for searching the activity/club catalog."""

    domain_name = "activity"
    params_type = ActivitySearchParams
    result_type = ActivitySearchResult
    output_type = ActivitySearchOutput

    # ========================================
    # Search Execution
    # ========================================

    async def execute_search(self, search_description: str) -> tuple[SearchParams, SearchOutput]:
        """Execute an activity search: query generator -> Weaviate.

        Args:
            search_description: Natural language search description from orchestrator.

        Returns:
            (generated_params, search_results) tuple.
        """
        query_generator = _get_activity_query_generator()
        params = await query_generator.generate_async(search_description)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._search_sync, params)
        return (params, result)

    @staticmethod
    def _search_sync(params: ActivitySearchParams) -> ActivitySearchOutput:
        """Synchronous Weaviate search (called via run_in_executor)."""
        from dreampath_processing.dreampath_agent.search_agent.tools.activity_search_client import (
            ActivitySearchClient,
        )

        client = ActivitySearchClient()
        try:
            return client.structured_hybrid_search(params)
        finally:
            client.close()

    # ========================================
    # Orchestrator Prompt Sections
    # ========================================

    def get_orchestrator_prompt_sections(self) -> dict[str, str]:
        """Return activity-specific prompt sections."""
        return {
            "search_guidelines": ACTIVITY_SEARCH_GUIDELINES,
            "task_guidelines": ACTIVITY_TASK_GUIDELINES,
            "example": ACTIVITY_EXAMPLE,
        }

    def get_orchestrator_result_schema(self) -> type[BaseModel]:
        """Return OrchestratorResult for OpenAI structured output."""
        return OrchestratorResult

    # ========================================
    # Rendering: Tool Results (context/building.py)
    # ========================================

    def render_result(self, result: dict, compact: bool = False) -> list[str]:
        """Render an activity result. Compact for old iterations, full for recent."""
        if compact:
            return [f" - {result['slug']}: {result['name']}"]

        lines = []
        lines.append(f"{result['slug']} - {result['name']}")
        meta_parts = []
        if result.get("domain"):
            meta_parts.append(f"Domain: {result['domain']}")
        if result.get("activity_type"):
            meta_parts.append(f"Type: {result['activity_type']}")
        if result.get("selectivity"):
            meta_parts.append(f"Selectivity: {result['selectivity']}")
        if result.get("time_commitment"):
            meta_parts.append(f"Time: {result['time_commitment']}")
        if meta_parts:
            lines.append(f"   {', '.join(meta_parts)}")

        mission = result.get("mission", "")
        if mission:
            lines.append(f"   Mission: {mission}")

        skills = result.get("skills", [])
        if skills:
            lines.append(f"   Skills: {', '.join(skills[:6])}")

        career = result.get("career_alignment", [])
        if career:
            lines.append(f"   Career Alignment: {', '.join(career[:4])}")

        return lines

    # ========================================
    # Rendering: Task State (context/building.py)
    # ========================================

    def render_task_top_result(self, result_id: str, result_index: dict) -> str:
        """Render a top_result entry in the task state block."""
        result = result_index.get(result_id)
        if result:
            mission = result.description[:200] + "..." if result.description and len(result.description) > 200 else (result.description or "No description")
            title = result.title if hasattr(result, "title") else getattr(result, "display_name", "")
            return f"- {result_id}: {title} | {mission}"
        return f"- {result_id}"

    # ========================================
    # Rendering: Final Summary (summarize.py)
    # ========================================

    def render_result_for_summary(self, result: SearchResult, verbosity: int) -> list[str]:
        """Render a single result for the final markdown summary."""
        if not isinstance(result, ActivitySearchResult):
            return [f"**{result.id}: {result.title}**", ""]

        activity = result
        lines = []

        if verbosity == 0:
            # Minimal
            lines.append(f"**{activity.display_name}** (`{activity.activity_slug}`)")
            meta = []
            if activity.domain:
                meta.append(f"Domain: {activity.domain}")
            if activity.selectivity_est:
                meta.append(f"Selectivity: {activity.selectivity_est}")
            if activity.time_commitment_est:
                meta.append(f"Time: {activity.time_commitment_est}")
            if meta:
                lines.append(f"- {' | '.join(meta)}")
            if activity.skills_exposed:
                lines.append(f"- Skills: {', '.join(activity.skills_exposed[:4])}")
            lines.append("")

        elif verbosity == 1:
            # Medium
            lines.append(f"**{activity.display_name}** (`{activity.activity_slug}`)")
            if activity.mission_synth:
                mission = activity.mission_synth[:300]
                if len(activity.mission_synth) > 300:
                    mission += "..."
                lines.append(f"- {mission}")
            meta = []
            if activity.domain:
                meta.append(f"Domain: {activity.domain}")
            if activity.activity_type:
                meta.append(f"Type: {activity.activity_type}")
            if activity.selectivity_est:
                meta.append(f"Selectivity: {activity.selectivity_est}")
            if activity.time_commitment_est:
                meta.append(f"Time: {activity.time_commitment_est}")
            if meta:
                lines.append(f"- {' | '.join(meta)}")
            if activity.skills_exposed:
                lines.append(f"- Skills: {', '.join(activity.skills_exposed[:6])}")
            if activity.career_alignment:
                lines.append(f"- Career Alignment: {', '.join(activity.career_alignment[:4])}")
            lines.append("")

        else:
            # Full (verbosity >= 2)
            lines.append(f"<activity>**{activity.display_name}** (`{activity.activity_slug}`)")
            if activity.activity_type:
                lines.append(f"- Type: {activity.activity_type}")
            if activity.domain:
                lines.append(f"- Domain: {activity.domain}")
            if activity.mission_synth:
                lines.append(f"- Mission: {activity.mission_synth}")
            if activity.what_you_do_synth:
                lines.append(f"- What You Do: {activity.what_you_do_synth}")
            if activity.who_its_for_synth:
                lines.append(f"- Who It's For: {activity.who_its_for_synth}")
            if activity.how_to_join_synth:
                lines.append(f"- How to Join: {activity.how_to_join_synth}")
            meta = []
            if activity.selectivity_est:
                meta.append(f"Selectivity: {activity.selectivity_est}")
            if activity.time_commitment_est:
                meta.append(f"Time Commitment: {activity.time_commitment_est}")
            if activity.owner_type:
                meta.append(f"Owner: {activity.owner_type}")
            if meta:
                lines.append(f"- {' | '.join(meta)}")
            if activity.skills_exposed:
                lines.append(f"- Skills: {', '.join(activity.skills_exposed)}")
            if activity.career_alignment:
                lines.append(f"- Career Alignment: {', '.join(activity.career_alignment)}")
            if activity.subtags:
                lines.append(f"- Tags: {', '.join(activity.subtags)}")
            if activity.source_of_truth_url:
                lines.append(f"- URL: {activity.source_of_truth_url}")
            lines.append("</activity>")

        return lines

    # ========================================
    # ID and Entry Building
    # ========================================

    def get_result_id(self, result: SearchResult) -> str:
        """Extract activity_slug as the canonical ID."""
        if isinstance(result, ActivitySearchResult):
            return result.activity_slug
        return result.id

    def build_tool_result_entry(self, result: SearchResult) -> dict:
        """Build dict for a single activity result in tool result data."""
        if not isinstance(result, ActivitySearchResult):
            return {
                "slug": result.id,
                "name": result.title,
                "mission": result.description or "",
            }

        return {
            "slug": result.activity_slug,
            "name": result.display_name,
            "domain": result.domain,
            "activity_type": result.activity_type,
            "mission": result.mission_synth or "",
            "selectivity": result.selectivity_est,
            "time_commitment": result.time_commitment_est,
            "skills": result.skills_exposed or [],
            "career_alignment": result.career_alignment or [],
        }


# ============================================
# Activity-specific prompt sections
# ============================================

ACTIVITY_SEARCH_GUIDELINES = """## SearchAction: Search Guidelines
For each search, you provide a natural language `search_description` string.
A trained query generator will automatically determine the best search parameters (query terms, domain filters, selectivity, time commitment, etc.).

**Important context**: The activity catalog is relatively small (~20 activities across clubs, labs, and research groups). Broad searches often surface most relevant options in one round.

**Search descriptions should be**:
- Atomic: specific, focused, single-query scope
- Use terms likely found in activity descriptions (e.g., "community service" instead of "giving back")
- If relevant, mention at most ONE domain, ONE selectivity level, ONE time commitment level

**Search capabilities** (the query generator can handle these automatically):
- Domain filtering (e.g., "in tech", "finance-related", "sports clubs")
- Selectivity preferences (e.g., "easy to join", "competitive", "open membership")
- Time commitment preferences (e.g., "low commitment", "intensive", "seasonal")

**Examples of good search descriptions**:
- "Tech clubs focused on software engineering and product development"
- "Low commitment consulting or business clubs"
- "Research labs in AI or machine learning"
- "Open-membership community service organizations"

**Semantic queries CAN include multiple related concepts**:
  ✓ "machine learning AI data science" → GOOD: one search
  ✓ "consulting business strategy" → GOOD: one search
  ✗ "tech clubs and sports teams" → BAD: unrelated domains, use separate searches

### Search Strategy
- **Use filters when the task explicitly calls for them** — e.g., "open-membership sports clubs" warrants both selectivity and domain filters. But **do not infer filters from ambiguous context.** If the task says "hands-on experience," that doesn't imply a specific activity type, selectivity, or time commitment.
- **If results are empty or poor**: The most likely cause on a small catalog is over-filtering. Before giving up, prompt the query generator to generate new parameters with loosened or removed filters and rely more on the semantic query.
  - If specific terms don't return results the first time around, try rephrasing with related skills, domains, or underlying disciplines.
  - E.g., "product management" might not appear directly → try "tech product development" or "consulting"
  - E.g., "quantitative trading" → try "finance" or "quantitative analysis"
  - E.g., "leadership" is developed across clubs, sports, and service organizations — broaden if initial results are narrow
- Given the small catalog, 2-3 search rounds per task is usually sufficient. But **never mark a task failed after a single empty search** — always retry with loosened filters first."""

ACTIVITY_TASK_GUIDELINES = """## TaskUpdateAction: Task Update Guidelines
When returning TaskUpdateAction:

### 1. Initial Task Creation
Guidelines for task decomposition:
- CREATE SEPARATE TASKS when the goal involves distinct domains or activity types
  Example: "Tech clubs AND community service" → 2 tasks (different domains)

- KEEP AS ONE TASK when multiple constraints apply to the SAME search
  Example: "Low commitment, easy to join finance clubs" → 1 task (filters on same search)

- KEEP AS ONE TASK for information about a specific activity
  Example: "Find info about DALI Lab" → 1 task (look up activity)

- Keep task count low — with a small catalog (~20 activities), 1-3 tasks is typically sufficient.

### 2. Mid-Turn Task Analysis
For each in-progress or non-started task, analyze the corresponding results.

#### Top Results Curation
The top_results field is YOUR selection of the best activities that satisfy the task description.
- Review search_executions to see all activities found
- Consider diversity of skills, time commitment, selectivity, and relevance
- Avoid highly similar activities unless there's a clear reason to include both

- **Only include activities whose mission and skills directly address the task description.**
- It is better to have 1-2 genuinely relevant activities (or zero, with a "failed" status) than padding with tangentially related ones.

**Choose up to 5 most relevant activity slugs.**

#### Status Determination
- Set status based on result quality (not just presence of results)
- Mark / keep tasks "in_progress" if there is still potential for improved results.

**Terminal statuses:**
- "complete" — top_results contain activities that address the task well
- "partially_complete" — decent but imperfect matches found
- "failed" — after 2-3 search rounds with poor results; the catalog is small, so exhausting options happens quickly. It is perfectly acceptable to fail when no activities match.

#### Orchestrator Note Bookkeeping
- Note which activities are strong vs weak matches
- Track which domains/types have been explored
- Suggest alternative search angles for in-progress tasks

## CompleteAction: Complete Guidelines
Before returning CompleteAction, verify all tasks are terminal (completed, partially completed, or failed).
This signals the end of search execution for the provided goal."""

ACTIVITY_EXAMPLE = """# Core Example

This example illustrates two key behaviors: (1) recovering from over-filtered empty results by diagnosing which filters were too restrictive and loosening them, and (2) efficient completion when results are strong.

## Recovery from Over-Filtering + Direct Success

Goal: "Find info on medium-commitment CS clubs for important industry skills in SWE experience and also community service activities"

Iteration 0 → TaskUpdateAction
  Task 1: "Identify medium-commitment computer science-oriented clubs for software engineering experience, things like full-stack web development, design, product management, etc."
  Task 2: "Find community service or volunteering organizations"

Iteration 1 → SearchAction
  Task 1: search("medium commitment CS clubs, full-stack web development, design, product")
  Task 2: search("community service volunteering organizations")
  → Task 1: generated params had query="medium commitment computer science, full-stack dev, design, product" + time_commitment_est=medium → 0 results (over-filtered)
  → Task 2: finds Dartmouth EMS and other service activities

Iteration 2 → TaskUpdateAction
  Task 1: in_progress | top_results: []
  Notes: "0 results. Looking at generated params: time_commitment_est=medium is too restrictive. Need to loosen the filter."
  Task 2: complete | top_results: [dartmouth-ems]
  Notes: "EMS is a direct match for hands-on community service."

Iteration 3 → SearchAction
  Task 1: search("CS clubs, full-stack web development, design, product")
  → Broader search without filter-triggering language → finds DALI Lab and other tech-adjacent activities

Iteration 4 → TaskUpdateAction
  Task 1: complete | top_results: [dali-lab]
  Notes: "DALI Lab is a strong match — hands-on software skills with interesting, broad industry experience with real clients."

Iteration 5 → CompleteAction
  "Both tasks completed. DALI Lab for software skills with highly relevant industry software engineering experience, Dartmouth EMS for community service."
"""
