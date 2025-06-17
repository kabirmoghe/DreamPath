import numpy as np
import pandas as pd
import json
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import pairwise_distances
from openai import OpenAI
import os
import hdbscan
import umap.umap_ as umap
import matplotlib.pyplot as plt

def load_alumni_json(alumni_json_path):
    with open(alumni_json_path, 'r') as file:
        alumni_json = json.load(file)

    records = []
    for alum in alumni_json:
        record = {
            "alum_id": alum["alum_id"],
            "name": alum["name"],
            "grad_year": alum["grad_year"],
            "major": alum["major"],
            "post_grad_summary_string": alum["post_grad"]["summary"],
            "post_grad_skills_string": ", ".join(alum["post_grad"]["skills"]),
            "career_trajectory_string": alum["career_trajectory"]["summary"],
            "long_term_skills_string": ", ".join(alum["career_trajectory"]["skills"])
        }
        records.append(record)

    return pd.DataFrame(records)

def embed_texts(text_list, model='text-embedding-3-small'):
    embeddings = []
    batch_size = 20  # Avoid rate limits

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    for i in range(0, len(text_list), batch_size):
        response = client.embeddings.create(
            model=model,
            input=text_list[i:i+batch_size]
        )
        batch_embeddings = [e.embedding for e in response.data]
        embeddings.extend(batch_embeddings)

    return embeddings

def extract_clustering_features(alumni_df):
    scaler = MinMaxScaler()

    # Normalize grad_year
    # alumni_df["grad_year_scaled"] = scaler.fit_transform(alumni_df[["grad_year"]])
    # major_dummies_values = pd.get_dummies(alumni_df["major"], prefix="major")

    # Normalize summary + skills
    alumni_df["postgrad_concat"] = alumni_df["post_grad_summary_string"] + ". Skills: " + alumni_df["post_grad_skills_string"]
    alumni_df["career_concat"] = alumni_df["career_trajectory_string"] + " Skills: " + alumni_df["long_term_skills_string"]

    postgrad_embeddings = embed_texts(alumni_df["post_grad_summary_string"])
    career_embeddings = embed_texts(alumni_df["career_trajectory_string"])

    # Create features
    # grad_year_feature = alumni_df["grad_year_scaled"].values.reshape(-1, 1)
    # major_dummies_feature = major_dummies_values.values

    X_postgrad = np.hstack([postgrad_embeddings])
    X_career = np.hstack([career_embeddings])

    return X_postgrad, X_career

def cluster_alumni(alumni_df):
    print("Extracting clustering features...")
    X_postgrad, X_career = extract_clustering_features(alumni_df)

    # Create clusterer
    print("Clustering...")
    postgrad_distance = pairwise_distances(X_postgrad, metric='cosine')
    career_distance = pairwise_distances(X_career, metric='cosine')
    
    postgrad_clusterer = hdbscan.HDBSCAN(min_cluster_size=3, metric='precomputed')
    career_clusterer = hdbscan.HDBSCAN(min_cluster_size=3, metric='precomputed')

    # Fit and predict
    alumni_df["postgrad_cluster"] = postgrad_clusterer.fit_predict(postgrad_distance)
    alumni_df["career_cluster"] = career_clusterer.fit_predict(career_distance)

    # Evaluation
    print("Dimensionality reduction...")
    dim_reducer = umap.UMAP()
    X_postgrad_2d = dim_reducer.fit_transform(X_postgrad)

    plt.scatter(X_postgrad_2d[:, 0], X_postgrad_2d[:, 1], c=alumni_df["postgrad_cluster"], cmap="Spectral")
    plt.title("Post-grad Clusters via UMAP + HDBSCAN")
    plt.show()

    print("Dimensionality reduction for career clusters...")
    X_career_2d = dim_reducer.fit_transform(X_career)

    plt.scatter(X_career_2d[:, 0], X_career_2d[:, 1], c=alumni_df["career_cluster"], cmap="Spectral")
    plt.title("Career Clusters via UMAP + HDBSCAN")
    plt.show()

    return alumni_df

if __name__ == "__main__":
    alumni_df = pd.read_csv("sample_alumni_clustering_data.csv")
    print("Loaded data: ")
    print(alumni_df.head())
    cluster_alumni(alumni_df)
