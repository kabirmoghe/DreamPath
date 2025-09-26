from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from dreampath_processing.courses.schedule_modules.course_path import CoursePath

@dataclass
class StudentProfile:
    name: str
    major: str
    college_interests: str
    post_grad_goals: str
    career_goals: str
    course_path: CoursePath
    minors: Optional[List[str]] = None
    clubs: Optional[List[str]] = None
    career: Optional[List[str]] = None

    # def __post_init__(self):
    #     if not isinstance(self.major, str):
    #         raise ValueError("major must be a string")
    #     if not isinstance(self.minors, list):
    #         raise ValueError("minors must be a list")
    #     if not isinstance(self.course_path, CoursePath):
    #         raise ValueError("course_path must be a CoursePath")
    #     if not isinstance(self.clubs, list):
    #         raise ValueError("clubs must be a list")
    #     if not isinstance(self.career, list):
    #         raise ValueError("career must be a list")

    def __str__(self):
        return f"""
Name: {self.name}
Major: {self.major}
College Interests: "{self.college_interests}"
Post-Grad Goals: "{self.post_grad_goals}"
Career Goals: "{self.career_goals}"
"""