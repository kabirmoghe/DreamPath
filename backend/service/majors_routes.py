"""
Majors API Endpoints

These endpoints handle major-related operations, fetching data from Weaviate.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List

from dreampath_processing.weaviate.course_service import WeaviateCourseService

router = APIRouter(prefix="/majors", tags=["majors"])


class MajorResponse(BaseModel):
    """Major response model"""
    major: str
    department: str
    department_id: str


@router.get("", response_model=List[MajorResponse])
async def get_all_majors():
    """
    Get all majors from Weaviate.

    Returns a list of all available majors with their department information.
    """
    try:
        # Get Weaviate service instance
        weaviate_service = WeaviateCourseService()

        # Fetch all majors from the Major collection
        major_data = weaviate_service.major_collection.query.fetch_objects(
            limit=1000,  # Adjust if you have more than 1000 majors
            return_properties=["major", "department", "department_id"]
        )

        if not major_data.objects:
            return []

        # Convert to response format and sort alphabetically
        majors = [
            MajorResponse(
                major=obj.properties["major"],
                department=obj.properties["department"],
                department_id=str(obj.properties["department_id"])
            )
            for obj in major_data.objects
        ]

        # Sort by major name
        majors.sort(key=lambda x: x.major)

        return majors

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch majors: {str(e)}"
        )
