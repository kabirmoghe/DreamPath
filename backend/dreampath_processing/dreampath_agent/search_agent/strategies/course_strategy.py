"""Course search strategy implementation.

Bundles all course-specific logic: search execution (with query generator),
prompt sections, rendering, and type mappings.
"""

import asyncio
import os

from dreampath_processing.dreampath_agent.search_agent.search_types import (
    OrchestratorResult,
)
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
from pydantic import BaseModel

# ============================================
# Query Generator Singleton
# ============================================

_query_generator = None


def _get_query_generator():
    """Lazy initialization of query generator with async client."""
    global _query_generator

    if _query_generator is None:
        from dreampath_processing.dreampath_agent.search_agent.tools.query_generator import (
            CourseQueryGenerator,
        )
        from openai import AsyncOpenAI, OpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not set - required for course search")

        sync_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        _query_generator = CourseQueryGenerator(sync_client, async_client=async_client)

        try:
            from dreampath_processing.dreampath_agent.search_agent.evaluation.utils import (
                load_best_prompt,
            )
            prompt = load_best_prompt()
            _query_generator.configure(system_prompt=prompt, model="gpt-4o-mini")
        except Exception as e:
            print(f"Warning: Could not load best prompt: {e}")
            print("Using fallback prompt_2")
            from dreampath_processing.dreampath_agent.search_agent.evaluation.manual_optimization.prompts.prompt_2 import (
                QUERY_GENERATION_PROMPT,
            )
            _query_generator.configure(system_prompt=QUERY_GENERATION_PROMPT, model="gpt-4o-mini")

    return _query_generator


