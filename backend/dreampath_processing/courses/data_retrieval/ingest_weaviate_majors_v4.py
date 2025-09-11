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

# ---- Schema / Collection (v4) ----------------------------------------------

def ensure_major_collection(client, name="Major", recreate=False, use_openai=True):
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
            wc.Property(name="major",            data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="department_id",    data_type=wc.DataType.UUID, index_filterable=True, skip_vectorization=True),
            wc.Property(name="department",       data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="updated_at",       data_type=wc.DataType.DATE, index_filterable=True, skip_vectorization=True),
        ],
        vectorizer_config=vector_cfg,
    )
    return coll

def main():
    ap = argparse.ArgumentParser(description="Ingest department CSVs into Weaviate (v4 client)")
    ap.add_argument("inputs", nargs="+", help="CSV file(s) or a directory containing CSVs")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate the collection before ingest")
    ap.add_argument("--no-openai", action="store_true", help="Don't use text2vec-openai (vectors must be supplied or vectorizer disabled)")
    ap.add_argument("--collection", default="Major", help="Collection name (default: Major)")
    args = ap.parse_args()

    client = connect_local_with_openai()  # or use connect_to_custom(url="http://localhost:8080", headers=...)
    try:
        coll = ensure_major_collection(client, name=args.collection, recreate=args.recreate, use_openai=(not args.no_openai))

        df = load_dataframes(args.inputs)
        expected = ["major","department_id","department"]
        for col in expected:
            if col not in df: df[col] = ""

        if "tags" not in df.columns:
            df["tags"] = [[] for _ in range(len(df))]

        df["updated_at"] = dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

        # v4: insert_many for convenience; it will vectorize from text if a vectorizer is configured
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "major": r["major"],
                "department_id": r["department_id"],
                "department": r["department"],
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
    main()