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

**If all tasks are "complete", "partially_complete", or "failed"**:
- Return CompleteAction to finalize

# Output Instructions
You MUST only return structured output (SearchAction | TaskUpdateAction | CompleteAction).

After you return an action:
- SearchAction → Tool executor runs searches, updates task.search_executions automatically
- TaskUpdateAction → System applies your updates to task.status, task.top_results, task.orchestrator_notes
- CompleteAction → Summarizer generates summary from all tasks

## SearchAction: Search Guidelines
For each TaskSearch you create in this Action, you must choose one of the following search tools:

1. module_search(search_description: str) - AI-optimized search
- Uses trained query generator to automatically determine best search parameters
- Best for 90% of cases when you want intelligent parameter selection, or for initial search attemps
- You provide ATOMIC search descriptions (specific, focused, single-query scope)
- **Atomic search constraint**:
  - Use terms and concepts that are likely to be found in a course catelog (e.g., computer science instead of software engineering, )
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

### Search Strategy: Explore Before Settling
- **First search round**: Use broad, department-agnostic module_search to discover which departments have relevant courses.
- **Follow-up rounds**: If initial results are mediocre or narrowly concentrated in one department, explicitly explore adjacent departments rather than rewording the same query.
  - Many topics span multiple departments. E.g., "data analysis" lives in Computer Science, Mathematics, QSS, Economics, and Engineering.
  - Industry-specific terms (e.g., "consulting", "software engineering", "product management") may not appear in academic course catalogs. When these terms yield poor results, pivot to the underlying academic disciplines and explore specific departments.
    Example: "consulting skills" → try searches in Economics, Speech, Psychology departments
    Example: "software engineering" → try Computer Science, or Engineering Sciences departments depending on goal's implied domain, desired skills, etc.
- **Do not** mark a task complete or partially_complete after only one search round unless the results are clearly strong and goal scope is inherently hyper-specific. If initial results are decent but narrow, run at least one more round targeting different departments before settling.

## TaskUpdateAction: Task Update Guidelines
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
This signals the end of search execution for the provided goal.

# Core Example

This example illustrates correct orchestrator behavior — especially honest failure. Completing a task with loosely related courses is far worse than marking it failed with a clear explanation.

## Mixed Success and Failure

Goal: "Find courses on DevOps/CI-CD practices, blockchain development, and systems programming"

Iteration 0 → TaskUpdateAction
  Task 1: "Find courses on DevOps practices, CI/CD pipelines, and infrastructure automation"
  Task 2: "Find courses on blockchain development and distributed ledger technology"
  Task 3: "Find courses on systems programming: C, OS internals, low-level computing"

Iteration 1 → SearchAction
  Task 1: module_search(search_description='DevOps CI/CD pipeline infrastructure automation courses')
  Task 2: module_search(search_description='Blockchain development distributed ledger technology courses')
  Task 3: module_search(search_description='Systems programming C operating systems low-level')
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
  Task 1: module_search(search_description='Software deployment automation continuous integration')
  Task 2: module_search(search_description='Cryptography distributed systems peer-to-peer networks')
  → Task 1: general CS courses again — still nothing on DevOps/CI-CD
  → Task 2: finds COSC60 (Networks), MATH75 (Crypto) — adjacent but not blockchain

Iteration 4 → TaskUpdateAction ...

Iteration 5 → SearchAction ...

Iteration 6 → TaskUpdateAction ...

Iteration 7 → SearchAction ...

Iteration 8 → TaskUpdateAction ...

Iteration 9 → SearchAction ...

Iteration 10 → TaskUpdateAction
  Task 1: failed | top_results: []
  Notes: "After multiple diverse search rounds, no courses cover DevOps, CI/CD, or infrastructure automation. COSC50 teaches software practices and COSC52 touches deployment, but neither addresses DevOps tooling or CI/CD workflows."
  Task 2: failed | top_results: []
  Notes: "No courses cover blockchain or distributed ledger technology. Found adjacent courses (COSC60 networking, MATH75 cryptography) but none address blockchain itself. The catalog does not offer blockchain-focused courses."

Iteration 11 → CompleteAction
  "1 of 3 tasks completed. Strong systems programming coverage found. DevOps/CI-CD and blockchain are industry-specific topics not represented in the academic catalog."

# Output Format
Return an Action according to the provided schema.
"""

def _format_search_action_content(action: SearchAction) -> str:
    """Format SearchAction into human-readable content for context"""
    lines = [f"Reasoning: {action.reasoning}", "", "Searches:"]

    for i, task_search in enumerate(action.searches, 1):
        if task_search.action_type == "module_search":
            lines.append(f"{i}. Task {task_search.task_id} - module_search(search_description='{task_search.search_input}')")
        else:  # manual_search
            params = task_search.search_input
            kwargs = {k: v for k, v in params.model_dump().items() if v is not None}
            kwargs_str = ", ".join(f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in kwargs.items())
            lines.append(f"{i}. Task {task_search.task_id} - manual_search({kwargs_str})")

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


async def orchestrator_node(state: SearchAgentState, config: RunnableConfig, verbose=False) -> dict:
    """
    Main search orchestrator node - decides next action via structured output.

    Returns:
        State updates dict (merged by LangGraph)
    """

    if verbose:
        print(f"  [ORCH] Starting orchestrator_node for iteration {state.iteration}")
        print(f"  [ORCH] Goal: {state.goal}")

    # ============================================
    # 1. BUILD CONTEXT (two-block structure)
    # ============================================
    if verbose:
        print("  [ORCH] Building context...")
    context_messages, token_updates = build_search_context(
        state=state,
        prompt=SEARCH_ORCHESTRATOR_SYS,
        config=config
    )

    if verbose:
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
        temperature=0,
    )
    # print(f"  [ORCH] Got response from instructor")

    # ============================================
    # 3. LOG DECISION
    # ============================================
    if verbose:
        print(f"\n[ORCHESTRATOR] Iteration {state.iteration}")
        print(f"  Action: {next_action.action_type}")
        print(f"  Reasoning: {next_action.reasoning[:100]}...")

    if isinstance(next_action, SearchAction):
        if verbose:
            print(f"  Searches planned: {len(next_action.searches)}")
        for i, search in enumerate(next_action.searches, 1):
            search_desc = search.search_input if isinstance(search.search_input, str) else (search.search_input.query or str(search.search_input))
            if verbose:
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
        "latest_reasoning": next_action.reasoning,
        "search_trace": state.search_trace + [decision_msg],
        "system_warning": False,
        **token_updates
    }