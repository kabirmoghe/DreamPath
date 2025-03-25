import pandas as pd
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from collections import Counter
from langchain.schema import Document
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
from prompts import *
from college_info_retrieval import produce_courses_for_major
from rapidfuzz import process, fuzz

# Set the OpenAI API key
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
    if os.path.exists(f'data/{vectorstore_name}_courses_with_descriptions.csv'):
        courses_with_descriptions_df = pd.read_csv(f'data/{vectorstore_name}_courses_with_descriptions.csv')
        courses_with_descriptions = courses_with_descriptions_df.to_dict('records')
    else:
        # If not, fetch course data
        courses_with_descriptions = produce_courses_for_major(vectorstore_name_raw)

        if courses_with_descriptions:
            courses_with_descriptions_df = pd.DataFrame(courses_with_descriptions)
            courses_with_descriptions_df.to_csv(f'data/{vectorstore_name}_courses_with_descriptions.csv', index=False)
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

def semantic_search(vectorstore, query, k=5):
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

    print('--------------------------------')
    print('Query: ', query)

    course_codes = [doc.metadata.get('course_code') for doc in results]
    print(course_codes)
    return course_codes

def parse_topics_from_student_response(prompt, major, parameter, parameter_response):
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

def get_departments_for_topic(topic, score_cutoff=80):
    """
    Gets departments for a given topic.

    Args:
        topic (str): Topic to search for.
        score_cutoff (int): Score cutoff for fuzzy matching.

    Returns:
        list[str]: List of departments.
    """
    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    prompt = PromptTemplate(
        input_variables=["topic"],
        template=DEPARTMENT_MATCHING_PROMPT
    )

    chain = prompt | llm
    response = chain.invoke({"topic": topic})
    response_text = response.content if hasattr(response, 'content') else str(response)

    # Processes departments from response
    raw_departments = [t.strip() for t in response_text.split(",")]
    known_departments = pd.read_csv("data/dartmouth_majors.csv")["Major"].tolist()
    departments = []

    for department in raw_departments:
        match, score, _ = process.extractOne(
            department.strip("'"), known_departments, scorer=fuzz.token_sort_ratio
        )
        if score >= score_cutoff:
            departments.append(match)
        else:
            print(f'No match found for {department}.')
    
    return departments

def get_courses_for_parameter_search_areas(search_areas, vectorstore):
    """
    Gets courses for a given set of search areas/topics.

    Args:
        search_areas (list[str]): List of search areas/topics.
        vectorstore (FAISS): Vector store to search.

    Returns:
        Counter: Counter of courses for each search area.
    """
    courses_for_search_areas = Counter()

    for area in search_areas:
        courses_for_area = semantic_search(vectorstore, area)
        courses_for_search_areas.update(courses_for_area)

    return courses_for_search_areas

def get_courses_for_parameter(major, parameter, parameter_response):
    """
    Gets courses for a given parameter (college interests, post-graduation goal, long term career goal).

    Args:
        major (str): Student's major.
        parameter (str): Parameter currently being parsed.
        parameter_response (str): Response to supply to prompt.

    Returns:
        Counter: Counter of courses for each search area.
    """
    if parameter == 'college_interests':
        prompt_template = PARSE_TOPICS_FOR_STUDENT_INTERESTS_PROMPT
    elif parameter == 'post_grad_goal':
        prompt_template = PARSE_TOPICS_FOR_POST_GRAD_GOAL_PROMPT
    elif parameter == 'long_term_goal':
        prompt_template = PARSE_TOPICS_FOR_LONG_TERM_GOAL_PROMPT
    else:
        raise ValueError(f"Invalid parameter: {parameter}")
    
    prompt = PromptTemplate(
        input_variables=[parameter, 'major'],
        template=prompt_template
    )

    # Parses topics from student response
    topics_for_parameter = parse_topics_from_student_response(prompt, major, parameter, parameter_response)    

    # Maps topics to departments
    topics_to_departments = {}
    for topic in topics_for_parameter:
        departments = get_departments_for_topic(topic)
        topics_to_departments[topic] = departments

    print(f'For parameter {parameter}:\n\ttopics to departments: {topics_to_departments}')

    major_courses_for_parameter = Counter()
    other_courses_for_parameter = Counter()

    # Keeps track of which department each course belongs to
    course_to_department_map = {}

    # Outputting topics' map to departments
    for topic, departments in topics_to_departments.items():
        print(f"Topic: {topic} --> Departments: {departments}")
        
        major_courses_for_topic = Counter()
        other_courses_for_topic = Counter()

        # Get courses for each department
        for department in departments:
            try:
                vectorstore = load_vector_store(department)
            except Exception as e:
                print(f'Error loading vectorstore for {department}: {e}')
                continue

            if vectorstore is None:
                print(f"No vectorstore found for {department}... Skipping.")
                continue
            
            courses_for_department = get_courses_for_parameter_search_areas([topic], vectorstore)

            for course_code in courses_for_department:
                course_to_department_map[course_code] = department
            
            if department == major:
                major_courses_for_topic.update(courses_for_department)
            else:
                other_courses_for_topic.update(courses_for_department)

        major_courses_for_parameter.update(major_courses_for_topic)
        other_courses_for_parameter.update(other_courses_for_topic)

    return major_courses_for_parameter, other_courses_for_parameter, course_to_department_map

