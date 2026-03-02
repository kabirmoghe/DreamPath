"""Tool input schemas for the orchestrator's tool-calling interface.

Each model defines the structured input for one tool. Every model has a required
`reason` field (max 200 chars) for logging/status. Other fields are domain-specific.
"""

from pydantic import BaseModel, Field


class CourseSearchInput(BaseModel):
    """Search for courses matching a goal."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    goal: str  # freeform search goal for the search agent


class CareerSearchInput(BaseModel):
    """Retrieve career role data."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    query: str  # what the student wants to know about careers


class PlanBuilderInput(BaseModel):
    """Create CoursePath operations (add, remove, move, swap)."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    instructions: str  # what operations to create


class CoursePathInput(BaseModel):
    """Execute pending CoursePath operations from the worklist."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")


class ModifyProfileInput(BaseModel):
    """Modify student profile fields. Requires user confirmation."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    instructions: str  # what to modify


class RebuildCoursePathInput(BaseModel):
    """Rebuild entire CoursePath. For major upheavals only."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
    instructions: str  # rebuild goal


class RespondInput(BaseModel):
    """Send a reply to the student. For conversation, summarizing results, clarifying intent."""

    reason: str = Field(description="Concise justification for this tool call (max ~200 chars)")
