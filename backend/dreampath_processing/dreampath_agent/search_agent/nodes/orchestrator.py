import time

from dreampath_processing.dreampath_agent.search_agent.context.building import build_search_context
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    CompleteAction,
    NextAction,
    SearchAction,
    SearchAgentState,
    TaskUpdateAction,
)
import instructor
from instructor import from_openai
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from openai import AsyncOpenAI

SEARCH_ORCHESTRATOR_SYS = """
You are an expert Search Orchestrator that finds the most relevant courses for a given goal. 
Your job is to decide the next action based on:
1. Current task state (task tracking live from system)
2. Search trace (what's happened so far)

# High-Level Decision Process

**If iteration == 0** (first call):
- Task state will be empty
- Analyze the goal
- Return TaskUpdateAction to create initial tasks (3-5 modular tasks)

**If any tasks are "not_started" or "in_progress"**:
- Review task.orchestrator_notes for guidance
- Return SearchAction with 1-5 atomic searches to refine/complete those tasks
- OR return TaskUpdateAction if you need to re-evaluate statuses first

**If all tasks are "complete" or "failed"**:
- Return CompleteAction to finalize

# Output Instructions
You MUST only return structured output (SearchAction | TaskUpdateAction | CompleteAction).

After you return an action:
- SearchAction → Tool executor runs searches, updates task.search_executions automatically
- TaskUpdateAction → System applies your updates to task.status, task.top_results, task.orchestrator_notes
- CompleteAction → Finalizer generates summary from all tasks

## SearchAction: Search Guidelines
For each TaskSearch you create in this Action, you must choose one of the following search tools:

1. module_search(search_description: str) - AI-optimized search
- Uses trained query generator to automatically determine best search parameters
- Best for 90% of cases when you want intelligent parameter selection, or for initial search attemps
- You provide ATOMIC search descriptions (specific, focused, single-query scope)
- **Atomic search constraint**:
  - Search descriptions must be atomic, with specific, focused, and single-query scope
  - If relevant, only include explicit references to ≤ ONE department, ≤ ONE difficulty classification, and ≤ ONE value classification
  - Under the hood, these are 3 filters that the AI-optimized search will use, but each accepts a single value
- Example: module_search("Easy CS courses with high learning value for ML careers")
   
2. manual_search(query, department, difficulty_classification, value_classification, max_num_prereqs, sort_by_level, limit, alpha) - Precise control
- Best for 10% of cases when you need precise control over search parameters and when module_search repeatedly yields incomplete / unsatisfactory results
- As such, you can use corresponding query parameters from the previous module_search as a starting point for refinement
- Example: manual_search(query="machine learning", department="Computer Science", difficulty_classification="Low", limit=5)
- **Atomic search constraint**:
  - As with module search, the query scope must still be atomic. 
  - Manually chosen CourseSearchParams must use:
    - ONE department value (or None)
    - ONE difficulty_classification (or None)
    - ONE value_classification (or None)

    - **Semantic queries CAN include multiple related concepts**:
    ✓ "machine learning deep learning neural networks" → GOOD: one search
    ✓ "data structures algorithms and complexity" → GOOD: one search
    ✗ "machine learning deep learning neural networks in Computer Science and Mathematics" → BAD: Multiple departments, so multiple searches required

**Searches are atomic in nature to improve efficiency, but you are encouraged to use multiple searches when relevant to tasks.**

## TaskUpdateAction: Task Update Guidelines
When returning TaskUpdateAction:

### 1. Initial Task Creation
Guidelines for task decomposition:
- CREATE SEPARATE TASKS when the goal involves distinct domains, topics, or independent requirements
  Example: "Intro bio AND upper-level neuroscience" → 2 tasks (different course types, departments)

- KEEP AS ONE TASK when multiple constraints apply to the SAME search
  Example: "Easy AND highly-rated philosophy" → 1 task (filters on same search)
  Example: "Machine learning with few prereqs" → 1 task (query + filter)

- KEEP AS ONE TASK for information regarding a single course, since a single lookup provides all the information needed
  Example: "Find information about course <course_code>" → 1 task (look up course)
  
- Broad example:
  "Identify relevant courses for interdisciplinary computational biology courses, covering a mix of easy and difficult courses that cover bioinformatics and data analysis fundamentals, as well as a relevant AI for drug discovery course"
  → Likely multiple tasks for corresponding computational biology courses, but 1 task for the AI for drug discovery course

Task Scope:
- If the goal refers to a broad field or topic, (sparingly) use multiple tasks to cover different topics or subfields that are necessary / relevant to the goal.

### 2. Mid-Turn Task Analysis
- For each in-progress or non-started task, analyze the corresponding results (for that task ID)
- Set status based on result quality (not just presence of results)
- Curate top_results: Select up to 10 most relevant course codes from search_executions
  - Review all courses found in search_executions
  - Choose the best matches for the task description
  - Consider diversity, difficulty, prerequisites, relevance w.r.t the task and goal
- Provide actionable orchestrator_notes for "in_progress" tasks
  Example: "Try Biology/Chemistry depts, current results are CS-focused"
- Mark "complete" only if results satisfy the task description
- Mark "failed" after multiple attempts with poor results

### Top Results Curation
The top_results field is YOUR selection of the best courses:
- Review search_executions to see all courses found
- Choose up to 10 most relevant course codes
- This is your expert judgment on which results best satisfy the task
- Frontend will display these as primary results

## CompleteAction: Complete Guidelines
When you study the tasks and determine they have all been completed or failed, you must return CompleteAction.
This signals the end of search execution for the provided goal.

# Output Format
Return an Action according to the provided schema.
"""

