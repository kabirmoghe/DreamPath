# DreamPath Agent Prompts
# Organized by node for maintainability

from .club_path import CLUBPATH_MODIFICATIONS_SYSTEM
from .context import (
    DETERMINE_USER_CONFIRMATION_SYS,
    MASTER_CONTEXT,
    MASTER_CONTEXT_SHORT,
    SUMMARY_SYS_PROMPT,
)
from .course_search import COURSE_SEARCH_SYS
from .finalize import CRAFT_FINAL_REPLY_SYS
from .modify_profile import MODIFY_PROFILE_SYS
from .plan_builder import BUILD_OPERATIONS_SYS
from .rebuild import (
    COURSE_REC_SYNTHESIS_SYS,
    PARAMETER_COURSE_SEARCH_GOAL,
)

__all__ = [
    # Node prompts
    "COURSE_SEARCH_SYS",
    "BUILD_OPERATIONS_SYS",
    "MODIFY_PROFILE_SYS",
    "CLUBPATH_MODIFICATIONS_SYSTEM",
    "PARAMETER_COURSE_SEARCH_GOAL",
    "COURSE_REC_SYNTHESIS_SYS",
    "CRAFT_FINAL_REPLY_SYS",
    
    # Context templates
    "MASTER_CONTEXT",
    "MASTER_CONTEXT_SHORT",
    "SUMMARY_SYS_PROMPT",
    "DETERMINE_USER_CONFIRMATION_SYS",
]
