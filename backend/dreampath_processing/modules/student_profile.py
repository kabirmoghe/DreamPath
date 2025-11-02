from dataclasses import dataclass
from typing import List, Optional

@dataclass
class StudentProfile:
    # Student information
    name: str
    major: str
    college_interests: str
    post_grad_goals: str
    career_goals: str
    
    # Optional data
    minors: Optional[List[str]] = None
    clubs: Optional[List[str]] = None
    career: Optional[List[str]] = None
    
    # Profile metadata
    profile_name: Optional[str] = None  # e.g., "Fall 2024 Plan", "CS Track"

    def __str__(self):
        return f"""
Profile Name: {self.profile_name if self.profile_name else "<profile name>"}
Name: {self.name}
Major: {self.major}
College Interests: "{self.college_interests}"
Post-Grad Goals: "{self.post_grad_goals}"
Career Goals: "{self.career_goals}"
"""