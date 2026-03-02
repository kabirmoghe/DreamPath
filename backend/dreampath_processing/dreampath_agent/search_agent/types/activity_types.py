"""Activity-specific search types.

ActivitySearchParams extends SearchParams with activity-specific filters.
ActivitySearchResult extends SearchResult with activity-specific fields.
ActivitySearchOutput extends SearchOutput with typed results.

Enum literals (ValidActivityType, ValidDomain, etc.) are defined here
as they are activity-domain concepts.
"""

from typing import Literal

from dreampath_processing.dreampath_agent.search_agent.types.base import (
    SearchOutput,
    SearchParams,
    SearchResult,
)
from pydantic import Field, model_validator

# Valid activity types (from activities CSV)
ValidActivityType = Literal["club", "lab", "research_group"]

# Valid domains (from activities CSV)
ValidDomain = Literal[
    "consulting",
    "finance",
    "media",
    "policy",
    "research",
    "service",
    "sports",
    "tech_product",
]

# Valid selectivity levels (from activities CSV)
ValidSelectivity = Literal["application", "open", "selective", "tryout"]

# Valid time commitment levels (from activities CSV)
ValidTimeCommitment = Literal["high", "low", "low_medium", "medium", "medium_high", "seasonal"]


class ActivitySearchParams(SearchParams):
    """Activity search parameters with activity-specific filters.

    Extends base SearchParams with activity_type, domain, selectivity, and time commitment filters.
    """

    limit: int | None = Field(default=5, description="Maximum number of results to return")

    domain: ValidDomain | None = Field(
        default=None, description="Domain/field of the activity"
    )
    selectivity_est: ValidSelectivity | None = Field(
        default=None, description="Selectivity level: open, application, selective, or tryout"
    )
    time_commitment_est: ValidTimeCommitment | None = Field(
        default=None, description="Estimated time commitment level"
    )


class ActivitySearchResult(SearchResult):
    """Activity search result with all relevant fields.

    The base `id` field maps to `activity_slug` and `title` maps to `display_name`.
    """

    activity_slug: str
    display_name: str
    mission_synth: str = ""
    activity_type: str = ""
    domain: str = ""
    selectivity_est: str = ""
    time_commitment_est: str = ""
    owner_type: str = ""
    skills_exposed: list[str] = Field(default_factory=list)
    career_alignment: list[str] = Field(default_factory=list)
    subtags: list[str] = Field(default_factory=list)
    who_its_for_synth: str = ""
    what_you_do_synth: str = ""
    how_to_join_synth: str = ""
    data_confidence: str = ""
    evidence_citations: str = ""
    source_of_truth_url: str = ""

    @model_validator(mode="before")
    @classmethod
    def map_base_fields(cls, data):
        """Map activity_slug -> id and display_name -> title for base class."""
        if isinstance(data, dict):
            if "id" not in data and "activity_slug" in data:
                data["id"] = data["activity_slug"]
            if "title" not in data and "display_name" in data:
                data["title"] = data["display_name"]
            if "description" not in data:
                data["description"] = data.get("mission_synth", "")
        return data


class ActivitySearchOutput(SearchOutput):
    """Activity search output with typed results."""

    results: list[ActivitySearchResult] = Field(default_factory=list)
