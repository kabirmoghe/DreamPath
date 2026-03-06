from pydantic import BaseModel, Field
from typing import Literal

class ActivityModification(BaseModel):
    # Base params
    activity_slug: str
    type: Literal['add', 'remove', 'edit']

    # Params for add / edit
    aligned_parameters: set[Literal["interests", "post_grad", "career"]] | None = Field(default=None)  # set of "interests", "post_grad", "career"
    membership_status: Literal['not_yet_joined', 'joining', 'active_member', 'inactive_member', 'left'] | None = Field(default=None)
    current_role: str | None = Field(default=None)

class ClubPathModifications(BaseModel):
    modifications: list[ActivityModification]
    