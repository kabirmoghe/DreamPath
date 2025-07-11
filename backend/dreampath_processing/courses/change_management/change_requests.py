from enum import Enum
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass

class ChangeType(Enum):
    REMOVE = "remove"
    ADD = "add"
    SWAP = "swap"
    SHIFT = "shift"
    REPLACE = "replace"

@dataclass
class CourseReference:
    course_code: str
    term_idx: Optional[int] = None
    term_idx_in_term: Optional[int] = None

@dataclass
class SchedulingWindow:
    start_term: int
    end_term: int

@dataclass
class ChangeRequest:
    change_type: ChangeType
    target_courses: List[CourseReference]
    new_courses: List[CourseReference]
    scheduling_windows: List[SchedulingWindow]