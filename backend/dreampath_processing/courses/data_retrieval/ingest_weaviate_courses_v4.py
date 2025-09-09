import os, re, argparse, datetime as dt, json, ast
import pandas as pd
import weaviate
import weaviate.classes.config as wc
from weaviate.classes.query import Filter

# ---- Connection helpers -----------------------------------------------------

def connect_local_with_openai():
    # If using text2vec-openai / reranker-openai, pass the key in headers:
    headers = {}
    if os.getenv("OPENAI_API_KEY"):
        headers = {"X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"]}
    # use HTTP+gRPC local defaults; change url if needed
    return weaviate.connect_to_local(headers=headers)

# ---- IDs & transforms -------------------------------------------------------
def stable_course_id(dept: str, course_code: str) -> str:
    """Reproducible id based on intrinsic fields."""
    try:
        d = (dept or "").strip().upper()
        c = (course_code or "").strip().upper()
        return f"{d}::{c}"
    except Exception as e:
        raise Exception(f"Error creating stable course id with dept: {dept} and course code: {course_code}: {e}")

def infer_level(code: str) -> int:
    m = re.search(r"(\d+)", str(code or ""))
    return int(m.group(1)) if m else 0

def infer_num_prereqs(best_prereq_path_str: str) -> int:
    best_prereq_path = ast.literal_eval(best_prereq_path_str)
    return len(best_prereq_path)

def load_dataframes(paths):
    rows = []
    for p in paths:
        print(f"Loading '{p}'...")
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith(".csv"):
                    rows.append(pd.read_csv(os.path.join(p, name)))
        else:
            rows.append(pd.read_csv(p))
    if not rows:
        raise SystemExit("No CSVs found.")
    return pd.concat(rows, ignore_index=True)

# ---- Schema / Collection (v4) ----------------------------------------------

def ensure_collection(client, name="Course", recreate=False, use_openai=True):
    if recreate:
        try:
            client.collections.delete(name)
        except Exception:
            pass

    existing = [c.name for c in client.collections.list_all()]
    if name in existing:
        return client.collections.get(name)

    vector_cfg = (
        wc.Configure.Vectorizer.text2vec_openai() if use_openai
        else wc.Configure.Vectorizer.none()
    )
    coll = client.collections.create(
        name=name,
        properties=[
            wc.Property(name="course_id",        data_type=wc.DataType.TEXT, index_filterable=True, skip_vectorization=True),
            wc.Property(name="dept",             data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="course_code",      data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="course_title",     data_type=wc.DataType.TEXT, index_searchable=True),  # Will be vectorized
            wc.Property(name="description",      data_type=wc.DataType.TEXT, index_searchable=True),  # Will be vectorized
            wc.Property(name="level",            data_type=wc.DataType.INT, index_filterable=True),
            wc.Property(name="prerequisites",    data_type=wc.DataType.TEXT, index_searchable=True, skip_vectorization=True),
            wc.Property(name="best_prereq_path", data_type=wc.DataType.TEXT, index_searchable=True, skip_vectorization=True),
            wc.Property(name="num_prereqs",      data_type=wc.DataType.INT, index_filterable=True),
            wc.Property(name="degree_req",       data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="course_url",       data_type=wc.DataType.TEXT, skip_vectorization=True),
            wc.Property(name="tags",             data_type=wc.DataType.TEXT_ARRAY, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="updated_at",       data_type=wc.DataType.DATE, index_filterable=True, skip_vectorization=True),
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
        coll = ensure_collection(client, name=args.collection, recreate=args.recreate, use_openai=(not args.no_openai))

        df = load_dataframes(args.inputs)
        expected = ["dept","course_title","course_url","course_code","description",
                    "prerequisites","degree_req","html_content","best_prereq_path"]
        for col in expected:
            if col not in df: df[col] = ""

        df["course_id"] = [stable_course_id(d, c) for d,c in zip(df["dept"], df["course_code"])]
        df["updated_at"] = dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        df["level"] = [infer_level(c) for c in df["course_code"]]
        df["num_prereqs"] = [infer_num_prereqs(b) for b in df["best_prereq_path"]]

        if "tags" not in df.columns:
            df["tags"] = [[] for _ in range(len(df))]

        # v4: insert_many for convenience; it will vectorize from text if a vectorizer is configured
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "course_id": r["course_id"],
                "dept": r["dept"],
                "course_code": r["course_code"],
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
    finally:
        client.close()

if __name__ == "__main__":
    # print(infer_level("COSC89.21"))
    main()