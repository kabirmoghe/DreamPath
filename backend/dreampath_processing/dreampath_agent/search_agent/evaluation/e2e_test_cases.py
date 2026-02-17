"""
End-to-end test cases for the Search Agent.

Each test case defines a search goal (as handed off from the main orchestrator)
and expected behavior characteristics that can be evaluated after execution.
Goals are written as orchestrator handoff instructions, not direct student queries.

These test the full graph: orchestrator → tool_executor → summarize.

Test categories:
1. Simple lookups (single course, existence checks)
2. Single-topic searches (focused, bounded)
3. Multi-topic / compound searches (requires task decomposition)
4. Edge cases (nonexistent courses, overly broad goals, contradictory constraints)
5. Iterative refinement scenarios (goals that should trigger reflection + retry)
"""

from pydantic import BaseModel, Field


class E2ETestCase(BaseModel):
    """End-to-end search agent test case."""

    # Input
    goal: str = Field(description="Search goal as handed off by the orchestrator")

    # Expected behavior characteristics (not exact outputs)
    category: str = Field(description="Test category")
    expected_task_count_range: tuple[int, int] = Field(
        description="(min, max) expected number of tasks created"
    )
    expected_iteration_range: tuple[int, int] = Field(
        description="(min, max) reasonable iteration count"
    )
    should_find_courses: bool = Field(
        default=True,
        description="Whether the agent should find at least some courses"
    )
    expected_min_unique_courses: int = Field(
        default=1,
        description="Minimum unique courses expected across all tasks"
    )
    expected_failure_tasks: int = Field(
        default=0,
        description="Number of tasks expected to fail (e.g., nonexistent courses)"
    )
    key_course_codes: list[str] = Field(
        default_factory=list,
        description="Course codes that SHOULD appear in results (soft expectation)"
    )
    description: str = Field(
        description="What this test evaluates and why"
    )


# ============================================================================
# Test Cases
# ============================================================================

