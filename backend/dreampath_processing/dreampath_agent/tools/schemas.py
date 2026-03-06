"""Tool input schemas for the orchestrator's tool-calling interface.

Each model defines the structured input for one tool. Every model has a required
`reason` field (max 200 chars) for logging/status. Other fields are domain-specific.
"""

from typing import Literal

from dreampath_processing.dreampath_agent.dreampath_types import ValidMajor
from pydantic import BaseModel, Field


class CourseSearchInput(BaseModel):
    """Search for courses matching goal(s)."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    goals: list[str]  # 1 for simple lookups, 2-3 for comprehensive coverage


class ActivitySearchInput(BaseModel):
    """Search for clubs/activities matching goal(s)."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    goals: list[str]


class CareerSearchInput(BaseModel):
    """Retrieve career role data."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    query: str  # what the student wants to know about careers


class CoursePathInput(BaseModel):
    """Execute CoursePath operations (add, remove, move, swap, replace)."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    operations: list[str]  # e.g. ["add COSC78 to term 5", "remove PSYC11"]


class ClubPathOperation(BaseModel):
    """A single ClubPath operation."""
    action: Literal["add", "remove", "edit"]
    activity_slug: str
    rank: int | None = Field(default=None, description="Target rank (1-indexed). For edit: repositions the activity.")
    membership_status: Literal["not_yet_joined", "joining", "active_member", "inactive_member", "left"] | None = Field(default=None, description="For edit: update the student's membership status.")
    current_role: str | None = Field(default=None, description="For edit: update the student's role at the activity.")


class ClubPathInput(BaseModel):
    """Execute ClubPath operations (add, remove, reorder)."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    operations: list[ClubPathOperation]


class ModifyProfileInput(BaseModel):
    """Modify student profile fields. Only include fields you want to change; omit unchanged fields (null)."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    major: ValidMajor | None = None
    college_interests: str | None = None
    post_grad_goals: str | None = None
    career_goals: str | None = None


class RespondInput(BaseModel):
    """Send a reply to the student. For conversation, summarizing results, clarifying intent."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")


class ChangeModeInput(BaseModel):
    """Switch between advise and build mode."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    target_mode: Literal["advise", "build"]
    instructions: str = Field(description="Guidance for the incoming mode — what to focus on, context from current conversation")


class CuratedCourse(BaseModel):
    """A course selected for the curated build plan."""
    course_code: str
    aligned_parameters: list[str]  # e.g. ["interests", "post_grad", "career"]


class CuratedActivity(BaseModel):
    """An activity selected for the curated build plan."""
    activity_slug: str
    aligned_parameters: list[str]


class CurateInput(BaseModel):
    """Curate course and activity recommendations for the build plan."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    courses: list[CuratedCourse]
    activities: list[CuratedActivity]
    coverage_rationale: str  # how courses + clubs together cover the student's needs


class BuildDreampathInput(BaseModel):
    """Build CoursePath + ClubPath from curated recommendations (deterministic)."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")


class CompletePhaseInput(BaseModel):
    """Mark current build phase complete and advance to the next."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    notes: str = Field(description="Summary of what was accomplished in this phase")


class PhaseGuidance(BaseModel):
    """Guidance for a single build phase."""
    phase: str
    guidance: str


class PlanBuildInput(BaseModel):
    """Set per-phase guidance for the build plan. Called once at the start of build mode."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    phase_guidance: list[PhaseGuidance]
