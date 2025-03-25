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
    vectorstore_name = vectorstore_name_raw.replace(" ", "_").lower()

     # Check if we have cached course data
    if os.path.exists(f'{vectorstore_name}_courses_with_descriptions.csv'):
        courses_with_descriptions_df = pd.read_csv(f'{vectorstore_name}_courses_with_descriptions.csv')
        courses_with_descriptions = courses_with_descriptions_df.to_dict('records')
    else:
        # If not, fetch course data
        courses_with_descriptions = produce_courses_for_major(vectorstore_name_raw)

        if courses_with_descriptions:
            courses_with_descriptions_df = pd.DataFrame(courses_with_descriptions)
            courses_with_descriptions_df.to_csv(f'{vectorstore_name}_courses_with_descriptions.csv', index=False)
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
    # Perform a semantic search
    results = vectorstore.similarity_search(query, k=k)

    print('--------------------------------')
    print('Query: ', query)

    course_codes = [doc.metadata.get('course_code') for doc in results]
    print(course_codes)
    return course_codes

def parse_topics_from_student_response(prompt, major, parameter, parameter_response):
    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    chain = prompt | llm
    response = chain.invoke({"major": major, parameter: parameter_response})
    response_text = response.content if hasattr(response, 'content') else str(response)
    topics = [t.strip() for t in response_text.split(",")]
    return topics

def get_departments_for_topic(topic, score_cutoff=80):
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
    known_departments = pd.read_csv("dartmouth_majors.csv")["Major"].tolist()
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
    courses_for_search_areas = Counter()

    for area in search_areas:
        courses_for_area = semantic_search(vectorstore, area)
        courses_for_search_areas.update(courses_for_area)

    return courses_for_search_areas

def get_courses_for_parameter(major, parameter, parameter_response):
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
    ranked_courses = sorted(course_recommendation_details.items(), key=lambda x: x[1]['total_count'], reverse=True)
    return ranked_courses

def get_skills_for_post_grad_goal(post_grad_goal_text):
    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    prompt = PromptTemplate(
        input_variables=["post_grad_goal"],
        template="""

    Context:
    A student has expressed interest in the following after graduating: 
    
    "{post_grad_goal}". 
    --
    Task:

    What are 5 specific technical or academic topics they should study in college? 
    These can include tools, concepts, or technologies that directly support their goal.
    Return only a comma-separated list of the topics.
    """
    )

    # Replace LLMChain with RunnableSequence (prompt | llm)
    chain = prompt | llm
    response = chain.invoke({"post_grad_goal": post_grad_goal_text})
    
    # Extract content from the response object
    response_text = response.content if hasattr(response, 'content') else str(response)
    topics = [t.strip() for t in response_text.split(",")]

    return topics

def get_skills_for_long_term_goal(long_term_goal_text):
    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    prompt = PromptTemplate(
        input_variables=["long_term_goal"],
        template="""

    Context:
    A student has expressed the following interest in the following long-term career aspirations:
    
    "{long_term_goal}". 
    --
    Task:

    What are 5 specific technical or academic topics they should study in college? 
    These can include tools, concepts, or technologies that directly support their aspirations, including more abstract areas that may support leadership, policy-making, research, etc.
    Return only a comma-separated list of the topics.
    """
    )

    chain = prompt | llm
    response = chain.invoke({"long_term_goal": long_term_goal_text})
    response_text = response.content if hasattr(response, 'content') else str(response)
    topics = [t.strip() for t in response_text.split(",")]
    return topics

def get_courses_across_student_parameters(student_parameters, vectorstore):
    parameter_course_counts = {}
    all_unique_courses = set()

    # Get recommended courses (and counts) for each parameter (e.g. college interests, post-grad goal, etc.)
    for parameter, parameter_search_areas in student_parameters.items():
        print(f"\nGetting courses for {parameter}...")
        if parameter == 'college_interests':
            courses_for_parameter_areas = get_courses_for_parameter_search_areas(parameter_search_areas, vectorstore)
        elif parameter == 'post_grad_goal':
            skills = get_skills_for_post_grad_goal(student_parameters['post_grad_goal'])
            print(f"--> Skills for post-grad goal: {skills}")

            courses_for_parameter_areas = get_courses_for_parameter_search_areas(skills, vectorstore)
        elif parameter == 'long_term_goal':
            skills = get_skills_for_long_term_goal(student_parameters['long_term_goal'])
            print(f"--> Skills for long-term aspirations: {skills}")

            courses_for_parameter_areas = get_courses_for_parameter_search_areas(skills, vectorstore)
        else:
            raise ValueError(f"Invalid parameter: {parameter}")

        parameter_course_counts[parameter] = courses_for_parameter_areas
        all_unique_courses.update(courses_for_parameter_areas)

    # Get all unique courses and their counts (by parameter, total)
    print(f'Producing course recommendation details...')
    course_recommendation_details = {}
    for course_code in all_unique_courses:
        total_count = 0

        for parameter in parameter_course_counts:
            if parameter=='long_term_goal':
                total_count += parameter_course_counts[parameter][course_code] * 0.5
            else:
                total_count += parameter_course_counts[parameter][course_code]
        
        course_recommendation_details[course_code] = {
            'total_count': total_count,
            'parameter_counts': {parameter: parameter_course_counts[parameter][course_code] for parameter in parameter_course_counts}
        }

    return course_recommendation_details

if __name__ == "__main__":

    # example_major = 'Computer Science'

    # example_student_parameters = {
    #     'college_interests': 'cybersecurity, cloud computing, artificial intelligence and security',
    #     'post_grad_goal': 'data scientist and machine learning engineer',
    #     'long_term_goal': 'Lead the development of ethical, large-scale AI systems that enhance global cybersecurity infrastructure and advocate for responsible AI use in government or corporate policy.'
    # }

    # major_course_recs, other_course_recs, all_unique_courses, course_to_department_map = get_courses_for_student_parameters(example_major, example_student_parameters)
    # scored_major_course_recs, scored_other_course_recs = score_recommended_courses(major_course_recs, other_course_recs, all_unique_courses)

    # ranked_major_course_recs = rank_recommended_courses(scored_major_course_recs)
    # ranked_other_course_recs = rank_recommended_courses(scored_other_course_recs)

    # print('--------------------------------')
    # print(ranked_major_course_recs)
    # print(ranked_other_course_recs)
    # print(course_to_department_map)

    # testing fuzzy matching with Studio Art
    llm_output_dept = "'Studio Art'"
    known_departments = pd.read_csv("dartmouth_majors.csv")["Major"].tolist()
    match, score, _ = process.extractOne(
        llm_output_dept, known_departments, scorer=fuzz.token_sort_ratio
    )
    print(f'Top match: {match}; score: {score}')