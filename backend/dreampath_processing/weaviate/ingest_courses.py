import re, argparse, datetime as dt, ast
import pandas as pd
import weaviate.classes.config as wc
from dreampath_processing.weaviate.connection import connect_local_with_openai
from dreampath_processing.weaviate.utils import safe_float, safe_int, safe_str
from dreampath_processing.courses.data_retrieval.college_info_retrieval import load_dataframes


# ---- IDs & transforms -------------------------------------------------------

def stable_course_id(department: str, course_code: str) -> str:
    """Reproducible id based on intrinsic fields."""
    try:
        d = (department or "").strip().upper()
        c = (course_code or "").strip().upper()
        return f"{d}::{c}"
    except Exception as e:
        print(department, course_code)
        raise Exception(f"Error creating stable course id with department: {department} and course code: {course_code}: {e}")


def infer_level(code: str) -> int:
    m = re.search(r"(\d+)", str(code or ""))
    return int(m.group(1)) if m else 0


def infer_num_prereqs(best_prereq_path_str: str) -> int:
    best_prereq_path = ast.literal_eval(best_prereq_path_str)
    return len(best_prereq_path)


# ---- Schema / Collection ----------------------------------------------------

def ensure_course_collection(client, name="Course", recreate=False, use_openai=True):
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
            # ========== EXISTING COURSE CATALOG FIELDS ==========
            wc.Property(name="course_id",        data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="course_code",      data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="department_id",    data_type=wc.DataType.UUID, index_filterable=True, skip_vectorization=True),
            wc.Property(name="department",       data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="course_title",     data_type=wc.DataType.TEXT, index_searchable=True),  # Vectorized
            wc.Property(name="description",      data_type=wc.DataType.TEXT, index_searchable=True),  # Vectorized
            wc.Property(name="level",            data_type=wc.DataType.INT, index_filterable=True),
            wc.Property(name="prerequisites",    data_type=wc.DataType.TEXT, index_searchable=True, skip_vectorization=True),
            wc.Property(name="best_prereq_path", data_type=wc.DataType.TEXT, index_searchable=True, skip_vectorization=True),
            wc.Property(name="num_prereqs",      data_type=wc.DataType.INT, index_filterable=True),
            wc.Property(name="degree_req",       data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="course_url",       data_type=wc.DataType.TEXT, skip_vectorization=True),
            wc.Property(name="tags",             data_type=wc.DataType.TEXT_ARRAY, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="updated_at",       data_type=wc.DataType.DATE, index_filterable=True, skip_vectorization=True),

            # ========== ENRICHED REVIEW FIELDS ==========
            wc.Property(name="total_reviews", data_type=wc.DataType.INT, index_filterable=True, skip_vectorization=True),

            wc.Property(name="global_difficulty_score", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_difficulty_normalized", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_difficulty_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_difficulty_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),

            wc.Property(name="global_difficulty_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_difficulty_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),

            wc.Property(name="difficulty_blurb", data_type=wc.DataType.TEXT, index_searchable=True),  # Vectorized

            wc.Property(name="global_value_score", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_value_normalized", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_value_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_value_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),

            wc.Property(name="global_value_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_value_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),

            wc.Property(name="learning_value_blurb", data_type=wc.DataType.TEXT, index_searchable=True),  # Vectorized
            wc.Property(name="target_audience_blurb", data_type=wc.DataType.TEXT, index_searchable=True),  # Vectorized
        ],
    )
    return coll


# ---- Row building -----------------------------------------------------------

def build_course_rows(df: "pd.DataFrame") -> list[dict]:
    """Convert a prepared course DataFrame into a list of Weaviate property dicts."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "course_id": r["course_id"],
            "course_code": r["course_code"],
            "department_id": r["department_id"],
            "department": r["department"],
            "course_title": r["course_title"],
            "description": r["description"],
            "level": r["level"],
            "prerequisites": r["prerequisites"],
            "best_prereq_path": r["best_prereq_path"],
            "num_prereqs": r["num_prereqs"],
            "degree_req": r["degree_req"],
            "course_url": r["course_url"],
            "tags": (
                list(r["tags"]) if isinstance(r["tags"], (list, tuple))
                else ([r["tags"]] if str(r["tags"]).strip() not in ["", "nan", "None"] else [])
            ),
            "updated_at": r["updated_at"],
            "total_reviews": safe_int(r.get("total_reviews")),
            "global_difficulty_score": safe_float(r.get("global_difficulty_score")),
            "global_difficulty_normalized": safe_float(r.get("global_difficulty_normalized")),
            "global_difficulty_percentile": safe_float(r.get("global_difficulty_percentile")),
            "dept_difficulty_percentile": safe_float(r.get("dept_difficulty_percentile")),
            "global_difficulty_classification": safe_str(r.get("global_difficulty_classification")),
            "dept_difficulty_classification": safe_str(r.get("dept_difficulty_classification")),
            "difficulty_blurb": safe_str(r.get("difficulty_blurb")),
            "global_value_score": safe_float(r.get("global_value_score")),
            "global_value_normalized": safe_float(r.get("global_value_normalized")),
            "global_value_percentile": safe_float(r.get("global_value_percentile")),
            "dept_value_percentile": safe_float(r.get("dept_value_percentile")),
            "global_value_classification": safe_str(r.get("global_value_classification")),
            "dept_value_classification": safe_str(r.get("dept_value_classification")),
            "learning_value_blurb": safe_str(r.get("learning_value_blurb")),
            "target_audience_blurb": safe_str(r.get("target_audience_blurb")),
        })
    return rows


# ---- CLI entry point --------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Ingest course CSVs into Weaviate")
    ap.add_argument("inputs", nargs="+", help="CSV file(s) or a directory containing CSVs")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate the collection before ingest")
    ap.add_argument("--no-openai", action="store_true", help="Don't use text2vec-openai")
    ap.add_argument("--collection", default="Course", help="Collection name (default: Course)")
    args = ap.parse_args()

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

    client = connect_local_with_openai()
    try:
        coll = ensure_course_collection(client, name=args.collection, recreate=args.recreate, use_openai=(not args.no_openai))

        df = load_dataframes(args.inputs)
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
            print(f"Ingested chunk {i // chunk_size + 1}: {len(chunk)} objects (total: {total}/{len(rows)})")

        print(f"Successfully ingested {total} objects into collection '{args.collection}'.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
