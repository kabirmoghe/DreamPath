from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from semantic_course_search import *
from college_info_retrieval import produce_courses_for_major
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
    print(f"Major cleaned: {major}")

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
    
    # Format recommendations 
    major_recommendations = []
    major_courses_with_descriptions_df = pd.read_csv(f'data/{major_cleaned}_courses_with_descriptions.csv')
    for course_code, details in ranked_major_course_recs[:10]:
        course_info = major_courses_with_descriptions_df[major_courses_with_descriptions_df['course_code'] == course_code]
        if not course_info.empty:
            # Convert NaN values to None (which becomes null in JSON)
            prerequisites = None
            if 'prerequisites' in course_info and not pd.isna(course_info['prerequisites'].iloc[0]):
                prerequisites = course_info['prerequisites'].iloc[0]
                
            degree_req = None
            if 'degree_req' in course_info and not pd.isna(course_info['degree_req'].iloc[0]):
                degree_req = course_info['degree_req'].iloc[0]
            
            # Clean up parameter scores to replace NaN with None
            parameter_scores = {}
            for param, score in details['parameter_counts'].items():
                parameter_scores[param] = None if pd.isna(score) else score
            
            major_recommendations.append({
                'courseCode': course_code,
                'courseTitle': ' '.join(course_info['course_title'].iloc[0].split()[2:]),
                'description': course_info['description'].iloc[0],
                'prerequisites': prerequisites,
                'degreeReq': degree_req,
                'totalScore': None if pd.isna(details['total_count']) else details['total_count'],
                'parameterScores': parameter_scores
            })

    # Get other recommendations
    other_recommendations = []
    for course_code, details in ranked_other_course_recs[:10]:
        department = all_course_to_department_map[course_code].replace(" ", "_").lower()
        courses_with_descriptions_df = pd.read_csv(f'data/{department}_courses_with_descriptions.csv')

        course_info = courses_with_descriptions_df[courses_with_descriptions_df['course_code'] == course_code]
        if not course_info.empty:
            # Convert NaN values to None (which becomes null in JSON)
            prerequisites = None
            if 'prerequisites' in course_info and not pd.isna(course_info['prerequisites'].iloc[0]):
                prerequisites = course_info['prerequisites'].iloc[0]
                
            degree_req = None
            if 'degree_req' in course_info and not pd.isna(course_info['degree_req'].iloc[0]):
                degree_req = course_info['degree_req'].iloc[0]
            
            # Clean up parameter scores to replace NaN with None
            parameter_scores = {}
            for param, score in details['parameter_counts'].items():
                parameter_scores[param] = None if pd.isna(score) else score
            
            other_recommendations.append({
                'courseCode': course_code,
                'courseTitle': ' '.join(course_info['course_title'].iloc[0].split()[2:]),
                'description': course_info['description'].iloc[0],
                'prerequisites': prerequisites,
                'degreeReq': degree_req,
                'totalScore': None if pd.isna(details['total_count']) else details['total_count'],
                'parameterScores': parameter_scores
            })

    return jsonify({
        'majorRecommendations': major_recommendations,
        'otherRecommendations': other_recommendations
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)