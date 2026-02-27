from dreampath_processing.dreampath_agent.search_agent.context.building import build_search_context
from dreampath_processing.dreampath_agent.search_agent.nodes.orchestrator import (
    SEARCH_ORCHESTRATOR_SKELETON,
)
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    CourseSearchOutput,
    CourseSearchParams,
    CourseSearchResult,
    SearchAgentState,
    SearchExecution,
    SearchTask,
)

if __name__ == "__main__":

    import time

    sample_search_trace = [
        {
            "role": "orchestrator",
            "args": {
                "action": "update_tasks",
                "task_updates": "...task updates...",
            },
            "content": "Reasoning for the update",
            "additional_kwargs": {
                "iteration": 0
            }
        },
        {
            "role": "orchestrator",
            "args": {
                "action": "search",
                "searches": "...searches...",
            },
            "content": "Reasoning for the action",
            "additional_kwargs": {
                "iteration": 1
            }
        },
        {
            "role": "tool",
            "args": {
                "name": "module_search",
                "type": "result",
                "task_id": "...",
            },
            "content": "Result for the search",
            "additional_kwargs": {
                "iteration": 1
            }
        },
        {
            "role": "orchestrator",
            "args": {
                "action": "update_tasks",
                "task_updates": "...task updates...",
            },
            "content": "Reasoning for the update",
            "additional_kwargs": {
                "iteration": 2
            }
        },
        {
            "role": "orchestrator",
            "args": {
                "action": "search",
                "searches": "...searches...",
            },
            "content": "Reasoning for the action",
            "additional_kwargs": {
                "iteration": 3
            }
        },
        {
            "role": "tool",
            "args": {
                "name": "manual_search",
                "type": "result",
                "task_id": "...",
            },
            "content": "Result for the search",
            "additional_kwargs": {
                "iteration": 3
            }
        },
    ]

    sample_task_state = [
        SearchTask(**{
            "task_id": 1,
            "status": "complete",
            "description": "Find ML courses",
            "search_executions": [
                SearchExecution(
                    params= CourseSearchParams(
                        query="ML courses",
                        alpha=0.5
                    ),
                    output= CourseSearchOutput(
                        results=[CourseSearchResult(course_code="X", department="X", course_title="X", description="X", prerequisites="X", course_url="X", num_prereqs=0, total_reviews=0, global_difficulty_percentile=0, global_difficulty_classification="X", dept_difficulty_percentile=0, dept_difficulty_classification="X", difficulty_blurb="X", global_value_percentile=0, global_value_classification="X", dept_value_percentile=0, dept_value_classification="X", learning_value_blurb="X", target_audience_blurb="X")]
                    ),
                    iteration=0,
                    timestamp=time.time()
                )
            ],
            "top_results": ["ML101", "ML201"],
            "orchestrator_notes": "Task complete, good variety found",
            "created_iteration": 0,
            "last_updated_iteration": 0,
            }),
        SearchTask(**{
            "task_id": 2,
            "status": "in_progress",
            "description": "Find philosophy courses",
            "search_executions": [
                SearchExecution(
                    params= CourseSearchParams(
                        query="Philosophy courses",
                        alpha=0.5
                    ),
                    output= CourseSearchOutput(
                        # contains all the fields from CourseSearchResult
                        results=[CourseSearchResult(course_code="X", department="X", course_title="X", description="X", prerequisites="X", course_url="X", num_prereqs=0, total_reviews=0, global_difficulty_percentile=0, global_difficulty_classification="X", dept_difficulty_percentile=0, dept_difficulty_classification="X", difficulty_blurb="X", global_value_percentile=0, global_value_classification="X", dept_value_percentile=0, dept_value_classification="X", learning_value_blurb="X", target_audience_blurb="X")]
                    ),
                    iteration=1,
                    timestamp=time.time()
                )
            ],
            "top_results": ["PH101", "PH201"],
            "orchestrator_notes": "Task in progress, need more challenging courses",
            "created_iteration": 0,
            "last_updated_iteration": 0,
        })
    ]
    
    ctx, token_updates = build_search_context(
        state=SearchAgentState(goal="Find ML courses", search_trace=sample_search_trace, tasks=sample_task_state),
        prompt=SEARCH_ORCHESTRATOR_SKELETON
    )

    print("=" * 80)
    print("CONTEXT MESSAGES:")
    print("=" * 80)
    for message in ctx:
        role = message.get("role", "user")
        content = message.get("content", "")
        print(f"\n[{role.upper()}]")
        print(content)
        print("-" * 80)

    print("\n" + "=" * 80)
    print("TOKEN UPDATES:")
    print("=" * 80)
    print(f"Iteration tokens: {token_updates['iteration_tokens']}")
    print(f"Cumulative tokens: {token_updates['cumulative_tokens']}")
