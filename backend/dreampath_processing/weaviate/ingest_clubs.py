"""Ingest club/activity data into Weaviate Activity collection."""

import json
import argparse
import pandas as pd
import weaviate.classes.config as wc
from dreampath_processing.weaviate.connection import connect_local_with_openai
from dreampath_processing.weaviate.utils import safe_str, parse_pipe_list


# ---- Schema / Collection ----------------------------------------------------

def ensure_activity_collection(client, name="Activity", recreate=False, use_openai=True):
    if recreate:
        try:
            client.collections.delete(name)
        except Exception:
            pass

    existing = [c for c, _ in client.collections.list_all().items()]
    if name in existing:
        return client.collections.get(name)

    coll = client.collections.create(
        name=name,
        vector_config=wc.Configure.Vectors.text2vec_openai() if use_openai else None,
        properties=[
            # ===== Vectorized prose fields =====
            wc.Property(name="display_name",      data_type=wc.DataType.TEXT, index_searchable=True),
            wc.Property(name="mission_synth",     data_type=wc.DataType.TEXT, index_searchable=True),
            wc.Property(name="what_you_do_synth", data_type=wc.DataType.TEXT, index_searchable=True),
            wc.Property(name="who_its_for_synth", data_type=wc.DataType.TEXT, index_searchable=True),

            # ===== Vectorized array fields =====
            # TEXT_ARRAY: Weaviate joins elements for embedding; also enables ContainsAny/ContainsAll filters
            wc.Property(name="subtags",          data_type=wc.DataType.TEXT_ARRAY, index_searchable=True, index_filterable=True),
            wc.Property(name="skills_exposed",   data_type=wc.DataType.TEXT_ARRAY, index_searchable=True, index_filterable=True),
            wc.Property(name="career_alignment", data_type=wc.DataType.TEXT_ARRAY, index_searchable=True, index_filterable=True),

            # ===== Filterable TEXT, not vectorized =====
            wc.Property(name="activity_slug",        data_type=wc.DataType.TEXT, index_filterable=True, index_searchable=True, skip_vectorization=True),
            wc.Property(name="activity_type",        data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="domain",               data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="selectivity_est",      data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="time_commitment_est",  data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="owner_type",           data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="campus_affiliation",   data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="data_confidence",      data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="last_verified_utc",    data_type=wc.DataType.DATE, index_filterable=True, skip_vectorization=True),

            # ===== Display-only (stored, not filterable, not vectorized) =====
            wc.Property(name="short_name",          data_type=wc.DataType.TEXT, skip_vectorization=True),
            wc.Property(name="how_to_join_synth",   data_type=wc.DataType.TEXT, skip_vectorization=True),
            wc.Property(name="source_of_truth_url", data_type=wc.DataType.TEXT, skip_vectorization=True),
            wc.Property(name="roles_exposed",       data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
            wc.Property(name="official_urls",       data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
            wc.Property(name="evidence_citations",  data_type=wc.DataType.TEXT, skip_vectorization=True),
        ],
    )
    return coll


# ---- Evidence helpers -------------------------------------------------------

def load_evidence(csv_path: str) -> dict[str, list[dict]]:
    """Read activity_evidence.csv and return rows grouped by activity_slug."""
    df = pd.read_csv(csv_path)
    evidence_by_slug: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        slug = row.get("activity_slug")
        if not slug or (isinstance(slug, float) and pd.isna(slug)):
            continue
        entry = {
            "source_type": safe_str(row.get("source_type")),
            "title":       safe_str(row.get("title")),
            "url":         safe_str(row.get("url")),
            "signal_kind": safe_str(row.get("signal_kind")),
            "reliability": safe_str(row.get("reliability")),
        }
        evidence_by_slug.setdefault(str(slug), []).append(entry)
    return evidence_by_slug


def derive_data_confidence(evidence_rows: list[dict]) -> str:
    if not evidence_rows:
        return "low"
    high_count = sum(1 for e in evidence_rows if e.get("reliability") == "high")
    ratio = high_count / len(evidence_rows)
    if ratio >= 0.6:
        return "high"
    elif ratio >= 0.3:
        return "medium"
    else:
        return "low"


def build_evidence_citations(evidence_rows: list[dict]) -> str:
    """Compact JSON string the LLM/finalizer can read to cite sources."""
    return json.dumps(evidence_rows)


# ---- Row building -----------------------------------------------------------

def build_activity_rows(activities_df: pd.DataFrame, evidence_by_slug: dict) -> list[dict]:
    """Convert activities DataFrame + evidence into Weaviate property dicts."""
    rows = []
    for _, r in activities_df.iterrows():
        slug = str(r.get("activity_slug", ""))
        evidence_rows = evidence_by_slug.get(slug, [])

        rows.append({
            # Vectorized prose
            "display_name":      safe_str(r.get("display_name")),
            "mission_synth":     safe_str(r.get("mission_synth")),
            "what_you_do_synth": safe_str(r.get("what_you_do_synth")),
            "who_its_for_synth": safe_str(r.get("who_its_for_synth")),

            # Vectorized arrays (pipe-separated in CSV)
            "subtags":          parse_pipe_list(r.get("subtags")),
            "skills_exposed":   parse_pipe_list(r.get("skills_exposed")),
            "career_alignment": parse_pipe_list(r.get("career_alignment")),

            # Filterable TEXT
            "activity_slug":       slug,
            "activity_type":       safe_str(r.get("activity_type")),
            "domain":              safe_str(r.get("domain")),
            "selectivity_est":     safe_str(r.get("selectivity_est")),
            "time_commitment_est": safe_str(r.get("time_commitment_est")),
            "owner_type":          safe_str(r.get("owner_type")),
            "campus_affiliation":  safe_str(r.get("campus_affiliation")),
            "data_confidence":     derive_data_confidence(evidence_rows),
            "last_verified_utc":   safe_str(r.get("last_verified_utc")),

            # Display-only
            "short_name":          safe_str(r.get("short_name")),
            "how_to_join_synth":   safe_str(r.get("how_to_join_synth")),
            "source_of_truth_url": safe_str(r.get("source_of_truth_url")),
            "roles_exposed":       parse_pipe_list(r.get("roles_exposed")),
            "official_urls":       parse_pipe_list(r.get("official_urls")),
            "evidence_citations":  build_evidence_citations(evidence_rows),
        })
    return rows


# ---- CLI entry point --------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Ingest club/activity data into Weaviate Activity collection")
    ap.add_argument("--activities", required=True, help="Path to activities.csv")
    ap.add_argument("--evidence", required=True, help="Path to activity_evidence.csv")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate the collection before ingest")
    ap.add_argument("--no-openai", action="store_true", help="Don't use text2vec-openai")
    ap.add_argument("--collection", default="Activity", help="Collection name (default: Activity)")
    args = ap.parse_args()

    client = connect_local_with_openai()
    try:
        coll = ensure_activity_collection(
            client, name=args.collection, recreate=args.recreate, use_openai=(not args.no_openai)
        )

        # Skip if already populated (unless recreating)
        if not args.recreate:
            count = coll.aggregate.over_all(total_count=True).total_count
            if count > 0:
                print(f"Activity collection already has {count} objects, skipping (use --recreate to reimport)")
                return

        activities_df = pd.read_csv(args.activities)
        evidence_by_slug = load_evidence(args.evidence)
        rows = build_activity_rows(activities_df, evidence_by_slug)

        chunk_size = 100
        total = 0
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            coll.data.insert_many(chunk)
            total += len(chunk)
            print(f"  Ingested {total}/{len(rows)} activities")

        print(f"Successfully ingested {total} objects into collection '{args.collection}'.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
