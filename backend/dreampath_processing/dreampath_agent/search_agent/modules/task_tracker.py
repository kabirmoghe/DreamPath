
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchTask,
    TaskStateUpdate,
)
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

# ============================================================================
# Task Tracker Prompts
# ============================================================================

TASK_TRACKER_SYSTEM_PROMPT = """You are the task tracker for a course search agent, an agent that identifies highly relevant college courses for a given search goal.

# Search Agent Overview

## Goal
The search agent is handed a high-level goal upon beginning its search turn.

This goal can be very broad:
- Goal: "Identify relevant courses for interdisciplinary computational biology courses, covering a mix of easy and difficult courses that cover bioinformatics and data analysis fundamentals, as well as a relevant AI for drug discovery course"

This goal can also be very narrow:
- Goal: "Find an easy, highly-rated philosophy course"

The goal can range anywhere between these two examples in depth / breadth.

## Search Agent Capabilities
The search agent can execute several hybrid queries for atomic instructions in parallel, but the atomic nature of these queries is important. Queries look like the following: 

```json
- query: simple semantic/keyword query to search for courses
- alpha: hybrid search weight (0=keyword, 1=semantic)
- department: course dept. to filter by
- course_code: optional specific course code to search for in targetted lookup
- max_num_prereqs: maximum number of prerequisites to filter by
- difficulty_classification: course difficulty filter (low, med., high)
- value_classification: learning value filter (low, med., high)
- sort_by_level: whether to sort results by course level number
- limit: maximum # of results to return
```

Given this, queries reflect finding a course(s) of a very specific nature, domain, topic, etc.
Thus, query scope is **atomic**.

# Task Tracking Instructions
You are responsible for task bookkeeping for the search agent, which includes the following 2 responsibilities:

1. When the search agent is given the high-level goal to begin a search, you initialize a set of tasks.
- You do so by decomposing the high-level goal into necessary tasks that will achieve the goal
- A "task" is modular but not necessarily atomic.
- I.e., a task represents some core aspect of the high-level goal that logically warrants being handled independently.
- Thus, an individual task can be accomplished by at most a handful of atomic queries [1-4].

2. Updating tasks during agent iteration
- The agent will use your tasks to determine which atomic course queries to execute, dynamically reflecting through the process to execute new searches, tweak queries, etc.
- As queries are executed and tasks are in progress, completed, or fail to complete over time, you generate task updates accordingly. 
- This is crucial in guiding the agent's search to determine where to focus search efforts. For example, if you study the course search results and see that Task X is complete / almost done / fails to complete even after a few attempts, update accordingly so the agent knows to move on, continue, etc. 
- The agent will communicate with you via the conversation history; e.g., if agent indicates they've tried multiple search strategies for Task X but can't find better matches, update task accordingly (e..g, → failed, add tracker notes, etc.)
- Lastly, if new tasks need to be created to satisfy a component of the goal that hasn't been met, do so accordingly but only if necessary.

## Task Decomposition Guidance

Guidelines for task decomposition:
- CREATE SEPARATE TASKS when the goal involves distinct domains, topics, or independent requirements
  Example: "CS courses AND math courses" → 2 tasks (different departments)
  Example: "Intro bio AND upper-level neuroscience" → 2 tasks (different course types)

- KEEP AS ONE TASK when multiple constraints apply to the SAME search
  Example: "Easy AND highly-rated philosophy" → 1 task (filters on same search)
  Example: "Machine learning with few prereqs" → 1 task (query + filter)
  

- For broad example:
  "Identify relevant courses for interdisciplinary computational biology courses, covering a mix of easy and difficult courses that cover bioinformatics and data analysis fundamentals, as well as a relevant AI for drug discovery course"
  → Likely multiple tasks for corresponding computational biology courses, but 1 task for the AI for drug discovery course

Task Scope:
- If the goal refers to a broad field or topic, (sparingly) use multiple tasks to cover different topics or subfields that are necessary / relevant to the goal.

## Ending Search
When you deem that each task has been completed / failed to complete, ensure that they are all updated accordingly such that the search can terminate accordingly. 

# Output Format
Output a valid TaskStateUpdate according to the provided schema. 
This contains either a freshly initialized set of tasks (responsibility 1) or a mid-turn update to tasks (responsibility 2).
"""

TASK_INIT_MESSAGE = """
Break down this search agent goal into modular, actionable tasks.

High-level goal: {goal}

A task should represent a cohesive search goal that can be satisfied with 1-4 atomic queries.
Multiple constraints (difficulty, value, prereqs) are PARAMETERS of a single task, not separate tasks.
"""

