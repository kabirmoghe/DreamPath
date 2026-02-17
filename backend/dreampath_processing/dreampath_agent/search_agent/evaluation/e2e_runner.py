"""
End-to-end evaluation runner for the Search Agent.

Runs each test case N times, collects structured metrics, and produces
an analysis report. Evaluates four dimensions:

(a) Task Decomposition - are tasks created sensibly for the goal?
(b) Tool Usage Quality - is the agent reflecting on results and iterating well?
(c) Efficiency - is it avoiding duplicate/redundant searches?
(d) Result Curation - are top_results well-chosen from available courses?
"""

import asyncio
import json
import time
import warnings
from collections import Counter
from pathlib import Path

from dreampath_processing.dreampath_agent.search_agent.evaluation.e2e_test_cases import (
    E2E_TEST_CASES,
    E2ETestCase,
)
from dreampath_processing.dreampath_agent.search_agent.graph import build_search_agent
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchTask,
)

warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

# ============================================================================
# Single Run Metrics
# ============================================================================

def extract_run_metrics(final_state: dict, test_case: E2ETestCase, elapsed: float) -> dict:
    """Extract structured metrics from a single search agent run."""
    tasks: list[SearchTask] = final_state.get("tasks", [])
    iteration = final_state.get("iteration", 0)

    # --- Basic counts ---
    task_count = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.status == "complete")
    partially_completed_tasks = sum(1 for t in tasks if t.status == "partially_complete")
    failed_tasks = sum(1 for t in tasks if t.status == "failed")

    # --- Course metrics ---
    all_top_results = []
    all_unique_courses = set()
    total_search_executions = 0
    all_search_params = []

    for task in tasks:
        all_top_results.extend(task.top_results)
        total_search_executions += len(task.search_executions)
        for ex in task.search_executions:
            for course in ex.output.results:
                all_unique_courses.add(course.course_code)
            all_search_params.append(ex.params.model_dump())

    unique_top_results = set(all_top_results)

    # --- Efficiency: detect duplicate searches ---
    search_signatures = []
    for params in all_search_params:
        sig = (
            params.get("query", ""),
            params.get("department"),
            params.get("course_code"),
            params.get("difficulty_classification"),
            params.get("value_classification"),
        )
        search_signatures.append(sig)
    duplicate_searches = len(search_signatures) - len(set(search_signatures))

    # --- Efficiency: searches per task ---
    searches_per_task = [len(t.search_executions) for t in tasks]

    # --- Tool usage: module_search vs manual_search ---
    search_trace = final_state.get("search_trace", [])
    module_search_count = 0
    manual_search_count = 0
    for entry in search_trace:
        if entry.get("type") == "orchestrator_decision":
            action = entry.get("action", {})
            if action.get("action_type") == "search":
                for s in action.get("searches", []):
                    if s.get("action_type") == "module_search":
                        module_search_count += 1
                    elif s.get("action_type") == "manual_search":
                        manual_search_count += 1

    # --- Expectation checks ---
    task_count_in_range = (
        test_case.expected_task_count_range[0]
        <= task_count
        <= test_case.expected_task_count_range[1]
    )
    iteration_in_range = (
        test_case.expected_iteration_range[0]
        <= iteration
        <= test_case.expected_iteration_range[1]
    )
    found_expected_courses = all(
        code in all_unique_courses for code in test_case.key_course_codes
    ) if test_case.key_course_codes else True

    courses_found = len(all_unique_courses) > 0
    if test_case.should_find_courses:
        find_status_correct = courses_found
    else:
        find_status_correct = not courses_found or failed_tasks >= test_case.expected_failure_tasks

    failure_count_correct = failed_tasks >= test_case.expected_failure_tasks

    # --- Token usage ---
    cumulative_tokens = final_state.get("cumulative_tokens", 0)
    iteration_tokens = final_state.get("iteration_tokens", [])

    return {
        # Identification
        "goal": test_case.goal,
        "category": test_case.category,

        # Timing
        "elapsed_seconds": round(elapsed, 2),

        # Task decomposition
        "task_count": task_count,
        "completed_tasks": completed_tasks,
        "partially_completed_tasks": partially_completed_tasks,
        "failed_tasks": failed_tasks,
        "task_descriptions": [t.description for t in tasks],
        "task_statuses": [t.status for t in tasks],

        # Iterations
        "iteration_count": iteration,

        # Courses
        "total_unique_courses": len(all_unique_courses),
        "unique_course_codes": sorted(all_unique_courses),
        "top_results_count": len(unique_top_results),
        "top_results": sorted(unique_top_results),

        # Tool usage
        "total_search_executions": total_search_executions,
        "module_search_count": module_search_count,
        "manual_search_count": manual_search_count,
        "searches_per_task": searches_per_task,

        # Efficiency
        "duplicate_searches": duplicate_searches,

        # Token usage
        "cumulative_tokens": cumulative_tokens,
        "iteration_tokens": iteration_tokens,

        # Expectation checks
        "task_count_in_range": task_count_in_range,
        "iteration_in_range": iteration_in_range,
        "found_expected_courses": found_expected_courses,
        "find_status_correct": find_status_correct,
        "failure_count_correct": failure_count_correct,
    }


