"""Test the compiled search agent graph end-to-end"""
import asyncio
import time
import warnings

from dreampath_processing.dreampath_agent.search_agent.graph import build_search_agent
from dreampath_processing.dreampath_agent.search_agent.nodes.finalizer import render_search_summary_markdown
from dreampath_processing.dreampath_agent.search_agent.search_types import SearchAgentState

# Suppress unclosed transport warnings from async clients (Weaviate, OpenAI)
# These occur when asyncio.run() is called repeatedly in interactive mode
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

tests = ["Find easy ML courses and challenging philosophy courses", 
         "Find info on COSC74", 
         "Find info on QSS20",
         "Find a class on computer vision",
         "Find classes covering core computational biology topics without many prerequisites",
         "Determine if there is a class on the history of AI",
         "Find info on COSC123",
         "Find interdisciplinary courses that may offer a new perspective on LLMs and AI"]

async def test_graph_execution():
    """Test full graph execution with a real search goal"""

    print("=" * 80)
    print("BUILDING SEARCH AGENT GRAPH")
    print("=" * 80)

    # Build the compiled graph
    graph = build_search_agent()

    print("\n" + "=" * 80)
    print("EXECUTING SEARCH AGENT")
    print("=" * 80)

    # Create initial state
    for test_index, test_search_goal in enumerate(["Find interdisciplinary courses that may offer a new perspective on LLMs and AI"]):
        print(f"\nTest {test_index + 1} of {len(tests)}: goal='{test_search_goal}'")
        initial_state = SearchAgentState(
            goal=test_search_goal
        )
        start_time = time.time()
        final_state = await graph.ainvoke(initial_state)
        elapsed = time.time() - start_time

        print(f"\n⏱️  Total execution time: {elapsed:.2f}s")
        print(f"📊 Final iteration: {final_state['iteration']}")
        print(f"📝 Tasks created: {len(final_state['tasks'])}")

        print("\n--- Task Results ---")
        for task in final_state['tasks']:
            print(f"\nTask {task.task_id}: {task.description[:80]}...")
            print(f"  Status: {task.status}")
            print(f"  Searches: {len(task.search_executions)}")
            print(f"  Top results: {task.top_results}")

            # Show unique courses found
            all_courses = []
            for ex in task.search_executions:
                all_courses.extend(ex.output.results)
            unique_codes = {c.course_code for c in all_courses}
            print(f"  Unique courses: {len(unique_codes)}")

        print("\n--- Final Summary ---")
        if final_state.get('final_summary'):
            print(final_state['final_summary'])

        print("\n--- Token Usage ---")
        print(f"  Iteration tokens: {final_state['iteration_tokens']}")
        print(f"  Cumulative: {final_state['cumulative_tokens']}")
        print("\n" + "=" * 80)

async def test(goal: str):
    graph = build_search_agent()

    # Create initial state
    initial_state = SearchAgentState(
        goal=goal
    )

    start_time = time.time()

    # Invoke the graph
    print("\nInvoking Search Agent...\n")
    final_state = await graph.ainvoke(initial_state)

    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("EXECUTION COMPLETE")
    print("=" * 80)

    print(f"\n⏱️  Total execution time: {elapsed:.2f}s")
    print(f"📊 Final iteration: {final_state['iteration']}")
    print(f"📝 Tasks created: {len(final_state['tasks'])}")

    print("\n--- Task Results ---")
    for task in final_state['tasks']:
        print(f"\nTask {task.task_id}: {task.description[:80]}...")
        print(f"  Status: {task.status}")
        print(f"  Searches: {len(task.search_executions)}")
        print(f"  Top results: {task.top_results}")

        # Show unique courses found
        all_courses = []
        for ex in task.search_executions:
            all_courses.extend(ex.output.results)
        unique_codes = {c.course_code for c in all_courses}
        print(f"  Unique courses: {len(unique_codes)}")

    print("\n--- Final Summary ---")
    if final_state.get('structured_summary'):
        print(render_search_summary_markdown(final_state['structured_summary'], verbosity=2))

    print("\n--- Token Usage ---")
    print(f"  Iteration tokens: {final_state['iteration_tokens']}")
    print(f"  Cumulative: {final_state['cumulative_tokens']}")

    # Complete messages
    print("\n--- Complete Messages ---")
    for message in final_state['messages']:
        print(f"{message.type}: {message.content}")

if __name__ == "__main__":
    # from dreampath_processing.dreampath_agent.search_agent.tools.course_search_client import CourseSearchClient
    # course_search_client = CourseSearchClient()

    # # # params = {"query": "", "alpha": 0.0, "course_code": "COSC74", "sort_by_level": false, "limit": 1}
    # results = course_search_client.hybrid_search(query='', course_code='COSC74', limit=1, alpha=0.0, sort_by_level=False, department=None, max_num_prereqs=None, difficulty_classification=None, value_classification=None)
    # print(results)


    while True:
        goal = input("Enter a search goal: ")
        if goal == "exit":
            break
        asyncio.run(test(goal))

    # asyncio.run(test_graph_execution())