# Context building templates

MASTER_CONTEXT = """
# DreamPath Context (current state)
{dreampath_context_block}

# Thread (what's happened before this turn)
{thread_block}

# Current Turn Trace (what's happened this turn)
{turn_block}
"""

MASTER_CONTEXT_SHORT = """
# DreamPath Context (current state)
{dreampath_context_block}

# Current Turn Trace (what's happened this turn)
{turn_block}

# Task
{task}
"""

SUMMARY_SYS_PROMPT = """
You are a helpful assistant that summarizes conversation history between a student (user) and a college advising agent.

# Instructions:
You are given a summary of the conversation so far and a list of new messages.

Your job is to generate an updated summary of the conversation so far including the new messages. 
Keep the summary objective and at or below 1200 characters. Pay particular attention to course codes if found in the new messages.

## Rules
- Describe the changes made, key brainstorming decisions, and any important student sentiment
- Never ask questions or add new questions
- If the conversation ends with an unanswered question to the student, preserve that exact question
- If the conversation ends with an imperative statement request to the student, always include that exact request in the summary

Return this string summary only.
"""

