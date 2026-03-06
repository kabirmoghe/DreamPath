"""
Club Path API Endpoints

Returns the user's ClubPath (recommended activities) from PostgreSQL.
"""

from dataclasses import asdict
from typing import Optional

from core.supabase_auth import get_current_user_id_optional
from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.database.student_service import StudentDatabaseService
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/clubpath", tags=["clubpath"])

db_connection = get_db_connection()
student_db_service = StudentDatabaseService(db_connection)


class ActivityResponse(BaseModel):
    activity_slug: str
    display_name: str
    activity_type: str = ""
    domain: str = ""
    mission_synth: str = ""
    aligned_parameters: list[str] | None = None
    membership_status: str = "not_yet_joined"
    selectivity_est: str = ""
    time_commitment_est: str = ""
    owner_type: str = ""
    skills_exposed: list[str] | None = None
    career_alignment: list[str] | None = None
    subtags: list[str] | None = None
    who_its_for_synth: str = ""
    what_you_do_synth: str = ""
    how_to_join_synth: str = ""
    data_confidence: str = ""
    evidence_citations: str = ""
    current_role: str | None = None
    roles_exposed: list[str] | None = None


class ClubPathResponse(BaseModel):
    user_id: str
    activities: list[ActivityResponse]


@router.get("/{user_id}", response_model=ClubPathResponse)
async def get_club_path(
    user_id: str,
    authenticated_user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    if authenticated_user_id and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own club path",
        )

    try:
        club_path = await student_db_service.load_club_path(user_id)

        if not club_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Club path not found",
            )

        activities = []
        for slug, activity in club_path.recommendations.items():
            activities.append(ActivityResponse(
                activity_slug=activity.activity_slug,
                display_name=activity.display_name,
                activity_type=activity.activity_type,
                domain=activity.domain,
                mission_synth=activity.mission_synth,
                aligned_parameters=sorted(activity.aligned_parameters) if activity.aligned_parameters else None,
                membership_status=activity.membership_status or "not_yet_joined",
                selectivity_est=activity.selectivity_est,
                time_commitment_est=activity.time_commitment_est,
                owner_type=activity.owner_type,
                skills_exposed=activity.skills_exposed or None,
                career_alignment=activity.career_alignment or None,
                subtags=activity.subtags or None,
                who_its_for_synth=activity.who_its_for_synth,
                what_you_do_synth=activity.what_you_do_synth,
                how_to_join_synth=activity.how_to_join_synth,
                data_confidence=activity.data_confidence,
                evidence_citations=activity.evidence_citations,
                current_role=activity.current_role,
                roles_exposed=activity.roles_exposed or None,
            ))

        return ClubPathResponse(user_id=str(user_id), activities=activities)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error loading club path: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load club path: {str(e)}",
        )