def get_courses_for_student_parameters(major, student_parameter_data):
    """
    Gets courses across all parameters for a given student.

    Args:
        major (str): Student's major.
        student_parameter_data (dict): Dictionary of student parameters.

    Returns:
        tuple: Tuple containing major course counts, other course counts, all unique courses, and course to parent department map.
    """
    major_parameter_course_counts = {}
    other_parameter_course_counts = {}
    all_unique_courses = set()
    all_course_to_department_map = {}

    # Iterates over each parameter and extracts courses for each
    for parameter, parameter_response_text in student_parameter_data.items():
        major_courses_for_parameter, other_courses_for_parameter, course_to_department_map = get_courses_for_parameter(major, parameter, parameter_response_text)

        # Add to major and other course counts
        major_parameter_course_counts[parameter] = major_courses_for_parameter
        other_parameter_course_counts[parameter] = other_courses_for_parameter

        # Add to all unique courses
        all_unique_courses.update(major_courses_for_parameter)
        all_unique_courses.update(other_courses_for_parameter)

        # Add to course to department map
        all_course_to_department_map.update(course_to_department_map)
    
    return major_parameter_course_counts, other_parameter_course_counts, all_unique_courses, all_course_to_department_map

def score_recommended_courses(major_parameter_course_counts, other_parameter_course_counts, all_unique_courses):
    """
    Scores courses across all parameters for a given student.

    Args:
        major_parameter_course_counts (dict): Dictionary of major course counts.
        other_parameter_course_counts (dict): Dictionary of other course counts.
        all_unique_courses (set): Set of all unique courses.

    Returns:
        tuple: Tuple containing major course recommendation details and other course recommendation details.
    """
    print(f'Producing course recommendation details...')
    major_course_recommendation_details = {}
    other_course_recommendation_details = {}

    for course_code in all_unique_courses:
        major_count = 0
        other_count = 0

        for parameter in major_parameter_course_counts:
            if parameter=='long_term_goal':
                major_count += major_parameter_course_counts[parameter][course_code] * 0.5
            else:
                major_count += major_parameter_course_counts[parameter][course_code]

        for parameter in other_parameter_course_counts:
            if parameter=='long_term_goal':
                other_count += other_parameter_course_counts[parameter][course_code] * 0.5
            else:
                other_count += other_parameter_course_counts[parameter][course_code]
        
        major_course_recommendation_details[course_code] = {
            'total_count': major_count,
            'parameter_counts': {parameter: major_parameter_course_counts[parameter][course_code] for parameter in major_parameter_course_counts}
        }

        other_course_recommendation_details[course_code] = {
            'total_count': other_count,
            'parameter_counts': {parameter: other_parameter_course_counts[parameter][course_code] for parameter in other_parameter_course_counts}
        }

    return major_course_recommendation_details, other_course_recommendation_details

def rank_recommended_courses(course_recommendation_details):
    """
    Ranks courses across all parameters for a given student.

    Args:
        course_recommendation_details (dict): Dictionary of course recommendation details.

    Returns:
        list[tuple]: List of tuples containing course code and recommendation details.
    """
    ranked_courses = sorted(course_recommendation_details.items(), key=lambda x: x[1]['total_count'], reverse=True)
    return ranked_courses

if __name__ == "__main__":
    pass