"""Activity search client for Weaviate hybrid search.

ActivitySearchClient wraps WeaviateActivityService with typed params/results.
Mirrors CourseSearchClient pattern.
"""

from typing import Any

from dreampath_processing.dreampath_agent.search_agent.types.activity_types import (
    ActivitySearchOutput,
    ActivitySearchParams,
    ActivitySearchResult,
)
from dreampath_processing.weaviate.activity_service import get_weaviate_activity_service

# All properties to return from Activity collection
_RETURN_PROPS = [
    # Vectorized prose
    "display_name",
    "mission_synth",
    "what_you_do_synth",
    "who_its_for_synth",
    # Vectorized arrays
    "subtags",
    "skills_exposed",
    "career_alignment",
    # Filterable
    "activity_slug",
    "activity_type",
    "domain",
    "selectivity_est",
    "time_commitment_est",
    "owner_type",
    "campus_affiliation",
    "data_confidence",
    # Display-only
    "short_name",
    "how_to_join_synth",
    "source_of_truth_url",
    "roles_exposed",
    "official_urls",
    "evidence_citations",
]


class ActivitySearchClient:
    """Activity search client using WeaviateActivityService singleton."""

    def __init__(self):
        self.service = get_weaviate_activity_service()

    def close(self):
        # Singleton manages its own lifecycle
        pass

    def hybrid_search(
        self,
        query: str | None = None,
        alpha: float | None = None,
        activity_type: str | None = None,
        domain: str | None = None,
        selectivity_est: str | None = None,
        time_commitment_est: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search on the Activity collection.

        Args:
            query: Search query string
            alpha: Hybrid search balance (0=keyword, 1=vector)
            activity_type: Filter by activity type
            domain: Filter by domain
            selectivity_est: Filter by selectivity level
            time_commitment_est: Filter by time commitment
            limit: Maximum results to return

        Returns:
            List of activity dictionaries
        """
        flt = self.service._build_filters(
            activity_type=activity_type,
            domain=domain,
            selectivity_est=selectivity_est,
            time_commitment_est=time_commitment_est,
        )

        if not query or query.strip() == "":
            # No query — fetch with filters only
            res = self.service.activity_collection.query.fetch_objects(
                filters=flt,
                limit=min(limit, 25),
                return_properties=_RETURN_PROPS,
            )
        else:
            # Hybrid search (semantic + keyword)
            kwargs = dict(
                query=query,
                alpha=alpha,
                filters=flt,
                limit=limit,
                return_properties=_RETURN_PROPS,
            )
            res = self.service.activity_collection.query.hybrid(**kwargs)

        return [o.properties for o in res.objects]

    def structured_hybrid_search(self, params: ActivitySearchParams) -> ActivitySearchOutput:
        """Perform structured hybrid search using ActivitySearchParams.

        Returns:
            ActivitySearchOutput with structured results
        """
        raw_results = self.hybrid_search(
            query=params.query,
            alpha=params.alpha,
            # activity_type=params.activity_type, # currently not used due to QG over-constraining filters
            domain=params.domain,
            selectivity_est=params.selectivity_est,
            time_commitment_est=params.time_commitment_est,
            limit=params.limit,
        )

        results = []
        for result in raw_results:
            try:
                activity_result = ActivitySearchResult(
                    activity_slug=result.get("activity_slug", ""),
                    display_name=result.get("display_name", ""),
                    mission_synth=result.get("mission_synth", ""),
                    activity_type=result.get("activity_type", ""),
                    domain=result.get("domain", ""),
                    selectivity_est=result.get("selectivity_est", ""),
                    time_commitment_est=result.get("time_commitment_est", ""),
                    owner_type=result.get("owner_type", ""),
                    skills_exposed=result.get("skills_exposed") or [],
                    career_alignment=result.get("career_alignment") or [],
                    subtags=result.get("subtags") or [],
                    who_its_for_synth=result.get("who_its_for_synth", ""),
                    what_you_do_synth=result.get("what_you_do_synth", ""),
                    how_to_join_synth=result.get("how_to_join_synth", ""),
                    data_confidence=result.get("data_confidence", ""),
                    evidence_citations=result.get("evidence_citations", ""),
                    source_of_truth_url=result.get("source_of_truth_url", ""),
                )
                results.append(activity_result)
            except Exception as e:
                print(f"Error creating ActivitySearchResult: {e}")
                continue

        return ActivitySearchOutput(results=results)


if __name__ == "__main__":
    client = ActivitySearchClient()

    try:
        print("Testing hybrid search...")
        results = client.hybrid_search(query="machine learning AI", limit=5, alpha=0.7)
        print(f"Found {len(results)} results")
        for r in results[:3]:
            print(f"  - {r.get('activity_slug')}: {r.get('display_name')}")

        print("\nTesting structured search...")
        params = ActivitySearchParams(
            query="software engineering",
            domain="tech_product",
            limit=5,
            alpha=0.7,
        )
        output = client.structured_hybrid_search(params)
        print(f"Structured search found {len(output.results)} results")
        for r in output.results[:3]:
            print(f"  - {r.activity_slug}: {r.display_name} ({r.domain})")

    except Exception as e:
        print(f"Error in testing: {e}")
    finally:
        client.close()
