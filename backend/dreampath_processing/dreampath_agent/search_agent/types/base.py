"""Base types for the search agent strategy pattern.

These are domain-agnostic base classes that concrete domains
(courses, activities) extend with their specific fields.
"""

from pydantic import BaseModel, Field


class SearchParams(BaseModel):
    """Base search parameters shared across all domains."""
    query: str | None = Field(default=None, description="Semantic/keyword query")
    alpha: float | None = Field(default=0.5, description="Hybrid search weight (0=keyword, 1=semantic)")
    limit: int | None = Field(default=10, description="Maximum number of results to return")


class SearchResult(BaseModel):
    """Base search result shared across all domains.

    Subclasses add domain-specific fields and use model_validator
    to map their canonical ID/title fields to id/title.
    """
    id: str = Field(description="Canonical identifier (course_code, activity_slug, etc.)")
    title: str = Field(description="Display name (course_title, display_name, etc.)")
    description: str = Field(default="", description="Description or summary text")


class SearchOutput(BaseModel):
    """Base search output container."""
    results: list[SearchResult] = Field(default_factory=list)
