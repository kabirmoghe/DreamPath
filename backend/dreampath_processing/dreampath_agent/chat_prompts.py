"""
Legacy re-exports for backwards compatibility.
All prompts have moved to dreampath_agent/nodes/prompts/.
"""

from dreampath_processing.dreampath_agent.nodes.prompts import (
    BUILD_OPERATIONS_SYS,
    COURSE_SEARCH_SYS,
    CRAFT_FINAL_REPLY_SYS,
    DETERMINE_USER_CONFIRMATION_SYS,
    # Context templates
    MASTER_CONTEXT,
    MASTER_CONTEXT_SHORT,
    MODIFY_PROFILE_SYS,
    # Node prompts
    ORCHESTRATOR_DECISION_SYS,
    SUMMARY_SYS_PROMPT,
)

__all__ = [
    # Context templates
    "MASTER_CONTEXT",
    "MASTER_CONTEXT_SHORT",
    "SUMMARY_SYS_PROMPT",
    "DETERMINE_USER_CONFIRMATION_SYS",
    # Node prompts
    "ORCHESTRATOR_DECISION_SYS",
    "BUILD_OPERATIONS_SYS",
    "COURSE_SEARCH_SYS",
    "MODIFY_PROFILE_SYS",
    "CRAFT_FINAL_REPLY_SYS",
]
