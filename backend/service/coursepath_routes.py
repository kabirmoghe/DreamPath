"""
Course Path API Endpoints

These endpoints handle course path operations from your local PostgreSQL database.
Returns data in the exact format that matches the Course dataclass.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from core.supabase_auth import get_current_user_id_optional, verify_supabase_token
from core import settings
from dreampath_processing.database.student_service import StudentDatabaseService
from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.courses.schedule_modules.course import Course

router = APIRouter(prefix="/coursepath", tags=["coursepath"])

# Database service
db_connection = get_db_connection()
student_db_service = StudentDatabaseService(db_connection)


class CourseData(BaseModel):
    """
    Course data matching the Course dataclass structure exactly.
    This is what gets stored in the course_bank within CoursePath.
    """
    course_code: str
    course_type: str  # "major" or "complementary"
    is_prereq: bool = False
    scheduled: bool = False
    prereq_tree: Optional[Dict[str, Any]] = None
    must_have_window: Optional[List[int]] = None
    term_idx: Optional[int] = None
    term_idx_in_term: Optional[int] = None
    # DreamPath-specific
    aligned_parameters: Optional[List[str]] = None
    # Basic course info
    course_title: Optional[str] = None
    course_description: Optional[str] = None
    department: Optional[str] = None
    prerequisites: Optional[str] = None
    course_url: Optional[str] = None
    num_prereqs: Optional[int] = None
    total_reviews: Optional[int] = None
    # Difficulty metrics
    global_difficulty_percentile: Optional[float] = None
    global_difficulty_classification: Optional[str] = None
    dept_difficulty_percentile: Optional[float] = None
    dept_difficulty_classification: Optional[str] = None
    difficulty_blurb: Optional[str] = None
    # Value metrics
    global_value_percentile: Optional[float] = None
    global_value_classification: Optional[str] = None
    dept_value_percentile: Optional[float] = None
    dept_value_classification: Optional[str] = None
    learning_value_blurb: Optional[str] = None
    # Target audience
    target_audience_blurb: Optional[str] = None


class CoursePathResponse(BaseModel):
    """Course path response matching CoursePath structure"""
    user_id: str
    major: str
    course_path: List[List[str]]  # List of terms, each containing course codes
    course_bank: Dict[str, CourseData]  # Full course objects by code
    curr_window_start: int
    recommended_courses: List[str]
    must_have_courses: List[str]
    lingering_courses: List[str]


class CoursePathVisualizationResponse(BaseModel):
    """Course path visualization as text"""
    user_id: str
    major: str
    visualization: str


import math

def _clean_nan(value):
    """Convert NaN values to None for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and value.lower() == 'nan':
        return None
    return value


def course_to_dict(course: Course) -> Dict[str, Any]:
    """Convert Course object to dictionary for API response."""
    return {
        # Required
        "course_code": course.course_code,
        "course_type": course.course_type.value,  # Convert enum to string
        # Scheduling state
        "is_prereq": course.is_prereq,
        "scheduled": course.scheduled,
        "prereq_tree": course.prereq_tree,
        "must_have_window": course.must_have_window,
        "term_idx": course.term_idx,
        "term_idx_in_term": course.term_idx_in_term,
        # DreamPath-specific
        "aligned_parameters": list(course.aligned_parameters) if course.aligned_parameters else None,
        # Basic course info
        "course_title": course.course_title,
        "course_description": course.course_description,
        "department": course.department,
        "prerequisites": _clean_nan(course.prerequisites),
        "course_url": course.course_url,
        "num_prereqs": course.num_prereqs,
        "total_reviews": course.total_reviews,
        # Difficulty metrics
        "global_difficulty_percentile": course.global_difficulty_percentile,
        "global_difficulty_classification": course.global_difficulty_classification,
        "dept_difficulty_percentile": course.dept_difficulty_percentile,
        "dept_difficulty_classification": course.dept_difficulty_classification,
        "difficulty_blurb": _clean_nan(course.difficulty_blurb),
        # Value metrics
        "global_value_percentile": course.global_value_percentile,
        "global_value_classification": course.global_value_classification,
        "dept_value_percentile": course.dept_value_percentile,
        "dept_value_classification": course.dept_value_classification,
        "learning_value_blurb": _clean_nan(course.learning_value_blurb),
        # Target audience
        "target_audience_blurb": _clean_nan(course.target_audience_blurb),
    }


