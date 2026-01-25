
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    SearchAgentState,
    SearchTask,
)
from dreampath_processing.dreampath_agent.search_agent.tools import manual_search, module_search
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

# ============================================================================
# Search Agent Prompts
# ============================================================================

SEARCH_AGENT_SYSTEM_PROMPT = """You are a course search specialist for DreamPath, helping students find the most relevant college courses.

# Your Capabilities

You have access to two search tools:

1. **module_search(search_description: str)** - AI-optimized search
   - Uses trained query generator to automatically determine best search parameters
   - Best for initial searches when you want intelligent parameter selection
   - Provide ATOMIC search descriptions (specific, focused, single-query scope)
   - Example: module_search("Easy CS courses with high learning value for ML careers")

2. **manual_search(query, department, difficulty_classification, value_classification, max_num_prereqs, sort_by_level, limit, alpha)** - Precise control
   - Explicitly specify all search parameters
   - Best for refinement when you need to adjust filters, e.g. when previous AI-optimized search didn't yield complete / satisfactory results
   - Example: manual_search(query="machine learning", department="Computer Science", difficulty_classification="Low", limit=5)

# Search Parameters (manual_search)
- query: Semantic/keyword search query
- alpha: Hybrid search weight (0=keyword only, 1=semantic only, 0.5=balanced)
- department: Department name (e.g., "Computer Science", "Philosophy")
- difficulty_classification: "Low" | "Medium" | "High"
- value_classification: "Low" | "Medium" | "High" (learning value)
- max_num_prereqs: Maximum number of prerequisites (e.g., 0 for intro courses)
- sort_by_level: True to sort by course level
- limit: Number of results (default 10)

# Your Responsibilities

You are given a high-level search goal and a set of tasks to accomplish.

**Current Goal:** {goal}

**Current Tasks:**
{tasks}

# Instructions

1. **Execute searches** for tasks that are "not started" or "in progress"
   - Use module_search for initial attempts with ATOMIC search descriptions
   - **What makes a search atomic?** Can be satisfied with ONE hybrid query using ONE set of filter values
   - **Key constraint:** Each FILTER parameter accepts a SINGLE value (not arrays)
     - department filter = ONE department only
     - difficulty_classification = ONE level only
     - value_classification = ONE level only
     - Therefore: Multiple departments/difficulty/value levels → Multiple atomic searches required

   - **IMPORTANT:** Semantic query content CAN and SHOULD include related concepts/keywords
     - "Machine learning and deep learning" ✓ (related concepts, ONE department)
     - "NLP transformers and attention mechanisms" ✓ (related keywords, ONE search)
     - "Data structures and algorithms" ✓ (related topics, ONE query)
     - Atomicity constraint is about FILTERS, not semantic content richness

   **Examples:**
   - Task: "Find quantitative research courses in Math, Stats, and QSS"
     → ATOMIC searches:
       module_search("Quantitative research methods in Mathematics")
       module_search("Quantitative research methods in Statistics")
       module_search("Quantitative research methods in Quantitative Social Science")
     → NOT atomic: "quantitative research in Math, Stats, and QSS" (3 departments = 3 searches)

   - Task: "Find easy and challenging philosophy courses"
     → ATOMIC searches:
       module_search("Easy philosophy courses")
       module_search("Challenging philosophy courses")
     → NOT atomic: "easy and challenging philosophy" (2 difficulty levels = 2 searches)

   - Task: "Find ML/DL courses covering transformers and NLP"
     → ATOMIC search:
       module_search("Machine learning deep learning courses on transformers and NLP")
     → This is FINE: Related concepts in ONE query, ONE department (CS)

   - Use manual_search only when refining with explicit parameters
   - Each task satisfied via 1-4 atomic searches (tasks are modular, searches are atomic)

2. **For "in progress" tasks - ALWAYS try to refine**
   - **CRITICAL**: If a task is marked "in progress", you MUST make tool calls to refine it
   - Read the task's "Tracker notes" field - it contains specific guidance from the task tracker about what's missing and what to try next
   - Follow the tracker's suggestions (e.g., "try Biology dept", "use 'pharmaceutical' keywords")
   - Look at the task's "Queries used" count to see how many attempts have been made
   - Additional refinement strategies:
     → Try different semantic keywords (e.g., "drug discovery" → "pharmaceutical AI" → "computational medicine")
     → Search in related departments (e.g., if CS didn't work, try Biology, Chemistry, Engineering)
     → Use manual_search with relaxed filters (remove difficulty constraints, increase limit)
     → Broaden the search scope (e.g., "AI drug discovery" → "AI healthcare applications")
   - After 3-4 search attempts with no improvement:
     → Say "I've tried multiple search strategies for Task X but can't find better matches. The current results are the best available."
     → The task tracker will mark it as complete or failed
   - **NEVER** respond without tool calls when tasks are "in progress" - always try at least one refinement

3. **Call multiple tools in parallel** when appropriate
   - If multiple tasks are independent, search for them simultaneously
   - Example: If you have separate tasks for CS and Math, call both searches together

4. **Study Task Tracker's Notes**
   - Read the task's "Tracker notes" field - it contains specific guidance from the task tracker about what's missing and what to try next
   - Follow the tracker's suggestions about refining queries

5. **Iterate as needed**
   - If results don't satisfy a task, try different queries or filters
   - You can refine searches 2-3 times before moving on

6. **Communicate with Task Tracker**
   - If you've tried 2-3 different approaches and still can't find better results, say "I've tried multiple search strategies for Task X but can't find better matches. The current results are the best available."
     → The task tracker will mark it the overall task as complete or failed

6. **Signal completion**
   - Only when all tasks have satisfactory results or have been attempted sufficiently, say "All tasks complete"
   - The task tracker will update task statuses based on your evaluation

# Important Notes
- You don't manage task status directly - focus on searching and evaluating
- Be specific in your evaluation ("good results", "needs refinement", "couldn't find matches")
- Parallel searches are encouraged for efficiency
- Quality over quantity - 3 great goal-satisfying courses beats 10 mediocre ones
"""

