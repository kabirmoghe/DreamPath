"""Interactive Weaviate browser — works with any collection."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import weaviate
import weaviate.classes.config as wc
from weaviate.classes.query import Filter

# Allow importing from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dreampath_processing.weaviate.connection import connect_local_with_openai

st.set_page_config(page_title="Weaviate Browser", layout="wide")
st.title("Weaviate Browser")


# ── Connection (cached for the session) ──────────────────────────────────────

@st.cache_resource
def get_client():
    return connect_local_with_openai()


client = get_client()

# ── Collection selector ───────────────────────────────────────────────────────

all_collections = sorted(client.collections.list_all().keys())
if not all_collections:
    st.error("No collections found. Run `setup_weaviate.py` first.")
    st.stop()

collection_name = st.sidebar.selectbox("Collection", all_collections)
coll = client.collections.get(collection_name)

# ── Schema introspection ──────────────────────────────────────────────────────

schema = coll.config.get()
props = schema.properties  # list of PropertyConfig

# Separate into filterable text props (useful for equality filters) and all prop names
filterable_text_props = [
    p.name for p in props
    if p.data_type in (wc.DataType.TEXT,)
    and getattr(p, "index_filterable", False)
    and not getattr(p, "skip_vectorization", True) is False  # include all filterable
]
# Simpler: any property marked index_filterable
filterable_props = [
    p.name for p in props if getattr(p, "index_filterable", False)
]
all_prop_names = [p.name for p in props]

# ── Sidebar controls ──────────────────────────────────────────────────────────

st.sidebar.markdown("---")
q = st.sidebar.text_input("Hybrid search query", "")
alpha = st.sidebar.slider("Alpha (0=keyword · 1=vector)", 0.0, 1.0, 0.5, 0.05)

st.sidebar.markdown("---")
filter_prop = st.sidebar.selectbox(
    "Filter property (optional)",
    ["(none)"] + filterable_props,
)
filter_val = ""
if filter_prop != "(none)":
    filter_val = st.sidebar.text_input(f"Filter value for `{filter_prop}`", "")

st.sidebar.markdown("---")
limit = st.sidebar.slider("Row limit", 5, 500, 50)

# ── Build filter ──────────────────────────────────────────────────────────────

flt = None
if filter_prop != "(none)" and filter_val.strip():
    flt = Filter.by_property(filter_prop).equal(filter_val.strip())

# ── Query ─────────────────────────────────────────────────────────────────────

try:
    if q.strip():
        res = coll.query.hybrid(
            query=q.strip(),
            alpha=alpha,
            limit=limit,
            filters=flt,
        )
    else:
        res = coll.query.fetch_objects(
            limit=limit,
            filters=flt,
        )
    objs = res.objects
except Exception as e:
    st.error(f"Query failed: {e}")
    st.stop()

# ── Stats header ──────────────────────────────────────────────────────────────

total_count = coll.aggregate.over_all(total_count=True).total_count
col1, col2, col3 = st.columns(3)
col1.metric("Total in collection", total_count)
col2.metric("Returned", len(objs))
col3.metric("Properties", len(all_prop_names))

# ── Results table ─────────────────────────────────────────────────────────────

if not objs:
    st.info("No results. Try a different query or filter.")
else:
    rows = [o.properties for o in objs]
    df = pd.DataFrame(rows)

    # Put the most identifying columns first if they exist
    priority = ["activity_slug", "course_code", "course_id", "major", "display_name",
                "course_title", "department", "domain", "activity_type"]
    ordered = [c for c in priority if c in df.columns] + [c for c in df.columns if c not in priority]
    df = df[ordered]

    st.dataframe(df, use_container_width=True)

# ── Property schema expander ──────────────────────────────────────────────────

with st.expander("Collection schema"):
    schema_rows = []
    for p in props:
        schema_rows.append({
            "name": p.name,
            "data_type": str(p.data_type),
            "filterable": getattr(p, "index_filterable", "—"),
            "searchable": getattr(p, "index_searchable", "—"),
            "skip_vectorization": getattr(p, "skip_vectorization", "—"),
        })
    st.dataframe(pd.DataFrame(schema_rows), use_container_width=True)
