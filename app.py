from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from semantic_course_search import *
from college_info_retrieval import produce_courses_for_major
from build_major_course_path import retrieve_enhanced_course_from_course_code, build_course_path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
# Only allow requests from frontend
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

@app.route('/api/majors', methods=['GET'])
def get_majors():
    # Return list of available majors
    available_majors = [
        "African and African American Studies", 
        "Biological Sciences", 
        "Biophysical Chemistry",
        "Cognitive Science",
        "Computer Science",
        "Economics",
        "Engineering Sciences",
        "English",
        "Government",
        "Mathematics",
        "Philosophy",
        "Psychology",
        "Studio Art"
    ]
    print(f"Available majors: {available_majors}")
    return jsonify(available_majors)

@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    data = request.json
    major = data.get('major')
    college_interests = data.get('collegeInterests', '')
    post_grad_goal = data.get('postGradGoal', '')
    long_term_goal = data.get('longTermGoal', '')
    
    print(f"Major: {major}")
    print(f"College interests: {college_interests}")
    print(f"Post-grad goal: {post_grad_goal}")
    print(f"Long-term goal: {long_term_goal}")

    # Clean major name for file paths
    major_cleaned = major.replace(" ", "_").lower()
    print(f"Major cleaned: {major_cleaned}")

    # Prepare student parameters
    student_parameters = {
        'college_interests': college_interests,
        'post_grad_goal': post_grad_goal,
        'long_term_goal': long_term_goal
    }
    
    # Get course recommendations
    major_course_recs, other_course_recs, all_unique_courses, all_course_to_department_map = get_courses_for_student_parameters(major, student_parameters)
    scored_major_course_recs, scored_other_course_recs = score_recommended_courses(major_course_recs, other_course_recs, all_unique_courses)

    ranked_major_course_recs = rank_recommended_courses(scored_major_course_recs)
    ranked_other_course_recs = rank_recommended_courses(scored_other_course_recs)
    
    # Format major course recommendations
    major_courses_with_descriptions_df = pd.read_csv(f'data/{major_cleaned}_courses_with_descriptions.csv')
    major_recommendations = []
    major_recommendations_map = {}
    for course_code, details in ranked_major_course_recs[:10]:
        formatted_course = format_course(course_code, major_courses_with_descriptions_df, details)
        if formatted_course:
            major_recommendations.append(formatted_course)
            major_recommendations_map[course_code] = formatted_course

    # Format complementary course recommendations
    complementary_recommendations = []
    complementary_recommendations_map = {}
    for course_code, details in ranked_other_course_recs[:10]:
        formatted_course = format_course(course_code, courses_df=None, details=details)
        if formatted_course:
            complementary_recommendations.append(formatted_course)
            complementary_recommendations_map[course_code] = formatted_course

    # Get course codes
    major_courses = [course['courseCode'] for course in major_recommendations]
    complementary_courses = [course['courseCode'] for course in complementary_recommendations]
    
    print(f"Produced major courses --> {major_courses}")
    print(f"Produced complementary courses --> {complementary_courses}")

    # Build course path and enhance course codes with catalog information
    course_codes_path, all_major_course_codes, all_complementary_course_codes = build_course_path(major_courses, complementary_courses)
    course_path = []

    for term in course_codes_path:
        term_courses = []
        for course_code in term:
            print(course_code)

            formatted_course = None

            # Check if course is a major recommendation and/or a prerequisite
            if course_code in all_major_course_codes:
                if course_code in major_recommendations_map:
                    formatted_course = major_recommendations_map[course_code]

                    # Rename scores
                    formatted_course['majorTotalScore'] = formatted_course['totalScore']
                    formatted_course['majorParameterScores'] = formatted_course['parameterScores']
                    del formatted_course['totalScore']
                    del formatted_course['parameterScores']
                else:
                    formatted_course = format_course(course_code)
                    formatted_course['isPrerequisite'] = True
                formatted_course['isMajor'] = True
                
            # Check if course is a complementary recommendation and/or a prerequisite
            if course_code in all_complementary_course_codes:
                if course_code in complementary_recommendations_map:
                    temp_course = complementary_recommendations_map[course_code]

                    # In case complementary course is not a major recommendation, format it
                    if formatted_course is None:
                        formatted_course = temp_course

                    # Rename scores
                    formatted_course['complementaryTotalScore'] = formatted_course['totalScore']
                    formatted_course['complementaryParameterScores'] = formatted_course['parameterScores']
                    del formatted_course['totalScore']
                    del formatted_course['parameterScores']
                else:
                    # In case complementary course is not a major recommendation, format it
                    if formatted_course is None:
                        formatted_course = format_course(course_code)

                    formatted_course['isPrerequisite'] = True
                formatted_course['isComplementary'] = True

            # Backup defaults
            formatted_course.setdefault('isMajor', False)
            formatted_course.setdefault('isComplementary', False)
            formatted_course.setdefault('isPrerequisite', False)
            term_courses.append(formatted_course)
        
        course_path.append(term_courses)

    return jsonify({
        'majorRecommendations': major_recommendations,
        'complementaryRecommendations': complementary_recommendations,
        'coursePath': course_path
    })

# Course formatting
def format_course(course_code, courses_df=None, details=None):
    # If department courses dataframe is provided, use it; otherwise produce course information
    if courses_df is None:
        course_info = retrieve_enhanced_course_from_course_code(course_code)
    else:
        course_info = courses_df[courses_df['course_code'] == course_code].iloc[0]

    if course_info.empty:
        return None
    
    # Format course depending on if recommended or prereq on DreamPath
    prerequisites = None
    if 'prerequisites' in course_info and not pd.isna(course_info['prerequisites']):
        prerequisites = course_info['prerequisites']

    degree_req = None
    if 'degree_req' in course_info and not pd.isna(course_info['degree_req']):
        degree_req = course_info['degree_req']

    formatted_course_info = {
        'courseCode': course_code,
        'courseTitle': ' '.join(course_info['course_title'].split()[2:]),
        'description': course_info['description'],
        'prerequisites': prerequisites,
        'degreeReq': degree_req
    }

    # If scoring details are provided (i.e. recommended course), include in response
    if details is not None:
        parameter_scores = {}

        for param, score in details['parameter_counts'].items():
            parameter_scores[param] = None if pd.isna(score) else score

        formatted_course_info['totalScore'] = None if pd.isna(details['total_count']) else details['total_count']
        formatted_course_info['parameterScores'] = parameter_scores

    return formatted_course_info

if __name__ == '__main__':
    app.run(debug=True, port=5001)
