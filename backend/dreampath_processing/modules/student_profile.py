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
    course_path: Optional[CoursePath] = None
    minors: Optional[List[str]] = None
    clubs: Optional[List[str]] = None
    career: Optional[List[str]] = None

    def __str__(self):
        return f"""
Name: {self.name}
Major: {self.major}
College Interests: "{self.college_interests}"
Post-Grad Goals: "{self.post_grad_goals}"
Career Goals: "{self.career_goals}"
"""