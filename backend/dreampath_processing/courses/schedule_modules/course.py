from dataclasses import dataclass
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
    prereq_tree: dict | None = None
    must_have_window: list[int] | None = None
    term_idx: int | None = None
    term_idx_in_term: int | None = None

    # DreamPath-specific
    aligned_parameters: set | None = None  # set of "interests", "post_grad", "career"

    # Basic course info (from Weaviate)
    course_title: str | None = None
    course_description: str | None = None
    department: str | None = None
    prerequisites: str | None = None
    course_url: str | None = None
    num_prereqs: int | None = None
    total_reviews: int | None = None

    # Difficulty metrics (from Weaviate)
    global_difficulty_percentile: float | None = None
    global_difficulty_classification: str | None = None
    dept_difficulty_percentile: float | None = None
    dept_difficulty_classification: str | None = None
    difficulty_blurb: str | None = None

    # Value metrics (from Weaviate)
    global_value_percentile: float | None = None
    global_value_classification: str | None = None
    dept_value_percentile: float | None = None
    dept_value_classification: str | None = None
    learning_value_blurb: str | None = None

    # Target audience (from Weaviate)
    target_audience_blurb: str | None = None

    def __str__(self):
        course_str = f"{self.course_code} [{self.course_type}, scheduled={self.scheduled}{', PREREQ' if self.is_prereq else ''}]"
        if self.must_have_window:
            course_str += f"\n\twindow={self.must_have_window}"
        if self.term_idx is not None:
            course_str += f"\n\tterm_idx={self.term_idx}"
        if self.aligned_parameters:
            course_str += f"\n\taligned={self.aligned_parameters}"

        return course_str
