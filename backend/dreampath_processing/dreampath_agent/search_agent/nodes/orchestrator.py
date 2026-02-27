import time

from dreampath_processing.dreampath_agent.search_agent.context.building import build_search_context
from dreampath_processing.dreampath_agent.search_agent.search_types import (
    CompleteAction,
    NextAction,
    SearchAction,
    SearchAgentState,
    TaskUpdateAction,
)
from dreampath_processing.dreampath_agent.search_agent.strategy import get_strategy
from langchain_core.runnables import RunnableConfig
from openai import AsyncOpenAI

# ============================================
# Orchestrator system prompt skeleton
# ============================================
# Domain-specific sections are injected via strategy.get_orchestrator_prompt_sections()

SEARCH_ORCHESTRATOR_SKELETON = """
You are an expert Search Orchestrator that finds the most relevant results for a given goal.
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

{search_guidelines}

{task_guidelines}

{example}

# Output Format
Return an Action according to the provided schema.
"""


def _format_search_action_content(action: SearchAction) -> str:
    """Format SearchAction into human-readable content for context"""
    lines = [f"Reasoning: {action.reasoning}", "", "Searches:"]

    for i, task_search in enumerate(action.searches, 1):
        lines.append(f"{i}. Task {task_search.task_id} - search(\"{task_search.search_description}\")")

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

    Gets the search strategy from config to use domain-specific prompts and schemas.
    """

    if verbose:
        print(f"  [ORCH] Starting orchestrator_node for iteration {state.iteration}")
        print(f"  [ORCH] Goal: {state.goal}")

    # Resolve strategy from state.domain
    strategy = get_strategy(state.domain)

    # ============================================
    # 1. BUILD PROMPT WITH DOMAIN-SPECIFIC SECTIONS
    # ============================================
    prompt_sections = strategy.get_orchestrator_prompt_sections()
    prompt = SEARCH_ORCHESTRATOR_SKELETON.format(**prompt_sections)

    # ============================================
    # 2. BUILD CONTEXT (two-block structure)
    # ============================================
    if verbose:
        print("  [ORCH] Building context...")
    context_messages, token_updates = build_search_context(
        state=state,
        prompt=prompt,
        config=config
    )

    if verbose:
        print(f"  [ORCH] Context built: {len(context_messages)} messages, {token_updates['iteration_tokens'][-1]} tokens")

    # ============================================
    # 3. GET STRUCTURED OUTPUT FROM LLM
    # ============================================
    result_schema = strategy.get_orchestrator_result_schema()

    client = AsyncOpenAI()
    _completion = await client.chat.completions.parse(
        model="gpt-4o",
        messages=context_messages,
        response_format=result_schema,
        temperature=0,
    )
    next_action: NextAction = _completion.choices[0].message.parsed.action

    # ============================================
    # 4. LOG DECISION
    # ============================================
    if verbose:
        print(f"\n[ORCHESTRATOR] Iteration {state.iteration}")
        print(f"  Action: {next_action.action_type}")
        print(f"  Reasoning: {next_action.reasoning[:100]}...")

    if isinstance(next_action, SearchAction):
        if verbose:
            print(f"  Searches planned: {len(next_action.searches)}")
        for i, search in enumerate(next_action.searches, 1):
            if verbose:
                print(f"    {i}. Task {search.task_id}: {search.search_description[:60]}...")

    # ============================================
    # 5. FORMAT DECISION AS MESSAGE
    # ============================================
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
            "full_action": next_action.model_dump()
        }
    }

    # ============================================
    # 6. RETURN STATE UPDATES
    # ============================================
    return {
        "next_action": next_action,
        "latest_reasoning": next_action.reasoning,
        "search_trace": state.search_trace + [decision_msg],
        "system_warning": False,
        **token_updates
    }