class CourseSearchStrategy:
    """Strategy for searching the course catalog."""

    domain_name = "course"
    params_type = CourseSearchParams
    result_type = CourseSearchResult
    output_type = CourseSearchOutput

    # ========================================
    # Search Execution
    # ========================================

    async def execute_search(self, search_description: str) -> tuple[SearchParams, SearchOutput]:
        """Execute a course search: query generator → Weaviate.

        Args:
            search_description: Natural language search description from orchestrator.

        Returns:
            (generated_params, search_results) tuple.
        """
        # 1. Query generator translates description → CourseSearchParams (async)
        query_generator = _get_query_generator()
        params = await query_generator.generate_async(search_description)

        # 2. Weaviate search (sync client via thread pool)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._search_sync, params)
        return (params, result)

    @staticmethod
    def _search_sync(params: CourseSearchParams) -> CourseSearchOutput:
        """Synchronous Weaviate search (called via run_in_executor)."""
        from dreampath_processing.dreampath_agent.search_agent.tools.course_search_client import (
            CourseSearchClient,
        )
        client = CourseSearchClient()
        try:
            return client.structured_hybrid_search(params)
        finally:
            client.close()

    # ========================================
    # Orchestrator Prompt Sections
    # ========================================

    def get_orchestrator_prompt_sections(self) -> dict[str, str]:
        """Return course-specific prompt sections."""
        return {
            "search_guidelines": COURSE_SEARCH_GUIDELINES,
            "task_guidelines": COURSE_TASK_GUIDELINES,
            "example": COURSE_EXAMPLE,
        }

    def get_orchestrator_result_schema(self) -> type[BaseModel]:
        """Return OrchestratorResult for OpenAI structured output."""
        return OrchestratorResult

    # ========================================
    # Rendering: Tool Results (context/building.py)
    # ========================================

    def render_result(self, result: dict, compact: bool = False) -> list[str]:
        """Render a course result. Compact for old iterations, full for recent."""
        if compact:
            return [f" - {result['code']}: {result['title']}"]

        lines = []
        lines.append(f"{result['code']} - {result['title']}")
        lines.append(f"   Dept: {result['department']}, Diff: {result['difficulty']}, Value: {result['value']}, Prereqs: {result['num_prereqs']}")

        desc = result.get("description", "")
        if desc:
            if len(desc) > 500:
                desc = desc[:500] + "..."
            lines.append(f"   Description: {desc}")

        if result.get("difficulty_blurb"):
            lines.append(f"   Difficulty Blurb: {result['difficulty_blurb']}")
        if result.get("learning_value_blurb"):
            lines.append(f"   Learning Value Blurb: {result['learning_value_blurb']}")
        if result.get("target_audience_blurb"):
            lines.append(f"   Target Audience Blurb: {result['target_audience_blurb']}")

        return lines

    # ========================================
    # Rendering: Task State (context/building.py)
    # ========================================

    def render_task_top_result(self, result_id: str, result_index: dict) -> str:
        """Render a top_result entry in the task state block."""
        result = result_index.get(result_id)
        if result:
            desc = result.description[:200] + "..." if result.description and len(result.description) > 200 else (result.description or "No description")
            title = result.title if hasattr(result, 'title') else getattr(result, 'course_title', '')
            return f"- {result_id}: {title} | {desc}"
        return f"- {result_id}"

    # ========================================
    # Rendering: Final Summary (summarize.py)
    # ========================================

    def render_result_for_summary(self, result: SearchResult, verbosity: int) -> list[str]:
        """Render a single result for the final markdown summary."""
        if not isinstance(result, CourseSearchResult):
            return [f"**{result.id}: {result.title}**", ""]

        course = result
        lines = []

        if verbosity == 0:
            # Minimal
            lines.append(f"**{course.course_code}: {course.course_title}**")
            diff = course.global_difficulty_classification or "Unknown"
            val = course.global_value_classification or "Unknown"
            lines.append(f"- Difficulty: {diff} | Learning Value: {val}")
            if course.target_audience_blurb:
                blurb = course.target_audience_blurb
                if len(blurb) > 200:
                    blurb = blurb[:197] + "..."
                lines.append(f"- Target Audience: '{blurb}'")
            lines.append("")

        elif verbosity == 1:
            # Medium
            lines.append(f"**{course.course_code}: {course.course_title}**")
            if course.description:
                desc = course.description[:300]
                if len(course.description) > 300:
                    desc += "..."
                lines.append(f"- {desc}")
            if course.global_difficulty_classification:
                lines.append(f"- Difficulty: {course.global_difficulty_classification}")
            if course.global_value_classification:
                val_line = f"- Learning Value: {course.global_value_classification}"
                if course.learning_value_blurb:
                    val_line += f" | '{course.learning_value_blurb}'"
                lines.append(val_line)
            if course.target_audience_blurb:
                lines.append(f"- Target Audience: '{course.target_audience_blurb}'")
            lines.append("")

        else:
            # Full (verbosity >= 2)
            lines.append(f"<course>**{course.course_code}: {course.course_title}**")
            lines.append(f"- Department: {course.department}")
            if course.description:
                lines.append(f"- Description: {course.description}")
            if course.num_prereqs > 0:
                lines.append(f"- Prerequisites: {course.prerequisites}")
            if course.course_url:
                lines.append(f"- URL: {course.course_url}")
            if course.global_difficulty_classification:
                diff_str = f"- Difficulty: {course.global_difficulty_classification}"
                if course.global_difficulty_percentile:
                    diff_str += f" (Percentile: {round(course.global_difficulty_percentile, 2)})"
                lines.append(diff_str)
            if course.global_value_classification:
                val_str = f"- Learning Value: {course.global_value_classification}"
                if course.global_value_percentile:
                    val_str += f" (Percentile: {round(course.global_value_percentile, 2)})"
                lines.append(val_str)
            if course.difficulty_blurb or course.learning_value_blurb or course.target_audience_blurb:
                lines.append("- Students sentiment:")
                if course.difficulty_blurb:
                    lines.append(f"\t→ About difficulty: {course.difficulty_blurb}")
                if course.learning_value_blurb:
                    lines.append(f"\t→ About learning value: {course.learning_value_blurb}")
                if course.target_audience_blurb:
                    lines.append(f"\t→ Target audience: {course.target_audience_blurb}")
            lines.append("</course>")

        return lines

    # ========================================
    # ID and Entry Building
    # ========================================

    def get_result_id(self, result: SearchResult) -> str:
        """Extract course_code as the canonical ID."""
        if isinstance(result, CourseSearchResult):
            return result.course_code
        return result.id

    def build_tool_result_entry(self, result: SearchResult) -> dict:
        """Build dict for a single course result in tool result data."""
        if not isinstance(result, CourseSearchResult):
            return {
                "code": result.id,
                "title": result.title,
                "description": result.description or "",
            }

        return {
            "code": result.course_code,
            "title": result.course_title,
            "department": result.department,
            "description": result.description or "",
            "difficulty": result.global_difficulty_classification,
            "value": result.global_value_classification,
            "num_prereqs": result.num_prereqs,
            "difficulty_blurb": result.difficulty_blurb or "",
            "learning_value_blurb": result.learning_value_blurb or "",
            "target_audience_blurb": result.target_audience_blurb or "",
        }


