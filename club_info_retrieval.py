from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import json
import os
import numpy as np
from club_matching_prompts import *
from dotenv import load_dotenv

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = OpenAIEmbeddings(api_key=openai_api_key)

def produce_club_name(club_description):
    prompt = PromptTemplate(
        input_variables=["club_description"],
        template=PRODUCE_CLUB_NAME_PROMPT
    )

    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    chain = prompt | llm
    response = chain.invoke({"club_description": club_description})
    club_name = response.content if hasattr(response, 'content') else str(response)
    return club_name

def produce_club_tags(club_description):
    prompt = PromptTemplate(
        input_variables=["club_description"],
        template=PRODUCE_CLUB_TAGS_PROMPT
    )

    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    chain = prompt | llm
    response = chain.invoke({"club_description": club_description})
    response_text = response.content if hasattr(response, 'content') else str(response)
    tags = [t.strip() for t in response_text.split(",")]
    return tags


def create_club_vector_store(club_data, vectorstore_name):
    """
    Creates (and saves) a FAISS vector store from a list of club dicts.

    Args:
        club_data (list[dict]): Each dict should have at least:
            - 'club_name'
            - 'organization_blurb'
            - 'tags' (list[str])
            - optionally 'category', 'url', etc.
        vectorstore_name (str): folder name under ./vectorstores/

    Returns:
        FAISS: the in-memory vectorstore.
    """
    # 1. Turn each club into a Document
    docs = []
    for club_category in club_data:
        for club in club_data[club_category]:
            # Combine blurb + tags into a single text chunk:
            description = club['organization_blurb'].strip()
            if club.get('tags'):
                description += "\n\nTags: " + ", ".join(club['tags'])

            metadata = {
                'club_name': club['club_name'],
                'club_category': club_category,
                'club_blurb': club['organization_blurb'],
                'tags': club['tags'],
                'urls': club.get('urls', [])
            }
            docs.append(Document(page_content=description, metadata=metadata))

    # 2. Embed & index
    vectorstore = FAISS.from_documents(docs, EMBED_MODEL)

    # 3. Persist
    os.makedirs("vectorstores", exist_ok=True)
    vectorstore.save_local(f"vectorstores/{vectorstore_name}")

    return vectorstore

def load_club_vector_store(vectorstore_name, clubs_json_path):
    """
    Load an existing FAISS store or build a new one from your JSON file.

    Args:
        vectorstore_name (str): the folder under ./vectorstores/
        clubs_json_path (str): path to your club_data_with_tags.json

    Returns:
        FAISS
    """
    vs_dir = f"vectorstores/{vectorstore_name}"
    if os.path.isdir(vs_dir):
        return FAISS.load_local(vs_dir, OpenAIEmbeddings(api_key=openai_api_key), allow_dangerous_deserialization=True)
    else:
        with open(clubs_json_path, 'r') as f:
            clubs = json.load(f)
        return create_club_vector_store(clubs, vectorstore_name)

def build_tag_embeddings(clubs_json_path):
    """
    Precompute and return a dict: { club_name: tag_embedding_vector }.
    """
    clubs = json.load(open(clubs_json_path))
    tag_embeds = {}
    for club_category in clubs:
        for club in clubs[club_category]:
            tags = club.get("tags", [])
            if tags:
                # produce one vector for the comma-joined tag list
                vec = EMBED_MODEL.embed_documents([", ".join(tags)])[0]
                tag_embeds[club["club_name"]] = vec
    return tag_embeds

if __name__ == "__main__":
    club_descriptions = json.load(open('data/club_data.json'))
    augment_club_data = False
    build_vector_store = True
    
    # Produce tags for each club if not already present
    if augment_club_data:
        for club_category in club_descriptions:
            for club in club_descriptions[club_category]:
                if 'club_name' not in club:
                    club['club_name'] = produce_club_name(club['organization_blurb'])
                print(f"Club name: {club['club_name']}")

            if 'tags' not in club:
                description = club['organization_blurb']
                print(f"{description[:500]}...")
                tags = produce_club_tags(description)
                print(f"\nTags: {tags}\n--")

                club['tags'] = tags

        json.dump(club_descriptions, open('data/club_data_with_tags.json', 'w'))

    # Build vector store
    if build_vector_store:
        club_description_augmented = json.load(open('data/club_data_with_tags.json'))

        create_club_vector_store(club_description_augmented, vectorstore_name="all_clubs")
