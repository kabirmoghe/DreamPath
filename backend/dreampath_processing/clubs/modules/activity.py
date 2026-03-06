from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Activity:
    # Required fields (no defaults) — must come first
    activity_slug: str
    display_name: str

    # Optional fields with defaults
    aligned_parameters: set | None = None  # set of "interests", "post_grad", "career"
    membership_status: Literal['not_yet_joined', 'joining', 'active_member', 'inactive_member', 'left'] = "not_yet_joined"
    current_role: str | None = None

    # Basic Activity Metadata (Weaviate)
    mission_synth: str = ""
    activity_type: str = ""
    domain: str = ""
    selectivity_est: str = ""
    time_commitment_est: str = ""
    owner_type: str = ""

    # Activity Details (Weaviate)
    skills_exposed: list[str] = field(default_factory=list)
    career_alignment: list[str] = field(default_factory=list)
    subtags: list[str] = field(default_factory=list)
    who_its_for_synth: str = ""
    what_you_do_synth: str = ""
    how_to_join_synth: str = ""
    data_confidence: str = ""
    evidence_citations: str = ""
    roles_exposed: list[str] = field(default_factory=list)
