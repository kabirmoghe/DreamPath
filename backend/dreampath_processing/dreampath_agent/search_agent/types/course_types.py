"""Course-specific search types.

CourseSearchParams extends SearchParams with course-specific filters.
CourseSearchResult extends SearchResult with course-specific fields.
CourseSearchOutput extends SearchOutput with typed results.

Enums (ValidDepartment, ValidDifficulty, ValidValue) are defined here
as they are course-domain concepts.
"""

from typing import Literal

from dreampath_processing.dreampath_agent.search_agent.types.base import (
    SearchOutput,
    SearchParams,
    SearchResult,
)
from pydantic import Field, model_validator

# Valid Dartmouth departments (from course catalog)
ValidDepartment = Literal[
    "African and African American Studies",
    "Anthropology",
    "Art History",
    "Asian Societies, Cultures, and Languages",
    "Biological Sciences",
    "Chemistry",
    "Classics",
    "Cognitive Science",
    "College Courses",
    "Comparative Literature",
    "Computer Science",
    "Divisional Courses",
    "Earth Sciences",
    "East European, Eurasian, and Russian Studies",
    "Economics",
    "Education",
    "Engineering Sciences",
    "English and Creative Writing",
    "Environmental Studies Program",
    "Film and Media Studies",
    "French and Italian Languages and Literatures",
    "Geography",
    "German Studies",
    "Government",
    "History",
    "Humanities",
    "Institute for Writing and Rhetoric",
    "Jewish Studies",
    "Latin American Latino and Caribbean Studies",
    "Linguistics",
    "Mathematics",
    "Middle Eastern Studies",
    "Music",
    "Native American and Indigenous Studies",
    "Philosophy",
    "Physics and Astronomy",
    "Psychological and Brain Sciences",
    "Quantitative Social Science",
    "Religion",
    "Sociology",
    "Spanish and Portuguese Languages and Literatures",
    "Speech",
    "Studio Art",
    "The John Sloan Dickey Center For International Understanding",
    "The Nelson A Rockefeller Center for Public Policy",
    "Theater",
    "Tuck Undergraduate",
    "Womens, Gender, and Sexuality Studies Program",
]

# Valid difficulty classifications (from review data)
ValidDifficulty = Literal["Low", "Medium", "High"]

# Valid learning value classifications (from review data)
ValidValue = Literal["Low", "Medium", "High"]


class CourseSearchParams(SearchParams):
    """Rich course search parameters with course-specific filters.

    Extends base SearchParams with department, difficulty, value filters, etc.
    """
    # Filters - Department & Course
    department: ValidDepartment | None = Field(default=None, description="The department to filter by")
    course_code: str | None = Field(default=None, description="Specific course code to search for")

    # Filters - Prerequisites
    max_num_prereqs: int | None = Field(default=None, description="Maximum number of prerequisites")

    # Filters - Difficulty
    difficulty_classification: ValidDifficulty | None = Field(default=None, description="Difficulty level filter")

    # Filters - Learning Value
    value_classification: ValidValue | None = Field(default=None, description="Learning value classification filter")

    # Modifiers
    sort_by_level: bool | None = Field(default=False, description="Whether to sort results by course level number")


class CourseSearchResult(SearchResult):
    """Course search result with all relevant fields.

    The base `id` field maps to `course_code` and `title` maps to `course_title`.
    """
    department: str
    course_code: str
    course_title: str
    prerequisites: str = ""
    course_url: str = ""
    num_prereqs: int = 0
    total_reviews: int | None = None
    global_difficulty_percentile: float | None = None
    global_difficulty_classification: str | None = None
    dept_difficulty_percentile: float | None = None
    dept_difficulty_classification: str | None = None
    difficulty_blurb: str | None = None
    global_value_percentile: float | None = None
    global_value_classification: str | None = None
    dept_value_percentile: float | None = None
    dept_value_classification: str | None = None
    learning_value_blurb: str | None = None
    target_audience_blurb: str | None = None

    @model_validator(mode="before")
    @classmethod
    def map_base_fields(cls, data):
        """Map course_code -> id and course_title -> title for base class."""
        if isinstance(data, dict):
            if "id" not in data and "course_code" in data:
                data["id"] = data["course_code"]
            if "title" not in data and "course_title" in data:
                data["title"] = data["course_title"]
            if "description" not in data:
                data["description"] = data.get("description", "")
        return data


class CourseSearchOutput(SearchOutput):
    """Course search output with typed results."""
    results: list[CourseSearchResult] = Field(default_factory=list)
