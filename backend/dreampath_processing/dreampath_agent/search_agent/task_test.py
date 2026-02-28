import asyncio
import os
import time

from dreampath_processing.dreampath_agent.search_agent.context.building import (
    _render_message_lines,
    _render_task_state_block,
    _render_tool_result,
)
from dreampath_processing.dreampath_agent.search_agent.graph import build_search_agent
from dreampath_processing.dreampath_agent.search_agent.nodes.summarize import (
    render_search_summary_markdown,
)
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    FinalSearchSummary,
    SearchAgentState,
)
from dreampath_processing.dreampath_agent.search_agent.strategy import get_strategy

EVAL_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation", "outputs")


def _render_full_trace(search_trace: list[dict], strategy) -> str:
    """Render the entire search trace with no compaction."""
    lines = []
    current_iter = None
    for msg in search_trace:
        msg_iter = msg.get("additional_kwargs", {}).get("iteration", 0)
        if msg_iter != current_iter:
            if current_iter is not None:
                lines.append("</iteration>")
            lines.append(f"<iteration number='{msg_iter}'>")
            current_iter = msg_iter

        if msg.get("role") == "tool":
            lines.extend(_render_tool_result(msg, compact=False, strategy=strategy))
        else:
            lines.extend(_render_message_lines(msg))

    if current_iter is not None:
        lines.append("</iteration>")
    return "\n".join(lines)


def _render_test_output(goal: str, final_state: dict, elapsed: float, strategy) -> str:
    """Render a complete test output file from final state."""
    sections = []

    # Header
    sections.append(f"Goal: {goal}")
    sections.append(f"Time: {elapsed:.2f}s | Iterations: {final_state['iteration']} | Tasks: {len(final_state['tasks'])}")
    sections.append(f"Tokens per iteration: {final_state['iteration_tokens']}")
    sections.append(f"Cumulative tokens: {final_state['cumulative_tokens']}")
    sections.append("")

    # Full search trace (uncompacted)
    sections.append("=" * 80)
    sections.append("SEARCH TRACE (full, uncompacted)")
    sections.append("=" * 80)
    sections.append(_render_full_trace(final_state['search_trace'], strategy))
    sections.append("")

    # Final task state
    sections.append("=" * 80)
    sections.append("FINAL TASK STATE")
    sections.append("=" * 80)
    sections.append(_render_task_state_block(
        goal=goal,
        iteration=final_state['iteration'],
        tasks=final_state['tasks'],
        strategy=strategy,
    ))
    sections.append("")

    # Final summary
    sections.append("=" * 80)
    sections.append("FINAL SUMMARY")
    sections.append("=" * 80)
    if final_state.get('structured_summary'):
        sections.append(render_search_summary_markdown(final_state['structured_summary']))
    elif final_state.get('final_summary'):
        sections.append(final_state['final_summary'])
    else:
        sections.append("(no summary produced)")

    return "\n".join(sections)


async def test(goal: str, index: int) -> FinalSearchSummary:
    graph = build_search_agent()

    initial_state = SearchAgentState(goal=goal)
    strategy = get_strategy(initial_state.domain)

    start_time = time.time()
    print(f"\n[Run {index}] Invoking Search Agent...\n")
    final_state = await graph.ainvoke(initial_state)
    elapsed = time.time() - start_time

    # Console summary
    print(f"\n[Run {index}] Done in {elapsed:.1f}s | {final_state['iteration']} iterations | {len(final_state['tasks'])} tasks")
    for task in final_state['tasks']:
        print(f"  Task {task.task_id} [{task.status}]: {task.description[:70]}  -> {task.top_results}")

    # Write full rendered output
    os.makedirs(EVAL_OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(EVAL_OUTPUT_DIR, f"run_{index}.txt")
    output = _render_test_output(goal, final_state, elapsed, strategy)
    with open(filepath, "w") as f:
        f.write(output)
    print(f"  Written to {filepath}")

    return final_state['structured_summary']

async def main() -> list[FinalSearchSummary]:
    goal = "find courses for student in software looking to learn about rapid prototyping, building MVPs, develop skills in being client facing, and full developer skills (full stack, working with DBs)"

    # Run 5 search agents in parallel
    structured_results = await asyncio.gather(*[test(goal, i) for i in range(5)])

    return structured_results

if __name__ == "__main__":
    structured_results = asyncio.run(main())

    for i, result in enumerate(structured_results):
        print(f"========== Result {i+1} ==========")
        print(render_search_summary_markdown(result))