# ============================================
# Course-specific prompt sections
# ============================================

COURSE_SEARCH_GUIDELINES = """## SearchAction: Search Guidelines
For each search, you provide a natural language `search_description` string.
A trained query generator will automatically determine the best search parameters (query terms, department filters, difficulty/value filters, etc.).

**Search descriptions should be**:
- Atomic: specific, focused, single-query scope
- Use terms likely found in a course catalog (e.g., "computer science" instead of "software engineering")
- If relevant, mention at most ONE department, ONE difficulty level, ONE value level

**Search capabilities** (the query generator can handle these automatically):
- Department filtering (e.g., "in Computer Science", "in Economics")
- Difficulty preferences (e.g., "easy", "challenging", "introductory")
- Learning value preferences (e.g., "high learning value", "highly rated")
- Prerequisite constraints (e.g., "with few prerequisites", "no prereqs")
- Course level (e.g., "upper-level", "introductory")

**Examples of good search descriptions**:
- "Easy machine learning courses with high learning value"
- "Upper-level neuroscience courses in the Biology department"
- "Introductory data analysis courses with minimal prerequisites"
- "Computer science courses on operating systems and low-level programming"

**Semantic queries CAN include multiple related concepts**:
  ✓ "machine learning deep learning neural networks" → GOOD: one search
  ✓ "data structures algorithms and complexity" → GOOD: one search
  ✗ "machine learning in Computer Science and Mathematics" → BAD: multiple departments, use separate searches

**Searches are atomic in nature to improve efficiency, but you are encouraged to use multiple searches when relevant to tasks.**

### Search Strategy: Explore Before Settling
- **First search round**: Use broad, department-agnostic searches to discover which departments have relevant courses.
- **Follow-up rounds**: If initial results are mediocre or narrowly concentrated in one department, explicitly explore adjacent departments rather than rewording the same query.
  - Many topics span multiple departments. E.g., "data analysis" lives in Computer Science, Mathematics, QSS, Economics, and Engineering.
  - Industry-specific terms (e.g., "consulting", "software engineering", "product management") may not appear in academic course catalogs. When these terms yield poor results, pivot to the underlying academic disciplines and explore specific departments.
    Example: "consulting skills" → try searches in Economics, Speech, Psychology departments
    Example: "software engineering" → try Computer Science, or Engineering Sciences departments depending on goal's implied domain, desired skills, etc.
- **Do not** mark a task complete or partially_complete after only one search round unless the results are clearly strong and goal scope is inherently hyper-specific. If initial results are decent but narrow, run at least one more round targeting different departments before settling."""

