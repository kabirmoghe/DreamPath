import pandas as pd
from collections import Counter
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
import re
from rapidfuzz import process, fuzz
from dreampath_processing.courses.prompts.course_matching_prompts import *
from dreampath_processing.courses.course_vector_db_ops import *
from dreampath_processing.courses.course_relationship_handling import get_department_alias_from_dept_name, get_department_from_course_code

# Set the OpenAI API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# ================================
# Modular extraction of courses for topics
# ================================

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

    raw_departments = [t.strip() for t in re.findall(r"'(.*?)'", response_text)]
    known_departments = pd.read_csv("dreampath_processing/courses/data/dartmouth_majors.csv")["Major"].tolist()
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

def get_courses_for_topic(topic, major, major_comp_split=0.75, num_courses=8, verbose=False):
    llm = ChatOpenAI(temperature=0, model="gpt-4o")

    # Extract subtopics from topic
    prompt = PromptTemplate(
    input_variables=["topic"],
    template=SUBTOPIC_EXTRACTION_PROMPT
)

    chain = prompt | llm
    response = chain.invoke({"topic": topic})
    response_text = response.content if hasattr(response, 'content') else str(response)

    subtopics = [t.strip() for t in response_text.split(",")]

    # Get major and complementary course counts for topic
    major_alias = get_department_alias_from_dept_name(major)
    major_course_counts = Counter()
    complementary_course_counts = Counter()

    for subtopic in subtopics:
        depts = get_departments_for_topic(subtopic)
        if verbose:
            print(f'* Subtopic: {subtopic} --> Departments: {depts}')

        for dept in depts:
            vectorstore = load_vector_store(dept)
            courses_for_dept = get_courses_for_parameter_search_areas([subtopic], vectorstore)
            if verbose:
                print(f'Department: {dept} --> Courses: {courses_for_dept}')

            # Get dept alias for each course
            for course in courses_for_dept:
                dept_alias, _ = get_department_from_course_code(course)
                if dept_alias == major_alias:
                    major_course_counts.update([course])
                else:
                    complementary_course_counts.update([course])

    num_major_courses = int(num_courses * major_comp_split)
    topic_major_courses = [course for course, _ in major_course_counts.most_common(num_major_courses)]
    topic_comp_courses = [course for course, _ in complementary_course_counts.most_common(num_courses - num_major_courses)]

    return topic_major_courses, topic_comp_courses

# ================================
# Extracting courses for parameters
# ================================

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

def score_recommended_courses(major_parameter_course_counts, other_parameter_course_counts, all_unique_courses, parameter_weights=None):
    """
    Scores courses across all parameters for a given student.

    Args:
        major_parameter_course_counts (dict): Dictionary of major course counts.
        other_parameter_course_counts (dict): Dictionary of other course counts.
        all_unique_courses (set): Set of all unique courses.
        parameter_weights (dict, optional): Dictionary of weights for each parameter.
            Should contain keys: 'college_interests', 'post_grad_goal', 'long_term_goal'
            Values should be in range [0,1]. At least one must be > 0.
            Defaults to {'college_interests': 1.0, 'post_grad_goal': 1.0, 'long_term_goal': 0.5}.

    Returns:
        tuple: Tuple containing major course recommendation details and other course recommendation details.
    """
    # Set default weights if none provided
    if parameter_weights is None:
        parameter_weights = {
            'college_interests': 1.0,
            'post_grad_goal': 1.0,
            'long_term_goal': 0.5
        }
    
    # Validate parameter weights
    valid_parameters = {'college_interests', 'post_grad_goal', 'long_term_goal'}
    
    # Check that all provided weights are for valid parameters
    for param in parameter_weights:
        if param not in valid_parameters:
            raise ValueError(f"Invalid parameter '{param}' in parameter_weights. Valid parameters: {valid_parameters}")
    
    # Check that weights are in valid range [0,1]
    for param, weight in parameter_weights.items():
        if not (0 <= weight <= 1):
            raise ValueError(f"Weight for '{param}' must be in range [0,1], got {weight}")
    
    # Check that at least one weight is > 0
    if not any(weight > 0 for weight in parameter_weights.values()):
        raise ValueError("At least one parameter weight must be greater than 0")
    
    # Ensure all parameters have weights (use defaults for missing ones)
    for param in valid_parameters:
        if param not in parameter_weights:
            if param == 'long_term_goal':
                parameter_weights[param] = 0.5
            else:
                parameter_weights[param] = 1.0
    
    print(f'Producing course recommendation details with weights: {parameter_weights}')
    major_course_recommendation_details = {}
    other_course_recommendation_details = {}

    for course_code in all_unique_courses:
        major_count = 0
        other_count = 0

        for parameter in major_parameter_course_counts:
            weight = parameter_weights.get(parameter, 1.0)
            major_count += major_parameter_course_counts[parameter][course_code] * weight

        for parameter in other_parameter_course_counts:
            weight = parameter_weights.get(parameter, 1.0)
            other_count += other_parameter_course_counts[parameter][course_code] * weight
        
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
    # Testing course extraction for hard-coded topics

    ai_topics = ["Machine Learning", "Deep Learning", "Natural Language Processing", "Reinforcement Learning", "Computer Vision", "Generative AI", "Large Language Models"]

    major_course_counts, other_course_counts = get_courses_for_topic(topic="Robotics and computer vision", major="Computer Science")
    print(f"Major courses: {major_course_counts}")
    print(f"Other courses: {other_course_counts}")
    # course_counts = Counter()

    # for topic in ai_topics:
    #     print('========================================')
    #     print(f'Topic: {topic}')
    #     topic_depts = get_departments_for_topic(topic)
    #     print(f'Topic: {topic} --> Departments: {topic_depts}')

    #     for dept in topic_depts:
    #         if dept == "Cognitive Science":
    #             continue
            
    #         vectorstore = load_vector_store(dept)
    #         courses_for_dept = get_courses_for_parameter_search_areas([topic], vectorstore)
    #         print(f'Department: {dept} --> Courses: {courses_for_dept}')

    #         course_counts.update(courses_for_dept)

    # print(f'Course counts: {course_counts.most_common(10)}')
