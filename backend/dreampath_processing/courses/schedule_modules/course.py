from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

class CourseType(Enum):
    MAJOR = "major"
    COMPLEMENTARY = "complementary"
    
    def __str__(self):
        if self == CourseType.MAJOR:
            return "Major"
        elif self == CourseType.COMPLEMENTARY:
            return "Complementary"
        return self.value

# Make enum values directly accessible
MAJOR = CourseType.MAJOR
COMPLEMENTARY = CourseType.COMPLEMENTARY

@dataclass
class Course:
    # Required fields
    course_code: str
    course_type: CourseType

    # Scheduling state
    is_prereq: bool = False
    scheduled: bool = False
    prereq_tree: Optional[dict] = None
    must_have_window: Optional[List[int]] = None
    term_idx: Optional[int] = None
    term_idx_in_term: Optional[int] = None

    # DreamPath-specific
    aligned_parameters: Optional[set] = None  # set of "interests", "post_grad", "career"

    # Basic course info (from Weaviate)
    course_title: Optional[str] = None
    course_description: Optional[str] = None
    department: Optional[str] = None
    prerequisites: Optional[str] = None
    course_url: Optional[str] = None
    num_prereqs: Optional[int] = None
    total_reviews: Optional[int] = None

    # Difficulty metrics (from Weaviate)
    global_difficulty_percentile: Optional[float] = None
    global_difficulty_classification: Optional[str] = None
    dept_difficulty_percentile: Optional[float] = None
    dept_difficulty_classification: Optional[str] = None
    difficulty_blurb: Optional[str] = None

    # Value metrics (from Weaviate)
    global_value_percentile: Optional[float] = None
    global_value_classification: Optional[str] = None
    dept_value_percentile: Optional[float] = None
    dept_value_classification: Optional[str] = None
    learning_value_blurb: Optional[str] = None

    # Target audience (from Weaviate)
    target_audience_blurb: Optional[str] = None

    def __str__(self):
        course_str = f"{self.course_code} [{self.course_type}, scheduled={self.scheduled}{', PREREQ' if self.is_prereq else ''}]"
        if self.must_have_window:
            course_str += f"\n\twindow={self.must_have_window}"
        if self.term_idx is not None:
            course_str += f"\n\tterm_idx={self.term_idx}"
        if self.aligned_parameters:
            course_str += f"\n\taligned={self.aligned_parameters}"

        return course_str