# ============================================================================
# Aggregate Analysis
# ============================================================================

def aggregate_runs(runs: list[dict], test_case: E2ETestCase) -> dict:
    """Aggregate metrics across N runs of the same test case."""
    n = len(runs)
    if n == 0:
        return {}

    def avg(key):
        return round(sum(r[key] for r in runs) / n, 2)

    def pct_true(key):
        return round(sum(1 for r in runs if r[key]) / n * 100, 1)

    # Consistency: how often does the same set of top results appear?
    top_result_sets = [frozenset(r["top_results"]) for r in runs]
    most_common_set, most_common_count = Counter(top_result_sets).most_common(1)[0]
    top_result_consistency = round(most_common_count / n * 100, 1)

    # Course overlap across runs (Jaccard of all unique courses found)
    all_course_sets = [set(r["unique_course_codes"]) for r in runs]
    intersection = set.intersection(*all_course_sets) if all_course_sets else set()
    union = set.union(*all_course_sets) if all_course_sets else set()
    course_jaccard = round(len(intersection) / len(union) * 100, 1) if union else 100.0

    return {
        "goal": test_case.goal,
        "category": test_case.category,
        "num_runs": n,

        # Averages
        "avg_elapsed_seconds": avg("elapsed_seconds"),
        "avg_task_count": avg("task_count"),
        "avg_iterations": avg("iteration_count"),
        "avg_unique_courses": avg("total_unique_courses"),
        "avg_top_results": avg("top_results_count"),
        "avg_search_executions": avg("total_search_executions"),
        "avg_duplicate_searches": avg("duplicate_searches"),
        "avg_cumulative_tokens": avg("cumulative_tokens"),

        # Ranges
        "iteration_range": (
            min(r["iteration_count"] for r in runs),
            max(r["iteration_count"] for r in runs)
        ),
        "task_count_range": (
            min(r["task_count"] for r in runs),
            max(r["task_count"] for r in runs)
        ),

        # Pass rates
        "pct_task_count_in_range": pct_true("task_count_in_range"),
        "pct_iteration_in_range": pct_true("iteration_in_range"),
        "pct_found_expected_courses": pct_true("found_expected_courses"),
        "pct_find_status_correct": pct_true("find_status_correct"),
        "pct_failure_count_correct": pct_true("failure_count_correct"),

        # Consistency
        "top_result_consistency_pct": top_result_consistency,
        "course_jaccard_pct": course_jaccard,
        "most_common_top_results": sorted(most_common_set),
    }


# ============================================================================
# Runner
# ============================================================================

async def run_single_test(graph, test_case: E2ETestCase, run_idx: int) -> dict:
    """Run a single test case once and return metrics."""
    initial_state = SearchAgentState(goal=test_case.goal)
    start = time.time()
    try:
        final_state = await graph.ainvoke(initial_state)
        elapsed = time.time() - start
        metrics = extract_run_metrics(final_state, test_case, elapsed)
        metrics["run_index"] = run_idx
        metrics["error"] = None
        return metrics
    except Exception as e:
        elapsed = time.time() - start
        return {
            "goal": test_case.goal,
            "category": test_case.category,
            "run_index": run_idx,
            "elapsed_seconds": round(elapsed, 2),
            "error": f"{type(e).__name__}: {e}",
        }


