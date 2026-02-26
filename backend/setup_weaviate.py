"""
Setup Weaviate collections and ingest course/major/activity data for local development.

Reads OPENAI_API_KEY from .env (required for text2vec-openai embeddings).
Creates Course, Major, and Activity collections, then ingests from CSV data files.

Usage:
    uv run python backend/setup_weaviate.py              # create + ingest (skip existing)
    uv run python backend/setup_weaviate.py --recreate   # drop and recreate collections
"""

import sys
import argparse
import datetime as dt
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any app imports
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Add backend/ to sys.path so dreampath_processing imports work
sys.path.insert(0, str(Path(__file__).parent))

from dreampath_processing.weaviate.connection import connect_local_with_openai
from dreampath_processing.weaviate.ingest_courses import (
    ensure_course_collection,
    stable_course_id,
    infer_level,
    infer_num_prereqs,
    build_course_rows,
)
from dreampath_processing.weaviate.ingest_majors import ensure_major_collection, build_major_rows
from dreampath_processing.weaviate.ingest_clubs import (
    ensure_activity_collection,
    build_activity_rows,
    load_evidence,
)
from dreampath_processing.courses.data_retrieval.college_info_retrieval import load_dataframes

DATA_DIR = Path(__file__).parent / "dreampath_processing" / "courses" / "data"
COURSE_CSV = DATA_DIR / "all_courses_with_reviews.csv"
MAJOR_CSV = DATA_DIR / "dartmouth_majors.csv"

CLUBS_DATA_DIR = Path(__file__).parent / "dreampath_processing" / "clubs" / "data"
ACTIVITY_CSV = CLUBS_DATA_DIR / "activities.csv"
EVIDENCE_CSV = CLUBS_DATA_DIR / "activity_evidence.csv"


def ingest_courses(client, recreate: bool = False):
    """Create Course collection and ingest data."""
    print("\n--- Courses ---")

    if not COURSE_CSV.exists():
        print(f"Course data not found: {COURSE_CSV}")
        return False

    coll = ensure_course_collection(client, recreate=recreate)

    # Check if already populated (skip if not recreating)
    if not recreate:
        count = coll.aggregate.over_all(total_count=True).total_count
        if count > 0:
            print(f"Course collection already has {count} objects, skipping (use --recreate to reimport)")
            return True

    df = load_dataframes([str(COURSE_CSV)])

    review_fields = [
        "total_reviews",
        "global_difficulty_score", "global_difficulty_normalized",
        "global_difficulty_percentile", "global_difficulty_classification",
        "dept_difficulty_percentile", "dept_difficulty_classification", "difficulty_blurb",
        "global_value_score", "global_value_normalized",
        "global_value_percentile", "global_value_classification",
        "dept_value_percentile", "dept_value_classification",
        "learning_value_blurb", "target_audience_blurb",
    ]
    catalog_fields = [
        "department", "department_id", "course_title", "course_url", "course_code",
        "description", "prerequisites", "degree_req", "html_content", "best_prereq_path",
    ]

    for col in catalog_fields + review_fields:
        if col not in df:
            df[col] = None if col in review_fields else ""

    df["course_id"] = [stable_course_id(d, c) for d, c in zip(df["department"], df["course_code"])]
    df["updated_at"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    df["level"] = [infer_level(c) for c in df["course_code"]]
    df["num_prereqs"] = [infer_num_prereqs(b) for b in df["best_prereq_path"]]

    if "tags" not in df.columns:
        df["tags"] = [[] for _ in range(len(df))]

    rows = build_course_rows(df)

    chunk_size = 100
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        coll.data.insert_many(chunk)
        total += len(chunk)
        print(f"  Ingested {total}/{len(rows)} courses")

    print(f"Courses: {total} objects ingested")
    return True


def ingest_majors(client, recreate: bool = False):
    """Create Major collection and ingest data."""
    print("\n--- Majors ---")

    if not MAJOR_CSV.exists():
        print(f"Major data not found: {MAJOR_CSV}")
        return False

    coll = ensure_major_collection(client, recreate=recreate)

    if not recreate:
        count = coll.aggregate.over_all(total_count=True).total_count
        if count > 0:
            print(f"Major collection already has {count} objects, skipping (use --recreate to reimport)")
            return True

    df = load_dataframes([str(MAJOR_CSV)])

    for col in ["major", "department_id", "department"]:
        if col not in df:
            df[col] = ""

    df["updated_at"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = build_major_rows(df)

    chunk_size = 100
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        coll.data.insert_many(chunk)
        total += len(chunk)
        print(f"  Ingested {total}/{len(rows)} majors")

    print(f"Majors: {total} objects ingested")
    return True


def ingest_activities(client, recreate: bool = False):
    """Create Activity collection and ingest club/activity data."""
    print("\n--- Activities ---")

    if not ACTIVITY_CSV.exists():
        print(f"Activity data not found: {ACTIVITY_CSV}")
        return False

    if not EVIDENCE_CSV.exists():
        print(f"Evidence data not found: {EVIDENCE_CSV}")
        return False

    coll = ensure_activity_collection(client, recreate=recreate)

    if not recreate:
        count = coll.aggregate.over_all(total_count=True).total_count
        if count > 0:
            print(f"Activity collection already has {count} objects, skipping (use --recreate to reimport)")
            return True

    import pandas as pd
    activities_df = pd.read_csv(str(ACTIVITY_CSV))
    evidence_by_slug = load_evidence(str(EVIDENCE_CSV))
    rows = build_activity_rows(activities_df, evidence_by_slug)

    chunk_size = 100
    total = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        coll.data.insert_many(chunk)
        total += len(chunk)
        print(f"  Ingested {total}/{len(rows)} activities")

    print(f"Activities: {total} objects ingested")
    return True


def main():
    ap = argparse.ArgumentParser(description="Setup Weaviate for local development")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate collections before ingesting")
    args = ap.parse_args()

    print("Setting up Weaviate...")
    print(f"Course data:   {COURSE_CSV}")
    print(f"Major data:    {MAJOR_CSV}")
    print(f"Activity data: {ACTIVITY_CSV}")

    client = connect_local_with_openai()
    try:
        course_ok = ingest_courses(client, recreate=args.recreate)
        major_ok = ingest_majors(client, recreate=args.recreate)
        activity_ok = ingest_activities(client, recreate=args.recreate)

        if course_ok and major_ok and activity_ok:
            print("\nWeaviate setup complete!")
        else:
            print("\nWeaviate setup completed with errors (see above)")
            sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
