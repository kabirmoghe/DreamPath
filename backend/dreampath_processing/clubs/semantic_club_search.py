from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import json
import os
import numpy as np
from dreampath_processing.clubs.prompts.club_matching_prompts import *
from dreampath_processing.clubs.club_info_retrieval import load_club_vector_store, build_tag_embeddings
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = OpenAIEmbeddings(api_key=openai_api_key)

# Add this mapping at the top of the file after imports
PARAMETER_TO_PROMPT_MAP = {
    "college_interests": PARSE_CLUB_THEMES_FROM_INTERESTS_PROMPT,
    "post_grad_goal": PARSE_CLUB_THEMES_FOR_POST_GRAD_GOALS_PROMPT,
    "long_term_goal": PARSE_CLUB_THEMES_FOR_LONG_TERM_GOALS_PROMPT
}
    
# ---- 3 retrieval strategies ----
def complete_similarity(vs, query, k=5):
    """
    One-shot embedding of the entire query string against (blurb+tags) vectors.
    Returns top-k (Document, distance) pairs sorted by L2 distance (lower = better).
    """
    return vs.similarity_search_with_score(query, k=k)


def dual_similarity(vs, tag_embeds, query, k=5, alpha=0.5):
    """
    Blends two signals:
      - blurb-based similarity (1 / (1 + L2_distance))
      - tag-based cosine similarity
    alpha ∈ [0,1] weights the blurb component.
    """
    # 1) get the entire list of docs & distances
    docs, dists = zip(*vs.similarity_search_with_score(query, k=len(vs.docstore._dict)))
    # 2) embed query once
    q_vec = EMBED_MODEL.embed_query(query)
    # 3) compute tag-sims
    tag_sims = []
    for doc in docs:
        name = doc.metadata["club_name"]
        t_vec = tag_embeds.get(name)
        if t_vec is None:
            # fallback to 0 similarity
            tag_sims.append(0.0)
        else:
            tag_sims.append(
                np.dot(q_vec, t_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(t_vec))
            )
    # 4) convert distances to a "blurb similarity" in [0,1]
    blurb_sims = [1.0 / (1.0 + d) for d in dists]
    # 5) combined score: higher = better
    combined = [alpha * b + (1 - alpha) * t for b, t in zip(blurb_sims, tag_sims)]
    # 6) pick top-k by combined
    idx = np.argsort(combined)[-k:][::-1]
    return [(docs[i], combined[i]) for i in idx]

def alpha_weighted(vs, tag_embeds, query, k=5, alpha=0.8):
    """
    Shortcut for dual_similarity with your preferred alpha.
    """
    return dual_similarity(vs, tag_embeds, query, k=k, alpha=alpha)

# Recommending clubs based on student parameters
def parse_club_topics_from_student_response(prompt, major, parameter, parameter_response):
    """
    Parses topics from student response for a given parameter in initial form.

    Args:
        prompt (PromptTemplate): Prompt template to use.
        major (str): Student's major.
        parameter (str): Parameter currently being parsed.
        parameter_response (str): Response to supply to prompt.

    Returns:
        list[str]: List of topics.
    """
    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    chain = prompt | llm
    response = chain.invoke({"major": major, parameter: parameter_response})
    response_text = response.content if hasattr(response, 'content') else str(response)
    topics = [t.strip() for t in response_text.split(",")]
    return topics

def get_club_recommendations(major, student_parameter_data):
    # Load vectorstore & tag embeddings
    vectorstore = load_club_vector_store(
        vectorstore_name="all_clubs",
        clubs_json_path="data/club_data_with_tags.json"
    )
    tag_embeds = build_tag_embeddings("data/club_data_with_tags.json")

    # Initialize defaultdict to store club recommendations - use dict instead of list
    club_recommendations = defaultdict(dict)
    club_metadata = {}

    # Iterate over each parameter and extract topics
    for parameter, parameter_response_text in student_parameter_data.items():
        # Get the appropriate prompt for this parameter
        if parameter not in PARAMETER_TO_PROMPT_MAP:
            print(f"Warning: No prompt found for parameter '{parameter}'. Skipping.")
            continue
            
        specific_prompt = PARAMETER_TO_PROMPT_MAP[parameter]
        
        # Extracting topics from student response
        prompt = PromptTemplate(
            input_variables=["major", parameter],
            template=specific_prompt
        )
        topics = parse_club_topics_from_student_response(prompt, major, parameter, parameter_response_text)
        topics_concat = ", ".join(topics)
        print(f"{parameter} --> {topics_concat}")

        # Retrieving club recommendations
        print("\n>> ALPHA-WEIGHTED (alpha=0.8):")
        parameter_recommendations = alpha_weighted(vectorstore, tag_embeds, topics_concat, alpha=0.8)
        for doc, score in parameter_recommendations:
            print(f"{doc.metadata['club_name']}: {score:.3f}")
            club_recommendations[doc.metadata['club_name']][parameter] = score
            club_metadata[doc.metadata['club_name']] = doc.metadata

        print("=" * 50)

    return club_recommendations, club_metadata

if __name__ == "__main__":
    # Sample responses
    sample_response = {
        "college_interests": "within CS, applied AI, cutting-edge developments, more deep things like OS, compilers; outside CS, I'm passionate about exploring international relations and history, middle eastern studies and contemporary conflicts and potentially writing articles on the topics.",
        "post_grad_goal": "work as a software engineer at an AI or cutting-edge tech startup or FAANG-like company, or build a startup and pursue entrepreneurship; could also engage in grad school to equip myself with important domain knowledge and delay the mentioned options to after",
        "long_term_goal": "I want to become a successful serial entrepreneur and maybe dabble in VC, becoming a leader in AI and impactful applications of it, specifically by being a pioneer in AI and employing it in meaningful ways"
    }

    print(get_club_recommendations("Computer Science", sample_response))
    