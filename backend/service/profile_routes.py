"""
Profile API Endpoints

These endpoints handle user profile operations in your local PostgreSQL database.
User authentication is verified via Supabase JWT tokens.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from core.supabase_auth import get_current_user_id_optional
from dreampath_processing.database.student_service import StudentDatabaseService
from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.modules.student_profile import StudentProfile

router = APIRouter(prefix="/profile", tags=["profile"])

# Global database service (initialized in service.py lifespan)
# You can also inject it as a dependency
db_connection = get_db_connection()
student_db_service = StudentDatabaseService(db_connection)


class ProfileInitializeRequest(BaseModel):
    """Request to initialize a new user profile"""
    user_id: str  # Supabase user.id
    email: str
    name: str


class ProfileCreateRequest(BaseModel):
    """Request to create a complete user profile (from onboarding)"""
    user_id: str
    name: str
    major: str
    college_interests: str
    post_grad_goals: str
    career_goals: str
    minors: Optional[list[str]] = None
    clubs: Optional[list[str]] = None
    career: Optional[list[str]] = None


class ProfileUpdateRequest(BaseModel):
    """Request to update user profile"""
    major: Optional[str] = None
    college_interests: Optional[str] = None
    post_grad_goal: Optional[str] = None
    career_goals: Optional[str] = None
    minors: Optional[list[str]] = None


class ProfileResponse(BaseModel):
    """Profile response"""
    user_id: str
    name: str
    email: Optional[str] = None
    major: str
    minors: Optional[list[str]] = None
    college_interests: str
    post_grad_goal: str
    career_goals: str
    clubs: Optional[list[str]] = None
    career: Optional[list[str]] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_profile(request: ProfileCreateRequest):
    """
    Create a complete user profile from onboarding data.

    This is called after the user completes the onboarding wizard
    and is ready to initialize their course path.
    """
    try:
        # user_id is now a UUID string from Supabase
        # Create complete profile with onboarding data
        profile = StudentProfile(
            name=request.name,
            major=request.major,
            college_interests=request.college_interests,
            post_grad_goals=request.post_grad_goals,
            career_goals=request.career_goals,
            minors=request.minors or [],
            clubs=request.clubs or [],
            career=request.career or [],
        )

        # Save to database
        await student_db_service.save_student_profile(profile, request.user_id)

        return {
            "status": "success",
            "message": "Profile created successfully",
            "user_id": request.user_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create profile: {str(e)}"
        )


@router.post("/initialize", status_code=status.HTTP_201_CREATED)
async def initialize_profile(request: ProfileInitializeRequest):
    """
    Initialize a new user profile in local PostgreSQL.

    This is called after a user signs up via Supabase.
    It creates the initial profile record linked to the Supabase user.id.

    Note: This endpoint doesn't require authentication since it's called
    during signup before the user has a valid session.
    """
    try:
        # Create initial profile with minimal data
        initial_profile = StudentProfile(
            name=request.name,
            major="Undeclared",  # User will update this later
            college_interests="",
            post_grad_goals="",
            career_goals="",
        )

        # Save to database
        await student_db_service.save_student_profile(
            profile=initial_profile,
            user_id=request.user_id  # Use Supabase user.id
        )

        return {
            "status": "success",
            "message": "Profile initialized",
            "user_id": request.user_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize profile: {str(e)}"
        )


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: str,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional)
):
    """
    Get user profile from local PostgreSQL.

    The user_id in the path should match the authenticated user's ID
    (from Supabase JWT token) for security.
    In dev mode, authentication is optional.
    """


    print(f"🔍 Profile: Getting profile for user_id: {user_id}, authenticated_user_id: {authenticated_user_id}")
    # Security: Ensure user can only access their own profile (enforced in production)
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own profile"
        )

    try:
        # user_id is now a UUID string from Supabase
        profile = await student_db_service.load_student_profile(user_id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        return ProfileResponse(
            user_id=user_id,
            name=profile.name,
            major=profile.major,
            minors=profile.minors,
            college_interests=profile.college_interests,
            post_grad_goal=profile.post_grad_goals,  # Note: different field name
            career_goals=profile.career_goals,
            clubs=profile.clubs,
            career=profile.career,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )


@router.put("/{user_id}", response_model=ProfileResponse)
async def update_profile(
    user_id: str,
    request: ProfileUpdateRequest,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional)
):
    """
    Update user profile in local PostgreSQL.

    The user_id in the path should match the authenticated user's ID
    for security. In dev mode, authentication is optional.
    """
    # Security: Ensure user can only update their own profile (enforced in production)
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )

    try:
        # user_id is now a UUID string from Supabase
        # Load existing profile
        profile = await student_db_service.load_student_profile(user_id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )

        # Update fields if provided
        if request.major is not None:
            profile.major = request.major
        if request.college_interests is not None:
            profile.college_interests = request.college_interests
        if request.post_grad_goal is not None:
            profile.post_grad_goals = request.post_grad_goal
        if request.career_goals is not None:
            profile.career_goals = request.career_goals
        if request.minors is not None:
            profile.minors = request.minors

        # Save updated profile
        await student_db_service.save_student_profile(profile, user_id)

        return ProfileResponse(
            user_id=user_id,
            name=profile.name,
            major=profile.major,
            minors=profile.minors,
            college_interests=profile.college_interests,
            post_grad_goal=profile.post_grad_goals,
            career_goals=profile.career_goals,
            clubs=profile.clubs,
            career=profile.career,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    user_id: str,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional)
):
    """
    Delete user profile from local PostgreSQL.

    Note: This doesn't delete the Supabase auth.users record.
    You may want to implement cascade deletion or handle this differently.
    """
    # Security: Ensure user can only delete their own profile (enforced in production)
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own profile"
        )

    try:
        # TODO: Implement delete in StudentDatabaseService
        # await student_db_service.delete_student_profile(user_id)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Profile deletion not yet implemented"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile: {str(e)}"
        )
