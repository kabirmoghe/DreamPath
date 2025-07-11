from dataclasses import dataclass, field
from typing import List, Set, Dict
import copy

@dataclass
class CoursePath:
    course_path: List[List[str]]
    recommended_major_courses: Set[str]
    all_major_courses: Set[str]
    recommended_complementary_courses: Set[str]
    all_complementary_courses: Set[str]
    scheduled_courses: Set[str]
    unscheduled_courses: Set[str]
    prereq_graph: Dict[str, List[str]]
    
    def __post_init__(self):
        """Validate the data after initialization"""
        if not isinstance(self.course_path, list):
            raise ValueError("course_path must be a list")
        if not isinstance(self.recommended_major_courses, set):
            raise ValueError("recommended_major_courses must be a set")
        if not isinstance(self.all_major_courses, set):
            raise ValueError("all_major_courses must be a set")
        if not isinstance(self.recommended_complementary_courses, set):
            raise ValueError("recommended_complementary_courses must be a set")
        if not isinstance(self.all_complementary_courses, set):
            raise ValueError("all_complementary_courses must be a set")
        if not isinstance(self.scheduled_courses, set):
            raise ValueError("scheduled_courses must be a set")
        if not isinstance(self.unscheduled_courses, set):
            raise ValueError("unscheduled_courses must be a set")
        if not isinstance(self.prereq_graph, dict):
            raise ValueError("prereq_graph must be a dict")