COURSE_TASK_GUIDELINES = """## TaskUpdateAction: Task Update Guidelines
When returning TaskUpdateAction:

### 1. Initial Task Creation
Guidelines for task decomposition:
- CREATE SEPARATE TASKS when the goal involves distinct domains, topics, or independent requirements
  Example: "Intro bio AND upper-level neuroscience" → 2 tasks (different course types, departments)

- KEEP AS ONE TASK when multiple constraints apply to the SAME search
  Example: "Easy AND highly-rated philosophy" → 1 task (filters on same search)
  Example: "Machine learning with few prereqs" → 1 task (query + filter)

- KEEP AS ONE TASK for information regarding a single course, since **a single lookup search provides all the information needed (e.g., prereqs., description, sentiment)**
  Example: "Find information about course <course_code>" → 1 task (look up course)

- Broad example:
  "Identify relevant courses for interdisciplinary computational biology courses, covering a mix of easy and difficult courses that cover bioinformatics and data analysis fundamentals, as well as a relevant AI for drug discovery course"
  → Likely multiple tasks for corresponding computational biology courses, but 1 task for the AI for drug discovery course

Task Scope:
- If the goal refers to a broad field or topic, (sparingly) use multiple tasks to cover different topics or subfields that are necessary / relevant to the goal.

#### Ensuring Focus on Right Domains / Field of Study
- When decomposing complex goals, ensure tasks explicitly specify the relevant domains / fields of study so keyword similarity does not lead you to surface courses from unrelated disciplines.
  Example: "design" --> within task, specify "UI/UX", or "architecture", or "product", or "graphic", etc.
  Example: "modeling" --> within task, specify "statistical / ML", or "financial", or "3D / CAD", etc.
  Example: "prototyping" --> within task, specify "hardware", or "software", etc.

### 2. Mid-Turn Task Analysis
For each in-progress or non-started task, analyze the corresponding results (for that task ID) by following the steps below.

#### Top Results Curation
The top_results field is YOUR selection of the best courses that satisfy the description for a given task
- Review search_executions to see all courses found
- Consider diversity, difficulty, prerequisites, relevance w.r.t the task and goal
- Avoid highly redundant courses unless there is a clear reason to include them. If courses have highly overlapping titles, descriptions, and content, prioritize the one most relevant to the task (e.g., in the most related department)

- Pay extremely careful attention to any specified fields of study / domains in the task.
  - If courses naively have similar keywords, ensure they are actually relevant to any specified domains and weed them out if not.
    Example: if the task specifies courses on "architecture" for a software engineering student, obviously omit courses from unrelated architectural design.
    Example: if the task specifies courses on "prototyping" for a software engineering student, top courses should not include courses from unrelated hardware prototyping.

- **Only include courses whose content directly addresses the task description.** Do not pad top_results with loosely related courses just to have results.
  - Ex: if looking for software courses, do not include hardware engineering courses that happen to have some keyword alignment in common.
- It is better to have 1-2 genuinely relevant courses (or zero, with a "failed" status) than 5 tangentially related ones.

**Choose up to 10 most relevant course codes. Frontend will display these as primary results.**

#### Status Determination
- Set status based on result quality (not just presence of results)
- Mark / keep tasks "in_progress" if there is still potential for improved completion through future search iterations.

**The following are terminal statuses that signify that a given task's potential for completion has been maximized and that it should not be revisited:**
- Mark "complete" only if top_results contain courses that address the task description well, and update orchestrator_notes to explain why you marked it complete.
  - Apply this test: if a student asked specifically for [task description], would these courses be a satisfying, on-topic answer? **Be strict here!** if you'd need to stretch or rationalize relevance, the task is NOT complete.
- Mark "partially_complete" if top_results do a decent job of addressing the task description, but are not comprehensive or perfect. Update orchestrator_notes to explain why you marked it partially complete.
  - This is important to surface moderate matches that are still likely relevant to the task and true nature of the overall goal.
  - For example, perhaps there are slightly less advanced courses that offer the similar but less advanced skills / knowledge.
- Mark "failed" after 4+ search iterations (excluding task updates) with poor or irrelevant results, and update orchestrator_notes explaining why you marked it failed.
  - **It is perfectly acceptable — and encouraged — to mark a task as "failed" when the course catalog simply doesn't have courses that directly match.**
  - Not every topic has dedicated courses. A failed task with an honest note like "No courses directly cover prompt engineering for LLMs" is far more valuable than a "complete" task with tangentially related results.
  - It is highly encouraged to highlight limitations with course relevance, e.g., "...course covers multi-robot systems and might be similar but is not directly relevant to multi-agent LLM-based systems."

#### Orchestrator Note Bookkeeping
- Provide actionable orchestrator_notes for "in_progress" tasks, or descriptive rationale for terminal tasks
- Carefully note which courses are the best matches, weaker matches, etc. for each task.
- Make note of potential departmental areas worth exploring, other filter values worth relaxing, and other exploration to help steer yourself in future search iterations.
  - Example: "Try Biology/Chemistry depts, current results are CS-focused"
  - Example: "Prototyping keyword searches yielded specific courses for hardware, let's focus on CS courses"
  - Example: "Maybe setting value_classification to high is too restrictive, there may not be reviews. We should try removing the constraint."
- **Track which departments have been explored.** If results are weak, note untried departments explicitly so the next SearchAction targets them rather than rewording the same query.
  - Example: "Searched broadly — results only from CS. Next: try Engineering Sciences, QSS departments."

## CompleteAction: Complete Guidelines
Before returning CompleteAction, carefully understand your orchestrator_notes to determine if certain tasks are worth exploring further.
Then, if you have studied the tasks and determined they are all terminal (completed, partially completed, or failed), you must return CompleteAction.
This signals the end of search execution for the provided goal."""