@router.get("/{user_id}", response_model=CoursePathResponse)
async def get_course_path(
    user_id: str,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional)
):
    """
    Get user's course path from PostgreSQL.

    Returns the full course path with:
    - course_path: List of terms (each term is a list of course codes)
    - course_bank: Dict mapping course_code to full Course object
    - Other metadata (curr_window_start, recommended_courses, etc.)

    Security: User can only access their own course path (enforced in production).
    In dev mode, authentication is optional.
    """
    # Security: In production, ensure user can only access their own course path
    # In dev mode, authenticated_user_id might be None if auth is bypassed
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own course path"
        )

    try:
        # user_id is now a UUID string from Supabase
        # Load course path from database
        course_path = await student_db_service.load_course_path(user_id)

        if not course_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course path not found. Build your path first using the chat assistant."
            )

        # Get student profile for major
        student_profile = await student_db_service.load_student_profile(user_id)
        major = student_profile.major if student_profile else "Unknown"

        # Convert course_bank (Dict[str, Course]) to API format
        course_bank_dict = {
            course_code: CourseData(**course_to_dict(course))
            for course_code, course in course_path.course_bank.items()
        }

        return CoursePathResponse(
            user_id=str(user_id),
            major=major,
            course_path=course_path.course_path,  # List[List[str]]
            course_bank=course_bank_dict,
            curr_window_start=course_path.curr_window_start,
            recommended_courses=list(course_path.recommended_courses),
            must_have_courses=list(course_path.must_have_courses),
            lingering_courses=list(course_path.lingering_courses),
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error loading course path: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load course path: {str(e)}"
        )


@router.get("/{user_id}/visualization", response_model=CoursePathVisualizationResponse)
async def get_course_path_visualization(
    user_id: str,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional)
):
    """
    Get user's course path as a text visualization.

    Returns a formatted string showing the term-by-term breakdown.
    """
    # Security check (enforced in production)
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own course path"
        )

    try:
        # user_id is now a UUID string from Supabase
        course_path = await student_db_service.load_course_path(user_id)

        if not course_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course path not found"
            )

        # Get student profile for major
        student_profile = await student_db_service.load_student_profile(user_id)
        major = student_profile.major if student_profile else "Unknown"

        # Use the built-in visualization method
        visualization = course_path.visualize_by_term_idx()

        return CoursePathVisualizationResponse(
            user_id=str(user_id),
            major=major,
            visualization=visualization
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get visualization: {str(e)}"
        )


class UpdateCurrentTermRequest(BaseModel):
    """Request to update current term"""
    term_index: int


@router.patch("/{user_id}/current-term", status_code=status.HTTP_200_OK)
async def update_current_term(
    user_id: str,
    request: UpdateCurrentTermRequest,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional)
):
    """
    Update the current term (curr_window_start) for a user's course path.

    This allows users to mark which term they're currently in.
    """
    # Security check (enforced in production)
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own course path"
        )

    try:
        success = await student_db_service.update_current_term(user_id, request.term_index)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course path not found"
            )

        return {"message": "Current term updated", "curr_window_start": request.term_index}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating current term: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update current term: {str(e)}"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_path(
    user_id: str,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional)
):
    """
    Delete user's course path.

    This resets the course path so the user can build a new one.
    """
    # Security check (enforced in production)
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own course path"
        )

    try:
        # TODO: Implement delete in StudentDatabaseService
        # await student_db_service.delete_course_path(user_id)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Course path deletion not yet implemented"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete course path: {str(e)}"
        )