TASK_UPDATE_MESSAGE = """
Update task status based on the agent's search execution and results.

Current tasks:
{tasks}

Instructions:
- Review recent tool results (module_search/manual_search calls) in the conversation
- Extract CourseSearchOutput from tool results and populate task.results field
- Extract CourseSearchParams from tool calls and ADD to task.queries_used list (append, don't replace)
  - This tracks how many search attempts have been made per task
  - Example: If Task 1 just used 2 searches, add both CourseSearchParams to queries_used
- Aggregate results from multiple searches if they correspond / satisfy the same task
- Update task status:
  - "in progress" if queries executed but task not fully satisfied
  - "complete" if good results found and agent seems satisfied
  - "failed" if multiple attempts (check queries_used length) but can't find good results
  - "not started" if not yet attempted
- **CRITICAL**: For EACH task, populate the `tracker_notes` field with task-specific guidance:
  - If "in progress": Explain what's missing and suggest next refinement strategy
    Example: "Current results are AI/neurotech focused, not drug discovery. Try searching Biology/Chemistry depts or use 'pharmaceutical' keywords"
  - If "complete": Brief note on why results satisfy the task
  - If "failed": Explain what was tried and why it didn't work
  - Keep notes concise (1-2 sentences max per task)
- Only create new tasks if a clear gap in the search goal is identified
"""

def format_tasks_for_display(tasks: list[SearchTask]) -> str:
    """Format task list for prompt readability"""
    if not tasks:
        return "No tasks yet."

    output = []
    for task in tasks:
        output.append(f"Task {task.task_id}: {task.description}")
        output.append(f"  Status: {task.status}")
        output.append(f"  Queries used: {len(task.queries_used)}")

        if task.results and task.results.results:
            # Show course codes for better task evaluation
            course_codes = [c.course_code for c in task.results.results]
            output.append(f"  Results: {', '.join(course_codes)}")
        else:
            output.append("  Results: None yet")

        output.append("")

    return "\n".join(output)

async def task_tracking_node(state: SearchAgentState, config) -> dict:
    """
    Creates tasks from user request OR updates based on agent's evaluation.

    Uses a small/fast model (gpt-4o-mini) for structured task management.
    """

    # Get model from config or use default, use o3 mini
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    current_tasks = state.tasks
    messages = state.messages
    iteration = state.iteration
    goal = state.goal

    messages = [SystemMessage(content=TASK_TRACKER_SYSTEM_PROMPT)] + messages
    new_messages = []

    # CREATION (iteration 0): Extract tasks from user request
    if iteration == 0 and not current_tasks:
        print("\n[TASK TRACKER] Creating tasks from goal...")

        # Add initialization message to messages
        new_messages.append(SystemMessage(content=TASK_INIT_MESSAGE.format(goal=goal)))
        messages = messages + new_messages

        # Invoke LLM
        task_update = await llm.with_structured_output(TaskStateUpdate).ainvoke(messages)
        print(f"[TASK TRACKER] Created {len(task_update.tasks)} tasks")

        # Assign task IDs (LLM doesn't generate these)
        for i, task in enumerate(task_update.tasks):
            if task.task_id is None:
                task.task_id = i + 1

        # Add status message to conversation
        status_msg = f"Created {len(task_update.tasks)} tasks:\n{format_tasks_for_display(task_update.tasks)}"
        new_messages.append(AIMessage(content=status_msg))

        return {
            "tasks": task_update.tasks,
            "messages": new_messages,  # Only append new messages (operator.add)
            "iteration": iteration
        }

    # UPDATE (subsequent iterations): Interpret agent's evaluation
    else:
        print(f"\n[TASK TRACKER] Updating tasks (iteration {iteration})...")

        # Add update message to messages
        new_messages.append(SystemMessage(content=TASK_UPDATE_MESSAGE.format(tasks=format_tasks_for_display(current_tasks))))
        messages = messages + new_messages

        # Invoke LLM
        task_update = await llm.with_structured_output(TaskStateUpdate).ainvoke(messages)

        # Preserve existing task IDs, assign new ones to new tasks
        existing_ids = {t.task_id for t in current_tasks if t.task_id is not None}
        next_id = max(existing_ids) + 1 if existing_ids else 1

        for task in task_update.tasks:
            if task.task_id is None:
                task.task_id = next_id
                next_id += 1

        # Add status message
        completed = sum(1 for t in task_update.tasks if t.status == "complete")
        failed = sum(1 for t in task_update.tasks if t.status == "failed")
        in_progress = sum(1 for t in task_update.tasks if t.status == "in progress")

        status_msg = f"Task update: {completed} complete, {in_progress} in progress, {failed} failed"

        print(f"[TASK TRACKER] {status_msg}")
        new_messages.append(AIMessage(content=status_msg))

        return {
            "tasks": task_update.tasks,
            "messages": new_messages,  # Only append new messages (operator.add)
            "iteration": iteration + 1
        }