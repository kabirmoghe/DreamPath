import argparse, datetime as dt
import pandas as pd
import weaviate.classes.config as wc
from dreampath_processing.weaviate.connection import connect_local_with_openai
from dreampath_processing.courses.data_retrieval.college_info_retrieval import load_dataframes


# ---- Schema / Collection ----------------------------------------------------

def ensure_major_collection(client, name="Major", recreate=False, use_openai=True):
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
            wc.Property(name="major",         data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="department_id", data_type=wc.DataType.UUID, index_filterable=True, skip_vectorization=True),
            wc.Property(name="department",    data_type=wc.DataType.TEXT, index_searchable=True, index_filterable=True, skip_vectorization=True),
            wc.Property(name="updated_at",    data_type=wc.DataType.DATE, index_filterable=True, skip_vectorization=True),
        ],
    )
    return coll


# ---- Row building -----------------------------------------------------------

def build_major_rows(df: "pd.DataFrame") -> list[dict]:
    """Convert a prepared major DataFrame into a list of Weaviate property dicts."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "major": r["major"],
            "department_id": r["department_id"],
            "department": r["department"],
            "updated_at": r["updated_at"],
        })
    return rows


# ---- CLI entry point --------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Ingest major CSVs into Weaviate")
    ap.add_argument("inputs", nargs="+", help="CSV file(s) or a directory containing CSVs")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate the collection before ingest")
    ap.add_argument("--no-openai", action="store_true", help="Don't use text2vec-openai")
    ap.add_argument("--collection", default="Major", help="Collection name (default: Major)")
    args = ap.parse_args()

    client = connect_local_with_openai()
    try:
        coll = ensure_major_collection(client, name=args.collection, recreate=args.recreate, use_openai=(not args.no_openai))

        df = load_dataframes(args.inputs)
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
            print(f"Ingested chunk {i // chunk_size + 1}: {len(chunk)} objects (total: {total}/{len(rows)})")

        print(f"Successfully ingested {total} objects into collection '{args.collection}'.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
