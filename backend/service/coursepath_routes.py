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
    course_title: Optional[str] = None
    course_description: Optional[str] = None


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


def course_to_dict(course: Course) -> Dict[str, Any]:
    """Convert Course object to dictionary for API response."""
    return {
        "course_code": course.course_code,
        "course_type": course.course_type.value,  # Convert enum to string
        "is_prereq": course.is_prereq,
        "scheduled": course.scheduled,
        "prereq_tree": course.prereq_tree,
        "must_have_window": course.must_have_window,
        "term_idx": course.term_idx,
        "term_idx_in_term": course.term_idx_in_term,
        "course_title": course.course_title,
        "course_description": course.course_description,
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
        # Convert user_id to int for database query
        user_id_int = int(user_id) if user_id.isdigit() else None
        if user_id_int is None:
            # Try as UUID (for Supabase users)
            # For now, use user_id as string
            user_id_int = user_id

        # Load course path from database
        course_path = await student_db_service.load_course_path(user_id_int)

        if not course_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course path not found. Build your path first using the chat assistant."
            )

        # Get student profile for major
        student_profile = await student_db_service.load_student_profile(user_id_int)
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
        # Convert user_id
        user_id_int = int(user_id) if user_id.isdigit() else user_id

        course_path = await student_db_service.load_course_path(user_id_int)

        if not course_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course path not found"
            )

        # Get student profile for major
        student_profile = await student_db_service.load_student_profile(user_id_int)
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
