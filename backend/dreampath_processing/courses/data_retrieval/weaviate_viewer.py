import streamlit as st
import pandas as pd
import weaviate
from weaviate.classes.query import Filter

st.set_page_config(page_title="Course Browser", layout="wide")
st.title("Course Browser (Weaviate)")

# Connect (adjust if you changed ports)
client = weaviate.connect_to_custom(
    http_host="localhost",
    http_port=8080,
    http_secure=False,
    grpc_host="localhost",
    grpc_port=50051,
    grpc_secure=False,
)

coll = client.collections.get("Course")

# Sidebar filters
q = st.sidebar.text_input("Search (hybrid)", "")
alpha = st.sidebar.slider("Hybrid alpha (0=keyword, 1=vector)", 0.0, 1.0, 0.5, 0.05)
dept = st.sidebar.text_input("Department filter (e.g., COSC)", "")
limit = st.sidebar.slider("Rows", 5, 200, 50)

# Build filters
flt = None
if dept:
    flt = Filter.by_property("dept").equal(dept)

# Query
if q:
    res = coll.query.hybrid(
        query=q, alpha=alpha, limit=limit,
        filters=flt,
        return_properties=[
            "dept","course_code","course_title","description","prerequisites","num_prereqs","level","course_url"
        ],
    )
    objs = res.objects
else:
    res = coll.query.fetch_objects(
        limit=limit, filters=flt,
        return_properties=[
            "dept","course_code","course_title","description","prerequisites","num_prereqs","level","course_url"
        ],
    )
    objs = res.objects

rows = [o.properties for o in objs]
df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

client.close()