E2E_TEST_CASES: list[E2ETestCase] = [

    # ---- Category 1: Simple Lookups ----

    E2ETestCase(
        goal="Find info on COSC74",
        category="simple_lookup",
        expected_task_count_range=(1, 2),
        expected_iteration_range=(2, 6),
        should_find_courses=True,
        expected_min_unique_courses=1,
        key_course_codes=["COSC74"],
        description="Single course lookup by code. Tests exact retrieval. "
                    "Should create 1 task, do 1 search, find the exact course."
    ),

    E2ETestCase(
        goal="Find info on COSC123",
        category="simple_lookup",
        expected_task_count_range=(1, 2),
        expected_iteration_range=(2, 6),
        should_find_courses=False,
        expected_min_unique_courses=0,
        expected_failure_tasks=1,
        description="Nonexistent course lookup. Tests honest failure behavior. "
                    "Should recognize course doesn't exist and mark task as failed."
    ),

    E2ETestCase(
        goal="Tell me about QSS20",
        category="simple_lookup",
        expected_task_count_range=(1, 2),
        expected_iteration_range=(2, 6),
        should_find_courses=True,
        expected_min_unique_courses=1,
        key_course_codes=["QSS20"],
        description="Single course lookup for a QSS course. Tests department "
                    "handling and exact code retrieval."
    ),

    # ---- Category 2: Single-Topic Searches ----

    E2ETestCase(
        goal="Find a class on computer vision",
        category="single_topic",
        expected_task_count_range=(1, 3),
        expected_iteration_range=(2, 8),
        should_find_courses=True,
        expected_min_unique_courses=1,
        description="Focused technical topic. Should find CS courses related to "
                    "computer vision, image processing, or visual computing."
    ),

    E2ETestCase(
        goal="Determine if there is a class on the history of AI",
        category="single_topic",
        expected_task_count_range=(1, 3),
        expected_iteration_range=(2, 8),
        should_find_courses=True,
        expected_min_unique_courses=1,
        description="Existence-oriented search for a niche topic. Tests whether "
                    "agent can find courses touching on AI history or philosophy of AI."
    ),

    E2ETestCase(
        goal="Find easy introductory economics courses with no prerequisites",
        category="single_topic",
        expected_task_count_range=(1, 2),
        expected_iteration_range=(2, 7),
        should_find_courses=True,
        expected_min_unique_courses=2,
        description="Single-topic with multiple constraints (difficulty + prereqs). "
                    "Tests constraint stacking on a single search task."
    ),

    E2ETestCase(
        goal="Find highly-rated philosophy courses",
        category="single_topic",
        expected_task_count_range=(1, 2),
        expected_iteration_range=(2, 7),
        should_find_courses=True,
        expected_min_unique_courses=2,
        description="Value-filtered exploratory search within a single department. "
                    "Tests value classification usage."
    ),

    # ---- Category 3: Multi-Topic / Compound Searches ----

    E2ETestCase(
        goal="Find easy ML courses and challenging philosophy courses",
        category="multi_topic",
        expected_task_count_range=(2, 4),
        expected_iteration_range=(3, 10),
        should_find_courses=True,
        expected_min_unique_courses=3,
        description="Two distinct topics with different difficulty constraints. "
                    "Tests task decomposition into separate tasks for ML (easy) "
                    "and philosophy (challenging)."
    ),

    E2ETestCase(
        goal="Find interdisciplinary courses that may offer a new perspective on LLMs and AI",
        category="multi_topic",
        expected_task_count_range=(2, 5),
        expected_iteration_range=(3, 12),
        should_find_courses=True,
        expected_min_unique_courses=3,
        description="Broad, interdisciplinary search goal. Tests whether agent "
                    "decomposes across multiple departments (CS, philosophy, "
                    "linguistics, cognitive science, etc.)."
    ),

    E2ETestCase(
        goal="Find classes covering core computational biology topics without many prerequisites",
        category="multi_topic",
        expected_task_count_range=(2, 5),
        expected_iteration_range=(3, 10),
        should_find_courses=True,
        expected_min_unique_courses=2,
        description="Cross-disciplinary search with prerequisite constraint. "
                    "Tests decomposition across biology and CS domains."
    ),

    E2ETestCase(
        goal="Find courses on statistics, machine learning, and data visualization "
             "to support preparation for a data science career path",
        category="multi_topic",
        expected_task_count_range=(3, 5),
        expected_iteration_range=(3, 12),
        should_find_courses=True,
        expected_min_unique_courses=5,
        description="Three explicit sub-topics enumerated in goal. Tests whether "
                    "agent creates separate tasks for each sub-area."
    ),

    E2ETestCase(
        goal="Find advanced math courses relevant to quantitative finance, "
             "and beginner-friendly writing courses",
        category="multi_topic",
        expected_task_count_range=(2, 4),
        expected_iteration_range=(3, 10),
        should_find_courses=True,
        expected_min_unique_courses=3,
        description="Completely unrelated topics with different difficulty levels. "
                    "Tests decomposition of disparate domains."
    ),

    # ---- Category 4: Edge Cases ----

    E2ETestCase(
        goal="Find accessible quantum computing courses suitable for a student "
             "without a physics or CS background",
        category="edge_case",
        expected_task_count_range=(1, 3),
        expected_iteration_range=(2, 10),
        should_find_courses=True,
        expected_min_unique_courses=0,
        description="Niche cross-disciplinary request. May find very few or no "
                    "courses. Tests agent's ability to handle sparse results "
                    "gracefully and potentially mark tasks as failed."
    ),

    E2ETestCase(
        goal="Find courses on underwater basket weaving",
        category="edge_case",
        expected_task_count_range=(1, 2),
        expected_iteration_range=(2, 8),
        should_find_courses=False,
        expected_min_unique_courses=0,
        expected_failure_tasks=1,
        description="Nonsensical topic. Tests honest failure — agent should "
                    "recognize no relevant courses exist and fail gracefully."
    ),

    # ---- Category 5: Iterative Refinement ----

    E2ETestCase(
        goal="Find courses covering both computational methods and experimental "
             "psychology approaches relevant to cognitive neuroscience graduate "
             "preparation",
        category="iterative_refinement",
        expected_task_count_range=(2, 5),
        expected_iteration_range=(3, 12),
        should_find_courses=True,
        expected_min_unique_courses=3,
        description="Complex, multi-faceted academic preparation goal. Tests "
                    "whether agent creates distinct tasks for computational "
                    "vs experimental approaches and iterates to find good matches."
    ),

    E2ETestCase(
        goal="Find studio art courses involving digital tools, and CS courses "
             "about creative coding or generative art",
        category="iterative_refinement",
        expected_task_count_range=(2, 4),
        expected_iteration_range=(3, 10),
        should_find_courses=True,
        expected_min_unique_courses=2,
        description="Art+tech intersection from two department angles. Tests "
                    "whether agent searches both Studio Art and CS departments "
                    "with appropriate queries."
    ),
]


def get_test_cases_by_category(category: str) -> list[E2ETestCase]:
    return [tc for tc in E2E_TEST_CASES if tc.category == category]


def print_test_suite_summary():
    print(f"Total test cases: {len(E2E_TEST_CASES)}\n")
    categories = {}
    for tc in E2E_TEST_CASES:
        categories.setdefault(tc.category, []).append(tc)
    for cat, cases in categories.items():
        print(f"  {cat}: {len(cases)} cases")
        for c in cases:
            print(f"    - {c.goal[:70]}...")


if __name__ == "__main__":
    print_test_suite_summary()
