import streamlit as st
import pandas as pd
import weaviate
from weaviate.classes.query import Filter

st.set_page_config(page_title="Course Browser", layout="wide")
st.title("Vector Course Browser")

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
department = st.sidebar.text_input("Department filter (e.g., COSC)", "")
limit = st.sidebar.slider("Rows", 5, 200, 50)

# Build filters
flt = None
if department:
    flt = Filter.by_property("department").equal(department)

return_ppts = ["department","course_code","course_title","description","prerequisites","num_prereqs","level","course_url"]
return_ppts += ["total_reviews","global_difficulty_percentile","global_difficulty_classification", "difficulty_blurb", "global_value_percentile", "global_value_classification","learning_value_blurb"]

# Query
if q:
    res = coll.query.hybrid(
        query=q, alpha=alpha, limit=limit,
        filters=flt,
        return_properties=return_ppts,
    )
    objs = res.objects
else:
    res = coll.query.fetch_objects(
        limit=limit, filters=flt,
        return_properties=return_ppts,
    )
    objs = res.objects

rows = [o.properties for o in objs]
df = pd.DataFrame(rows)
st.dataframe(df)

client.close()