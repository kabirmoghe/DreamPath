import os, re, argparse, datetime as dt, json, ast
import pandas as pd
import weaviate
import weaviate.classes.config as wc
from weaviate.classes.query import Filter
from dreampath_processing.courses.data_retrieval.college_info_retrieval import load_dataframes

# ---- Connection helpers -----------------------------------------------------

def connect_local_with_openai():
    # If using text2vec-openai / reranker-openai, pass the key in headers:
    headers = {}
    if os.getenv("OPENAI_API_KEY"):
        headers = {"X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"]}
    # use HTTP+gRPC local defaults; change url if needed
    return weaviate.connect_to_local(headers=headers)

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

# ---- Safe type converters for review data ----------------------------------

def safe_float(value):
    """Convert value to float, handling NaN/None."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def safe_int(value):
    """Convert value to int, handling NaN/None."""
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def safe_str(value):
    """Convert value to str, handling NaN/None."""
    if pd.isna(value) or value in ["", "nan", "None"]:
        return None
    return str(value).strip()

# ---- Schema / Collection (v4) ----------------------------------------------

def ensure_course_collection(client, name="Course", recreate=False, use_openai=True):
    if recreate:
        try:
            client.collections.delete(name)
        except Exception:
            pass

    existing = [c for c, _ in client.collections.list_all().items()]
    if name in existing:
        return client.collections.get(name)

    vector_cfg = (
        wc.Configure.Vectorizer.text2vec_openai() if use_openai
        else wc.Configure.Vectorizer.none()
    )
    coll = client.collections.create(
        name=name,
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

            # ========== NEW ENRICHED REVIEW FIELDS ==========
            # Review count
            wc.Property(name="total_reviews", data_type=wc.DataType.INT, index_filterable=True, skip_vectorization=True),

            # Difficulty metrics (numeric scores - filterable)
            wc.Property(name="global_difficulty_score", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_difficulty_normalized", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_difficulty_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_difficulty_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),

            # Difficulty classifications (text - searchable + filterable)
            wc.Property(name="global_difficulty_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_difficulty_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),

            # Difficulty blurb (VECTORIZED for semantic search)
            wc.Property(name="difficulty_blurb", data_type=wc.DataType.TEXT, index_searchable=True),

            # Learning value metrics (numeric scores - filterable)
            wc.Property(name="global_value_score", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_value_normalized", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="global_value_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_value_percentile", data_type=wc.DataType.NUMBER, index_filterable=True, skip_vectorization=True),

            # Learning value classifications (text - searchable + filterable)
            wc.Property(name="global_value_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept_value_classification", data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),

            # Learning value blurbs (VECTORIZED for semantic search)
            wc.Property(name="learning_value_blurb", data_type=wc.DataType.TEXT, index_searchable=True),
            wc.Property(name="target_audience_blurb", data_type=wc.DataType.TEXT, index_searchable=True),
        ],
        vectorizer_config=vector_cfg,
        # Optional: enable generative/reranker modules if your server has them
        # generative_config=wc.Configure.Generative.openai(),
    )
    return coll

def main():
    ap = argparse.ArgumentParser(description="Ingest department CSVs into Weaviate (v4 client)")
    ap.add_argument("inputs", nargs="+", help="CSV file(s) or a directory containing CSVs")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate the collection before ingest")
    ap.add_argument("--no-openai", action="store_true", help="Don't use text2vec-openai (vectors must be supplied or vectorizer disabled)")
    ap.add_argument("--collection", default="Course", help="Collection name (default: Course)")
    args = ap.parse_args()

    client = connect_local_with_openai()  # or use connect_to_custom(url="http://localhost:8080", headers=...)
    try:
        coll = ensure_course_collection(client, name=args.collection, recreate=args.recreate, use_openai=(not args.no_openai))


        df = load_dataframes(args.inputs)
        expected = ["department","department_id","course_title","course_url","course_code","description",
                    "prerequisites","degree_req","html_content","best_prereq_path"]
        # Add expected review fields (optional for backward compatibility)
        review_fields = [
            "total_reviews",
            "global_difficulty_score", "global_difficulty_normalized",
            "global_difficulty_percentile", "global_difficulty_classification",
            "dept_difficulty_percentile", "dept_difficulty_classification", "difficulty_blurb",
            "global_value_score", "global_value_normalized",
            "global_value_percentile", "global_value_classification",
            "dept_value_percentile", "dept_value_classification",
            "learning_value_blurb", "target_audience_blurb"
        ]
        expected.extend(review_fields)

        # Fill missing columns (backward compatibility)
        for col in expected:
            if col not in df:
                if col in review_fields:
                    df[col] = None  # Review fields default to None
                else:
                    df[col] = ""  # Catalog fields default to empty string

        df["course_id"] = [stable_course_id(d, c) for d,c in zip(df["department"], df["course_code"])]
        df["updated_at"] = dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        df["level"] = [infer_level(c) for c in df["course_code"]]
        df["num_prereqs"] = [infer_num_prereqs(b) for b in df["best_prereq_path"]]

        if "tags" not in df.columns:
            df["tags"] = [[] for _ in range(len(df))]

        # v4: insert_many for convenience; it will vectorize from text if a vectorizer is configured
        rows = []
        for _, r in df.iterrows():
            rows.append({
                # ========== EXISTING CATALOG FIELDS ==========
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
                "tags": (list(r["tags"]) if isinstance(r["tags"], (list,tuple))
                         else ([r["tags"]] if str(r["tags"]).strip() not in ["","nan","None"] else [])),
                "updated_at": r["updated_at"],

                # ========== NEW REVIEW FIELDS ==========
                "total_reviews": safe_int(r.get("total_reviews")),

                # Difficulty metrics
                "global_difficulty_score": safe_float(r.get("global_difficulty_score")),
                "global_difficulty_normalized": safe_float(r.get("global_difficulty_normalized")),
                "global_difficulty_percentile": safe_float(r.get("global_difficulty_percentile")),
                "dept_difficulty_percentile": safe_float(r.get("dept_difficulty_percentile")),
                "global_difficulty_classification": safe_str(r.get("global_difficulty_classification")),
                "dept_difficulty_classification": safe_str(r.get("dept_difficulty_classification")),
                "difficulty_blurb": safe_str(r.get("difficulty_blurb")),

                # Learning value metrics
                "global_value_score": safe_float(r.get("global_value_score")),
                "global_value_normalized": safe_float(r.get("global_value_normalized")),
                "global_value_percentile": safe_float(r.get("global_value_percentile")),
                "dept_value_percentile": safe_float(r.get("dept_value_percentile")),
                "global_value_classification": safe_str(r.get("global_value_classification")),
                "dept_value_classification": safe_str(r.get("dept_value_classification")),
                "learning_value_blurb": safe_str(r.get("learning_value_blurb")),
                "target_audience_blurb": safe_str(r.get("target_audience_blurb")),
            })
        # Process in smaller chunks to avoid gRPC message size limits
        chunk_size = 100  # Adjust based on your data size
        total_ingested = 0
        
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            coll.data.insert_many(chunk)
            total_ingested += len(chunk)
            print(f"Ingested chunk {i//chunk_size + 1}: {len(chunk)} objects (total: {total_ingested}/{len(rows)})")

        print(f"Successfully ingested {total_ingested} objects into collection '{args.collection}'.")

        # Print review data statistics
        courses_with_reviews = sum(1 for r in rows if r.get("total_reviews") is not None and r["total_reviews"] > 0)
        if courses_with_reviews > 0:
            print(f"\n📊 Review Data Statistics:")
            print(f"   Courses with reviews: {courses_with_reviews}")
            print(f"   Courses without reviews: {total_ingested - courses_with_reviews}")
            print(f"   Coverage: {courses_with_reviews/total_ingested*100:.1f}%")
    finally:
        client.close()

if __name__ == "__main__":
    main()