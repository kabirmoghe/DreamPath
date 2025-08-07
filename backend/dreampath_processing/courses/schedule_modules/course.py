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
        course_str = f"{self.course_code} [{self.course_type}, scheduled={self.scheduled}{', PREREQ' if self.is_prereq else ''}]"
        if self.must_have_window:
            course_str += f"\n\twindow={self.must_have_window}"
        if self.term_idx is not None:
            course_str += f"\n\tterm_idx={self.term_idx}"
 
        return course_str
