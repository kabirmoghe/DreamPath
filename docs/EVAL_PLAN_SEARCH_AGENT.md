# Search Agent: Extended Evaluation Plan

Beyond the E2E test suite (which tests full graph runs and measures task decomposition, tool usage, efficiency, and result curation), this plan outlines deeper evaluation layers.

## 1. Query Generation Evaluation (Atomic-Level)

**What:** Evaluate the `query_generator` (instructor-based param extraction) in isolation, using the existing `golden_examples.py` dataset (23 examples across 11 archetypes).

**Existing infrastructure:** `evaluation/metrics.py` already has a hybrid scoring system (70% programmatic + 30% LLM judge). The golden examples and metrics are ready to use.

**Work needed:**
- Build a runner that calls `query_generator.generate_async(search_description)` for each golden example N times
- Score each output using the existing `evaluate_query_generation()` function
- Track per-archetype and per-feature pass rates
- Report which parameter extraction skills are weakest (department mapping, alpha tuning, value inference, etc.)
- Compare prompt versions (the `manual_optimization/` and `gepa_optimization/` dirs already have prompt variants)

**Key metrics:**
- Per-archetype programmatic score distribution
- Per-feature pass rate (e.g., "difficulty_extraction" passes 90% of the time, "alpha_tuning" only 60%)
- LLM judge agreement with programmatic scoring
- Prompt version comparison (which prompt yields best scores)

**Value:** Isolates query generation quality from orchestrator decision-making. If E2E results are poor, this tells you whether the problem is at the search parameter level or the orchestration level.

## 2. Orchestrator Decision Evaluation (Search Agent Internal)

**What:** Evaluate the search agent's internal orchestrator node decisions in isolation — given a specific state snapshot, does it make the right call?

**Approach:**
- Create "state snapshots" at various points during execution:
  - Iteration 0 (fresh goal): Does it create sensible tasks?
  - After first search returns: Does it correctly evaluate results and decide next action?
  - After finding good results: Does it mark tasks complete and not over-search?
  - After finding nothing: Does it try different approaches before marking failed?
- Each snapshot is a serialized `SearchAgentState` with known search_trace
- Feed snapshot into `orchestrator_node` and evaluate the returned `NextAction`

**Test scenarios:**
1. **Good first results** — snapshot where task has 3 highly relevant courses → expect `TaskUpdateAction` marking complete
2. **Poor first results** — snapshot where search returned irrelevant courses → expect `SearchAction` with refined approach
3. **No results** — empty search output → expect either different search approach or failure marking
4. **Mixed results** — some tasks done, some not → expect action only on incomplete tasks
5. **Duplicate detection** — snapshot where same search was already tried → expect different approach

**Key metrics:**
- Action type correctness (did it choose search/update/complete appropriately?)
- Task status transition correctness (complete when results are good, failed when exhausted)
- Search refinement quality (did the new search differ meaningfully from the previous one?)
- Top results curation precision (are curated codes actually the most relevant?)

**Implementation notes:**
- Requires creating a state serialization/deserialization mechanism
- Can snapshot real states from E2E runs and annotate them with expected actions
- LLM judge can evaluate whether the reasoning in the action makes sense

## 3. Search Diversity & Coverage Analysis

**What:** Evaluate whether the agent explores the search space effectively across iterations rather than repeating similar searches.

**Approach:**
- From E2E run traces, extract all `CourseSearchParams` used per task
- Compute pairwise similarity between search params within a task:
  - Query semantic similarity (embedding cosine)
  - Parameter overlap (same department? same difficulty? same alpha?)
- Flag "stale" iterations where search params are too similar to previous ones
- Track which parameter "knobs" the agent actually turns when refining

**Key metrics:**
- **Search diversity score** — average pairwise dissimilarity of searches within a task
- **Parameter variation rate** — how often does each parameter change between iterations?
- **Diminishing returns detection** — does the N-th search in a task still find new courses?
- **Strategy progression** — does the agent move from module_search to manual_search when appropriate?

**Value:** Directly addresses evaluation dimension (c) — efficiency. A high-quality agent should explore different angles rather than hammering the same query.

## 4. Result Relevance Evaluation (LLM Judge)

**What:** Use an LLM judge to evaluate whether the curated top_results actually match the task description.

**Approach:**
- For each completed task, take the task description and the curated top_results (with full course metadata)
- Ask an LLM judge: "Given this search task, rate how relevant each curated course is (0-1)"
- Compare curated courses vs. non-curated courses found in the same task — are the curated ones genuinely better?

**Evaluation criteria:**
1. **Relevance** — does the course match the task description?
2. **Completeness** — are there relevant courses in `all_courses` that were NOT curated but should have been?
3. **Precision** — are there curated courses that don't actually match?
4. **Constraint satisfaction** — if the task mentions difficulty/prereqs, do curated courses satisfy them?

**Implementation:**
```python
# Pseudo-code for LLM judge evaluation
for task in completed_tasks:
    for course in task.top_results:
        score = llm_judge(
            task_description=task.description,
            course_title=course.title,
            course_description=course.description,
            course_metadata={difficulty, value, prereqs, dept}
        )
    # Also check if any non-curated courses score higher than curated ones
```

**Key metrics:**
- Average relevance score of curated results
- Precision@K (what % of top-K curated courses are relevant?)
- Recall (what % of relevant courses in all_courses were curated?)
- "Miss rate" — how often is there a better course that wasn't curated?

## 5. Regression Testing Framework

**What:** Create a CI-friendly test suite that catches regressions when prompts or orchestrator logic change.

**Approach:**
- Select 5-8 "golden" E2E test cases that represent core behaviors
- Define hard pass/fail criteria (not just ranges):
  - "COSC74 lookup must find COSC74 in top_results"
  - "Nonexistent course must result in failed task"
  - "Multi-topic goal must create >= 2 tasks"
- Run with n=1 (fast) as a pytest suite
- Fail the test if any hard criteria are violated

**Implementation:**
```python
# pytest-compatible test functions
@pytest.mark.asyncio
async def test_exact_course_lookup():
    result = await run_single_test(graph, COSC74_CASE, 0)
    assert "COSC74" in result["top_results"]
    assert result["task_count"] == 1

@pytest.mark.asyncio
async def test_nonexistent_course_failure():
    result = await run_single_test(graph, COSC123_CASE, 0)
    assert result["failed_tasks"] >= 1
```

**Value:** Prevents prompt changes from silently breaking core agent behaviors. Fast enough to run on every PR.

## 6. Cost & Latency Profiling

**What:** Detailed breakdown of where time and tokens are spent.

**Approach:**
- Already have `iteration_tokens` and `cumulative_tokens` from E2E runs
- Add timing instrumentation to each component:
  - Orchestrator LLM call time vs. context building time
  - Search execution time (query generation + Weaviate query)
  - Summarize node time
- Profile across test categories to identify which goal types are most expensive

**Key metrics:**
- Tokens per iteration (is context growing too fast?)
- Cost per test case category (simple lookups should be cheap)
- Time breakdown: orchestrator % vs. search % vs. other %
- Context window utilization (are we approaching limits on complex goals?)

## Priority Order

1. **Query Generation Evaluation** — low effort (infra exists), high signal
2. **Result Relevance (LLM Judge)** — medium effort, directly validates quality
3. **Regression Testing** — medium effort, high ongoing value
4. **Search Diversity Analysis** — can be built from existing E2E trace data
5. **Orchestrator Decision Eval** — higher effort (needs state snapshots), deep insight
6. **Cost & Latency Profiling** — nice-to-have, can add incrementally
