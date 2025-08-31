import os
import pandas as pd
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from dotenv import load_dotenv
import os
from dreampath_processing.courses.college_info_retrieval import produce_courses_for_major

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

def create_vector_store(courses_with_descriptions, vectorstore_name):
    """
    Creates vector store for set of courses associated with a department.

    Args:
        courses_with_descriptions (list[dict]): List of dictionaries, each containing course information.
        vectorstore_name (str): Name of the vector store.

    Returns:
        FAISS: Vector store for the courses.
    """
    # Create embeddings for the course descriptions
    docs = [
        Document(page_content=course['description'],
                 metadata={'course_title': course['course_title'],
                           'course_code': course['course_code'],
                           'course_url': course['course_url'],
                           'prerequisites': course['prerequisites'],
                           'degree_req': course['degree_req']})
        for course in courses_with_descriptions
    ]

    # Create a FAISS vector store
    embedding_model = OpenAIEmbeddings(api_key=openai_api_key)
    vectorstore = FAISS.from_documents(docs, embedding_model)
    vectorstore.save_local(f"vectorstores/{vectorstore_name}")
    return vectorstore  # Return the created vectorstore

def load_vector_store(vectorstore_name_raw):
    """
    Loads vector store for set of courses associated with a department. Either loads from cache or creates new vector store.

    Args:
        vectorstore_name_raw (str): Name of the department.

    Returns:
        FAISS: Vector store for the courses.
    """
    vectorstore_name = vectorstore_name_raw.replace(" ", "_").lower()

     # Check if we have cached course data
    if os.path.exists(f'dreampath_processing/courses/data/{vectorstore_name}_courses_with_descriptions.csv'):
        courses_with_descriptions_df = pd.read_csv(f'dreampath_processing/courses/data/{vectorstore_name}_courses_with_descriptions.csv')
        courses_with_descriptions = courses_with_descriptions_df.to_dict('records')
    else:
        # If not, fetch course data
        courses_with_descriptions = produce_courses_for_major(vectorstore_name_raw)

        if courses_with_descriptions:
            courses_with_descriptions_df = pd.DataFrame(courses_with_descriptions)
            courses_with_descriptions_df.to_csv(f'dreampath_processing/courses/data/{vectorstore_name}_courses_with_descriptions.csv', index=False)
        else:
            print(f"No courses found for {vectorstore_name_raw}")
            return None

    # Create or load vector store
    if not os.path.exists(f'vectorstores/{vectorstore_name}'):
        os.makedirs('vectorstores', exist_ok=True)
        vectorstore = create_vector_store(courses_with_descriptions=courses_with_descriptions, vectorstore_name=vectorstore_name)
    else:
        vectorstore = FAISS.load_local(f"vectorstores/{vectorstore_name}", OpenAIEmbeddings(api_key=openai_api_key), allow_dangerous_deserialization=True)

    return vectorstore

def semantic_search(vectorstore, query, k=5, verbose=False):
    """
    Performs semantic search on a vector store for courses associated with a department.

    Args:
        vectorstore (FAISS): Vector store to search.
        query (str): Query to search for.
        k (int): Number of results to return.

    Returns:
        list[str]: List of course codes.
    """
    # Perform a semantic search
    results = vectorstore.similarity_search(query, k=k)

    if verbose:
        print('--------------------------------')
        print('Query: ', query)

    course_codes = [doc.metadata.get('course_code') for doc in results]
    if verbose:
        print(course_codes)
        
    return course_codes