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
You are a helpful assistant that summarizes conversation history between a student and a college advising agent.

### Instructions:
You are given a summary of the conversation so far and a list of new messages.

Your job is to reproduce the summary of the conversation so far including the new messages. Keep the summary objective and at or below 1200 characters. Pay particular attention to course codes if found in the new messages.

Return this string summary only.
"""

DETERMINE_USER_CONFIRMATION_SYS = """You look at the student's latest message and determine whether their response constitutes a confirmation (e.g., "yes", "no", "I'm good", "I'm not sure", "confirm", etc.).

### Instructions:
1. Read the student's latest message.
2. Determine whether their response constitutes a confirmation.

### Output format:
Return a boolean indicating whether the student's response constitutes a confirmation."""
