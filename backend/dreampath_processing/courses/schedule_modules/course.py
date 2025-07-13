from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

class CourseType(Enum):
    MAJOR = "major"
    COMPLEMENTARY = "complementary"

# Make enum values directly accessible
MAJOR = CourseType.MAJOR
COMPLEMENTARY = CourseType.COMPLEMENTARY

@dataclass
class Course:
    course_code: str
    course_type: CourseType
    is_prereq: bool = False
    scheduled: bool = False
    prereq_tree: Optional[dict] = None
    must_have_window: Optional[Tuple[int, int]] = None
    term_idx: Optional[int] = None
    term_idx_in_term: Optional[int] = None
    course_name: Optional[str] = None
    course_description: Optional[str] = None

    def __str__(self):
        return f"{self.course_code} [{self.course_type}, scheduled={self.scheduled}, window={self.must_have_window}]"