COURSE_EXAMPLE = """# Core Example

This example illustrates correct orchestrator behavior — especially honest failure. Completing a task with loosely related courses is far worse than marking it failed with a clear explanation.

## Mixed Success and Failure

Goal: "Find courses on DevOps/CI-CD practices, blockchain development, and systems programming"

Iteration 0 → TaskUpdateAction
  Task 1: "Find courses on DevOps practices, CI/CD pipelines, and infrastructure automation"
  Task 2: "Find courses on blockchain development and distributed ledger technology"
  Task 3: "Find courses on systems programming: C, OS internals, low-level computing"

Iteration 1 → SearchAction
  Task 1: search("DevOps CI/CD pipeline infrastructure automation courses")
  Task 2: search("Blockchain development distributed ledger technology courses")
  Task 3: search("Systems programming C operating systems low-level")
  → Task 1: finds COSC50 (Software Design) and ENGS65 (Engineering Software Design) — software eng, but not DevOps
  → Task 2: finds cryptography/distributed systems courses but nothing on blockchain
  → Task 3: finds COSC58 (OS), COSC50 (C programming), COSC51 (Architecture) — direct matches

Iteration 2 → TaskUpdateAction
  Task 1: in_progress | top_results: []
  Notes: "COSC50 covers software engineering and COSC52 covers web deployment, but neither addresses DevOps tooling, CI/CD pipelines, or infrastructure-as-code. Try deployment/automation angle."
  Task 2: in_progress | top_results: []
  Notes: "No blockchain courses found. COSC60 covers networking but not distributed ledgers. Try broader search."
  Task 3: complete | top_results: [COSC58, COSC50, COSC51]
  Notes: "Strong systems coverage: COSC58 (OS internals), COSC50 (C, UNIX tools), COSC51 (architecture)."

Iteration 3 → SearchAction
  Task 1: search("Software deployment automation continuous integration")
  Task 2: search("Cryptography distributed systems peer-to-peer networks")
  → Task 1: general CS courses again — still nothing on DevOps/CI-CD
  → Task 2: finds COSC60 (Networks), MATH75 (Crypto) — adjacent but not blockchain

...more iterations...

Iteration 10 → TaskUpdateAction
  Task 1: failed | top_results: []
  Notes: "After multiple diverse search rounds, no courses cover DevOps, CI/CD, or infrastructure automation."
  Task 2: failed | top_results: []
  Notes: "No courses cover blockchain or distributed ledger technology."

Iteration 11 → CompleteAction
  "1 of 3 tasks completed. Strong systems programming coverage found. DevOps/CI-CD and blockchain are industry-specific topics not represented in the academic catalog."
"""