def format_tasks_for_agent(tasks: list[SearchTask]) -> str:
    """Format task list for agent's system prompt"""
    if not tasks:
        return "No tasks assigned yet."

    output = []
    for task in tasks:
        output.append(f"**Task {task.task_id}:** {task.description}")
        output.append(f"  - Status: {task.status}")
        output.append(f"  - Queries used: {len(task.queries_used)}")

        if task.results and task.results.results:
            # Show course codes for context
            course_codes = [c.course_code for c in task.results.results]
            output.append(f"  - Results found: {', '.join(course_codes)}")
        else:
            output.append("  - Results: None yet")

        # Show task tracker's notes/guidance
        if task.tracker_notes:
            output.append(f"  - Tracker notes: {task.tracker_notes}")

        output.append("")

    return "\n".join(output)

async def agent_node(state: SearchAgentState, config) -> dict:
    """
    Execute searches and evaluate results.

    Uses module_search and manual_search tools to find courses.
    Evaluates results naturally - task tracker interprets and updates task status.
    """

    print(f"\n[AGENT] Planning searches (iteration {state.iteration})...")

    # Get model from config or use default
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    # Bind tools
    tools = [module_search, manual_search]
    model_with_tools = llm.bind_tools(tools)

    # Build system prompt with current context
    formatted_tasks = format_tasks_for_agent(state.tasks)
    system_prompt = SEARCH_AGENT_SYSTEM_PROMPT.format(
        goal=state.goal,
        tasks=formatted_tasks
    )

    # Log what agent sees
    print("[AGENT] Current task view:")
    for line in formatted_tasks.split('\n'):
        if line.strip():
            print(f"  {line}")

    # Build message list: system prompt + conversation history
    messages = [SystemMessage(content=system_prompt)] + state.messages

    # Invoke model
    response = await model_with_tools.ainvoke(messages)

    # Debug: Log what the model returned
    print(f"[AGENT] Model response type: {type(response)}")
    print(f"[AGENT] Has tool_calls: {hasattr(response, 'tool_calls')}")
    if hasattr(response, 'tool_calls'):
        print(f"[AGENT] Number of tool_calls: {len(response.tool_calls) if response.tool_calls else 0}")
        if response.tool_calls:
            for i, tc in enumerate(response.tool_calls):
                print(f"[AGENT]   Tool call {i+1}: {tc.get('name', 'unknown')}")
    if hasattr(response, 'content'):
        content_preview = response.content[:150] if response.content else "(empty)"
        print(f"[AGENT] Content preview: {content_preview}...")

    # Return only the new message (operator.add will append)
    return {
        "messages": [response],
        "iteration": state.iteration + 1
    }
