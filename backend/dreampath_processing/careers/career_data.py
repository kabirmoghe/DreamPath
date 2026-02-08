"""
Career data loader with caching and keyword matching.

Loads hardcoded career data from JSON files. This is temporary demo-ware
simulating future deep-research-agent output. DB tables are defined
(see database/schema/career_tables.sql) but not yet applied.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def get_swe_data() -> dict:
    """Load and cache the full SWE career family data."""
    with open(_DATA_DIR / "swe_roles.json") as f:
        return json.load(f)


def get_role_by_slug(slug: str) -> dict | None:
    """Get a single role by its slug (e.g., 'full-stack', 'backend')."""
    data = get_swe_data()
    for role in data["roles"]:
        if role["slug"] == slug:
            return role
    return None


def get_all_role_slugs() -> list[str]:
    """Return all available role slugs."""
    data = get_swe_data()
    return [role["slug"] for role in data["roles"]]


# Family-level keywords that match the SWE family broadly
_FAMILY_KEYWORDS = [
    "swe", "software engineering", "software engineer", "software development",
    "software developer", "software career", "tech career", "engineering career",
    "coding career", "programming career", "developer career",
]


def match_query_to_roles(query: str) -> list[dict]:
    """
    Match a query string to career roles using keyword matching.

    Returns a list of matched role dicts. If the query matches the SWE
    family broadly (e.g., "software engineering careers"), all roles are
    returned. If it matches a specific role's keywords (e.g., "backend
    engineer"), only that role is returned.

    Args:
        query: The search query from the user/orchestrator handoff.

    Returns:
        List of matched role dicts (may be empty if no match).
    """
    q = query.lower()
    data = get_swe_data()
    roles = data["roles"]

    # Check for family-level match first
    if any(kw in q for kw in _FAMILY_KEYWORDS):
        return list(roles)

    # Check individual role matches
    matched = []
    for role in roles:
        role_keywords = role.get("keywords", [])
        if any(kw in q for kw in role_keywords):
            matched.append(role)

    return matched