def _format_search_action_content(action: SearchAction) -> str:
    """Format SearchAction into human-readable content for context"""
    lines = [f"Reasoning: {action.reasoning}", "", "Searches:"]

    for i, task_search in enumerate(action.searches, 1):
        lines.append(f"{i}. Task {task_search.task_id} - {task_search.action_type}")

        # Format search input based on type
        if task_search.action_type == "module_search":
            lines.append(f"   Query: {task_search.search_input}")
        else:  # manual_search
            params = task_search.search_input
            lines.append(f"   Query: {params.query}")
            if params.department:
                lines.append(f"   Department: {params.department}")
            if params.course_code:
                lines.append(f"   Course code: {params.course_code}")
            if params.max_num_prereqs is not None:
                lines.append(f"   Max prereqs: {params.max_num_prereqs}")
            if params.difficulty_classification:
                lines.append(f"   Difficulty: {params.difficulty_classification}")
            if params.value_classification:
                lines.append(f"   Value: {params.value_classification}")

    return "\n".join(lines)


def _format_task_update_content(action: TaskUpdateAction) -> str:
    """Format TaskUpdateAction into human-readable content for context"""
    lines = [f"Reasoning: {action.reasoning}", "", "Updates:"]

    for update in action.task_updates:
        lines.append(f"Task {update.task_id}: {update.new_status}")
        if update.top_results:
            lines.append(f"  Top results: {', '.join(update.top_results[:5])}{'...' if len(update.top_results) > 5 else ''}")
        lines.append(f"  Notes: {update.orchestrator_notes}")

    return "\n".join(lines)


def _format_complete_content(action: CompleteAction) -> str:
    """Format CompleteAction into human-readable content for context"""
    return f"Reasoning: {action.reasoning}"


def _emit_status(config: RunnableConfig, reason: str):
    """Emit a status message if writer is available in config."""
    writer = config.get("configurable", {}).get("writer")
    if writer:
        status_event = AIMessage(
            content="",
            additional_kwargs={
                "event_type": "node_status",
                "node": "course_search",
                "status": "node_info",
                "next_node": "course_search",
                "reason": reason
            }
        )
        try:
            writer(status_event)
        except Exception as e:
            print(f"  [ORCH] Error emitting status: {e}")


async def orchestrator_node(state: SearchAgentState, config: RunnableConfig) -> dict:
    """
    Main search orchestrator node - decides next action via structured output.

    Returns:
        State updates dict (merged by LangGraph)
    """

    print(f"  [ORCH] Starting orchestrator_node for iteration {state.iteration}")

    # ============================================
    # 1. BUILD CONTEXT (two-block structure)
    # ============================================
    print("  [ORCH] Building context...")
    context_messages, token_updates = build_search_context(
        state=state,
        prompt=SEARCH_ORCHESTRATOR_SYS,
        config=config
    )

    # print("  [ORCH] Context messages:")
    # for message in context_messages:
    #     print(f"    {message['role']}: {message['content']}")

    print(f"  [ORCH] Context built: {len(context_messages)} messages, {token_updates['iteration_tokens'][-1]} tokens")

    # ============================================
    # 2. GET STRUCTURED OUTPUT FROM LLM (instructor)
    # ============================================
    # print(f"  [ORCH] Calling instructor API...")
    # Set mode at client creation time to ensure JSON mode is used
    # This avoids instructor's Response wrapper issue with discriminated unions
    client = from_openai(AsyncOpenAI(), mode=instructor.Mode.JSON)

    # Our messages are already in OpenAI format (role + content dicts)
    next_action: NextAction = await client.chat.completions.create(
        model="gpt-4o",
        messages=context_messages,
        response_model=NextAction,
        temperature=0
    )
    # print(f"  [ORCH] Got response from instructor")

    # ============================================
    # 3. LOG DECISION
    # ============================================
    print(f"\n[ORCHESTRATOR] Iteration {state.iteration}")
    print(f"  Action: {next_action.action_type}")
    print(f"  Reasoning: {next_action.reasoning[:100]}...")

    if isinstance(next_action, SearchAction):
        print(f"  Searches planned: {len(next_action.searches)}")
        for i, search in enumerate(next_action.searches, 1):
            search_desc = search.search_input if isinstance(search.search_input, str) else search.search_input.query
            print(f"    {i}. Task {search.task_id}: {search_desc[:60]}...")

    # ============================================
    # 4. FORMAT DECISION AS MESSAGE (Option A format)
    # ============================================
    # Format content based on action type (node's responsibility!)
    if isinstance(next_action, SearchAction):
        content = _format_search_action_content(next_action)
    elif isinstance(next_action, TaskUpdateAction):
        content = _format_task_update_content(next_action)
    else:  # CompleteAction
        content = _format_complete_content(next_action)

    decision_msg = {
        "role": "orchestrator",
        "args": {
            "action": next_action.action_type,
        },
        "content": content,
        "additional_kwargs": {
            "iteration": state.iteration,
            "timestamp": time.time(),
            "full_action": next_action.model_dump()  # Store full action for debugging
        }
    }

    # ============================================
    # 5. RETURN STATE UPDATES
    # ============================================
    # Note: Don't return messages here - they get streamed via subgraphs=True
    # and cause intermediate content to appear in frontend. Status updates
    # are sent via writer instead.
    return {
        "next_action": next_action,
        "search_trace": state.search_trace + [decision_msg],
        **token_updates
    }