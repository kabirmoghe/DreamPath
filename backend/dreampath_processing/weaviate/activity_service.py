"""Weaviate Activity service — singleton for the Activity collection."""

import os
import threading
import warnings

import weaviate
from weaviate.classes.query import Filter

# Suppress ResourceWarnings from Weaviate - singleton pattern keeps connections open intentionally
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed")


class WeaviateActivityService:
    """Singleton service for the Weaviate Activity collection.

    Thread-safe, mirrors WeaviateCourseService pattern.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            http_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
            http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
            http_secure = os.getenv("WEAVIATE_HTTP_SECURE", "false").lower() == "true"
            grpc_host = os.getenv("WEAVIATE_GRPC_HOST", "localhost")
            grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
            grpc_secure = os.getenv("WEAVIATE_GRPC_SECURE", "false").lower() == "true"

            self.client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=http_secure,
                grpc_host=grpc_host,
                grpc_port=grpc_port,
                grpc_secure=grpc_secure,
                skip_init_checks=True,
                headers={"X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY", "")},
            )

            self.activity_collection = self.client.collections.get("Activity")
            self._initialized = True

    def _build_filters(
        self,
        activity_type: str | None = None,
        domain: str | None = None,
        selectivity_est: str | None = None,
        time_commitment_est: str | None = None,
    ):
        """Build Weaviate filters for activity search."""
        filters = None

        if activity_type:
            f = Filter.by_property("activity_type").equal(activity_type)
            filters = f if filters is None else (filters & f)

        if domain:
            f = Filter.by_property("domain").equal(domain)
            filters = f if filters is None else (filters & f)

        if selectivity_est:
            f = Filter.by_property("selectivity_est").equal(selectivity_est)
            filters = f if filters is None else (filters & f)

        if time_commitment_est:
            f = Filter.by_property("time_commitment_est").equal(time_commitment_est)
            filters = f if filters is None else (filters & f)

        return filters

    def get_activity_by_slug(self, activity_slug: str) -> dict | None:
        """Get activity by slug. Returns None if not found."""
        try:
            result = self.activity_collection.query.fetch_objects(
                filters=Filter.by_property("activity_slug").equal(activity_slug),
                limit=1,
                return_properties=[
                    "activity_slug",
                    "display_name",
                    "mission_synth",
                    "activity_type",
                    "domain",
                    "selectivity_est",
                    "time_commitment_est",
                    "owner_type",
                    "skills_exposed",
                    "career_alignment",
                    "subtags",
                    "who_its_for_synth",
                    "what_you_do_synth",
                    "how_to_join_synth",
                    "data_confidence",
                    "evidence_citations",
                    "roles_exposed",
                ],
            )
            if not result.objects:
                return None
            return result.objects[0].properties
        except Exception as e:
            print(f"Error retrieving activity {activity_slug}: {e}")
            return None

    def close(self):
        if hasattr(self, "client"):
            self.client.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def get_weaviate_activity_service() -> WeaviateActivityService:
    """Get the singleton WeaviateActivityService instance."""
    return WeaviateActivityService()
