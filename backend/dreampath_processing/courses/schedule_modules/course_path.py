from dataclasses import dataclass, field
from typing import List, Set, Dict
from .course import Course

@dataclass
class CoursePath:
    course_path: List[List[str]]
    recommended_courses: Set[str]
    course_bank: Dict[str, Course]
    prereq_graph: Dict[str, List[str]]
    curr_window_start: int = 0
    must_have_courses: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Validate the data after initialization"""
        if not isinstance(self.course_path, list):
            raise ValueError("course_path must be a list")
        if not isinstance(self.curr_window_start, int): 
            raise ValueError("curr_window_start must be an int" )
        if not isinstance(self.recommended_courses, set):
            raise ValueError("recommended_courses must be a set")
        if not isinstance(self.course_bank, dict):
            raise ValueError("course_bank must be a dict")
        if not isinstance(self.prereq_graph, dict):
            raise ValueError("prereq_graph must be a dict")
        if not isinstance(self.must_have_courses, set):
            raise ValueError("must_have_courses must be a set")