async def run_evaluation(
    n_runs: int = 5,
    test_cases: list[E2ETestCase] | None = None,
    output_dir: str = "evaluation/results",
) -> dict:
    """
    Run the full evaluation suite.

    Args:
        n_runs: Number of times to run each test case
        test_cases: Subset of test cases (defaults to all)
        output_dir: Directory for results files

    Returns:
        Complete results dict with per-run and aggregate data
    """
    cases = test_cases or E2E_TEST_CASES
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    graph = build_search_agent()

    all_results = {}
    total_tests = len(cases) * n_runs
    completed = 0

    print(f"\n{'='*80}")
    print(f"SEARCH AGENT E2E EVALUATION")
    print(f"{'='*80}")
    print(f"Test cases: {len(cases)}")
    print(f"Runs per case: {n_runs}")
    print(f"Total runs: {total_tests}")
    print(f"{'='*80}\n")

    for case_idx, test_case in enumerate(cases):
        case_key = f"case_{case_idx:02d}"
        print(f"\n[{case_idx+1}/{len(cases)}] {test_case.category}: {test_case.goal[:60]}...")

        runs = []
        for run_idx in range(n_runs):
            completed += 1
            print(f"  Run {run_idx+1}/{n_runs} ({completed}/{total_tests} total)...", end=" ", flush=True)
            metrics = await run_single_test(graph, test_case, run_idx)
            if metrics.get("error"):
                print(f"ERROR: {metrics['error']}")
            else:
                print(
                    f"done in {metrics['elapsed_seconds']}s | "
                    f"tasks={metrics['task_count']} iters={metrics['iteration_count']} "
                    f"courses={metrics['total_unique_courses']}"
                )
            runs.append(metrics)

        # Filter successful runs for aggregation
        successful_runs = [r for r in runs if r.get("error") is None]
        agg = aggregate_runs(successful_runs, test_case) if successful_runs else {}

        all_results[case_key] = {
            "test_case": test_case.model_dump(),
            "runs": runs,
            "aggregate": agg,
        }

    # Save raw results
    raw_path = output_path / "raw_results.json"
    with open(raw_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nRaw results saved to {raw_path}")

    # Generate and save report
    report = generate_report(all_results)
    report_path = output_path / "evaluation_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Report saved to {report_path}")

    return all_results


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(results: dict) -> str:
    """Generate a markdown evaluation report from results."""
    lines = [
        "# Search Agent E2E Evaluation Report",
        "",
    ]

    # Overall summary
    all_aggs = [v["aggregate"] for v in results.values() if v.get("aggregate")]
    total_runs = sum(a.get("num_runs", 0) for a in all_aggs)
    total_errors = sum(
        len([r for r in v["runs"] if r.get("error")])
        for v in results.values()
    )

    lines.extend([
        "## Overall Summary",
        "",
        f"- **Test cases:** {len(results)}",
        f"- **Total successful runs:** {total_runs}",
        f"- **Total errors:** {total_errors}",
        "",
    ])

    # Dimension scorecards
    lines.extend(["## Evaluation Dimensions", ""])

    # (a) Task Decomposition
    lines.extend([
        "### (a) Task Decomposition Quality",
        "",
        "| Test Case | Category | Avg Tasks | Expected Range | % In Range |",
        "|-----------|----------|-----------|----------------|------------|",
    ])
    for key, val in results.items():
        agg = val.get("aggregate", {})
        tc = val["test_case"]
        if agg:
            lines.append(
                f"| {tc['goal'][:50]}... | {tc['category']} | "
                f"{agg['avg_task_count']} | "
                f"{tc['expected_task_count_range']} | "
                f"{agg['pct_task_count_in_range']}% |"
            )
    lines.append("")

    # (b) Tool Usage
    lines.extend([
        "### (b) Tool Usage Quality",
        "",
        "| Test Case | Avg Searches | Module/Manual | Avg Iters | Iter Range (actual) |",
        "|-----------|-------------|---------------|-----------|---------------------|",
    ])
    for key, val in results.items():
        agg = val.get("aggregate", {})
        if agg:
            tc = val["test_case"]
            # Compute avg module/manual across runs
            successful = [r for r in val["runs"] if not r.get("error")]
            avg_mod = round(sum(r.get("module_search_count", 0) for r in successful) / len(successful), 1) if successful else 0
            avg_man = round(sum(r.get("manual_search_count", 0) for r in successful) / len(successful), 1) if successful else 0
            lines.append(
                f"| {tc['goal'][:50]}... | {agg['avg_search_executions']} | "
                f"{avg_mod}/{avg_man} | "
                f"{agg['avg_iterations']} | {agg['iteration_range']} |"
            )
    lines.append("")

    # (c) Efficiency
    lines.extend([
        "### (c) Efficiency",
        "",
        "| Test Case | Avg Duplicates | Avg Tokens | Avg Time (s) |",
        "|-----------|---------------|------------|--------------|",
    ])
    for key, val in results.items():
        agg = val.get("aggregate", {})
        if agg:
            tc = val["test_case"]
            lines.append(
                f"| {tc['goal'][:50]}... | "
                f"{agg['avg_duplicate_searches']} | "
                f"{agg['avg_cumulative_tokens']} | "
                f"{agg['avg_elapsed_seconds']} |"
            )
    lines.append("")

    # (d) Result Curation
    lines.extend([
        "### (d) Result Curation Quality",
        "",
        "| Test Case | Avg Top Results | % Found Expected | Top Result Consistency | Course Jaccard |",
        "|-----------|----------------|-----------------|----------------------|---------------|",
    ])
    for key, val in results.items():
        agg = val.get("aggregate", {})
        if agg:
            tc = val["test_case"]
            lines.append(
                f"| {tc['goal'][:50]}... | "
                f"{agg['avg_top_results']} | "
                f"{agg['pct_found_expected_courses']}% | "
                f"{agg['top_result_consistency_pct']}% | "
                f"{agg['course_jaccard_pct']}% |"
            )
    lines.append("")

    # Per-case detailed results
    lines.extend(["## Detailed Results by Test Case", ""])

    for key, val in results.items():
        tc = val["test_case"]
        agg = val.get("aggregate", {})
        runs = val["runs"]

        lines.extend([
            f"### {tc['goal']}",
            f"**Category:** {tc['category']}",
            f"**Description:** {tc['description']}",
            "",
        ])

        if agg:
            lines.extend([
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Runs (successful/total) | {agg['num_runs']}/{len(runs)} |",
                f"| Avg time | {agg['avg_elapsed_seconds']}s |",
                f"| Avg iterations | {agg['avg_iterations']} (range: {agg['iteration_range']}) |",
                f"| Avg tasks created | {agg['avg_task_count']} (range: {agg['task_count_range']}) |",
                f"| Avg unique courses | {agg['avg_unique_courses']} |",
                f"| Avg top results | {agg['avg_top_results']} |",
                f"| Avg search executions | {agg['avg_search_executions']} |",
                f"| Avg duplicate searches | {agg['avg_duplicate_searches']} |",
                f"| Avg tokens | {agg['avg_cumulative_tokens']} |",
                f"| Task count in expected range | {agg['pct_task_count_in_range']}% |",
                f"| Iterations in expected range | {agg['pct_iteration_in_range']}% |",
                f"| Found expected courses | {agg['pct_found_expected_courses']}% |",
                f"| Find status correct | {agg['pct_find_status_correct']}% |",
                f"| Failure count correct | {agg['pct_failure_count_correct']}% |",
                f"| Top result consistency | {agg['top_result_consistency_pct']}% |",
                f"| Course Jaccard across runs | {agg['course_jaccard_pct']}% |",
                f"| Most common top results | {', '.join(agg['most_common_top_results']) or 'none'} |",
                "",
            ])

        # Show task descriptions from each run
        lines.append("**Task decompositions across runs:**")
        for r in runs:
            if r.get("error"):
                lines.append(f"- Run {r['run_index']}: ERROR - {r['error']}")
            else:
                descs = r.get("task_descriptions", [])
                statuses = r.get("task_statuses", [])
                task_strs = [f"{d} [{s}]" for d, s in zip(descs, statuses)]
                lines.append(f"- Run {r['run_index']}: {' | '.join(task_strs)}")
        lines.extend(["", "---", ""])

    return "\n".join(lines)


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Search Agent E2E Evaluation")
    parser.add_argument("-n", "--num-runs", type=int, default=5, help="Runs per test case")
    parser.add_argument("-c", "--category", type=str, default=None, help="Filter by category")
    parser.add_argument("-i", "--index", type=int, default=None, help="Run only test case at index")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    cases = E2E_TEST_CASES
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    if args.index is not None:
        cases = [E2E_TEST_CASES[args.index]]

    # Default output dir includes timestamp
    output_dir = args.output_dir or f"evaluation/results"

    asyncio.run(run_evaluation(
        n_runs=args.num_runs,
        test_cases=cases,
        output_dir=output_dir,
    ))
