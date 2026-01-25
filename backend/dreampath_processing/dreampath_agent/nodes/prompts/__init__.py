# DreamPath Agent Prompts
# Organized by node for maintainability

from .context import (
    DETERMINE_USER_CONFIRMATION_SYS,
    MASTER_CONTEXT,
    MASTER_CONTEXT_SHORT,
    SUMMARY_SYS_PROMPT,
)
from .course_search import COURSE_SEARCH_SYS
from .finalize import CRAFT_FINAL_REPLY_SYS
from .modify_profile import MODIFY_PROFILE_SYS
from .orchestrator import ORCHESTRATOR_DECISION_SYS
from .plan_builder import BUILD_OPERATIONS_SYS
from .rebuild import PARAMETER_COURSE_SEARCH_QUERIES_SYS, UPDATE_COURSE_RECOMMENDATIONS_SYS

__all__ = [
    # Node prompts
    "ORCHESTRATOR_DECISION_SYS",
    "COURSE_SEARCH_SYS",
    "BUILD_OPERATIONS_SYS",
    "MODIFY_PROFILE_SYS",
    "PARAMETER_COURSE_SEARCH_QUERIES_SYS",
    "UPDATE_COURSE_RECOMMENDATIONS_SYS",
    "CRAFT_FINAL_REPLY_SYS",
    # Context templates
    "MASTER_CONTEXT",
    "MASTER_CONTEXT_SHORT",
    "SUMMARY_SYS_PROMPT",
    "DETERMINE_USER_CONFIRMATION_SYS",
]
