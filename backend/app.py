from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from dreampath_processing.courses.semantic_course_search import *
from dreampath_processing.courses.college_info_retrieval import produce_courses_for_major
from dreampath_processing.courses.build_major_course_path import retrieve_enhanced_course_from_course_code, build_course_path
from dreampath_processing.clubs.semantic_club_search import *
from dotenv import load_dotenv
from supabase import create_client, Client # type: ignore

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = Flask(__name__)
# Only allow requests from frontend
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

@app.route('/api/majors', methods=['GET'])
def get_majors():
    # Return list of available majors
    available_majors = pd.read_csv('data/dartmouth_majors.csv')['Major'].unique().tolist()
    
    print(f"Available majors: {available_majors}")
    return jsonify(available_majors)

@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    data = request.json
    major = data.get('major')
    college_interests = data.get('collegeInterests', '')
    post_grad_goal = data.get('postGradGoal', '')
    long_term_goal = data.get('longTermGoal', '')
    user_id = data.get('user_id')
    profile_id = data.get('profile_id')
    iteration_name = data.get('iteration_name', 'DreamPath Iteration')
    
    # Extract parameter weights from request (optional)
    # parameter_weights = data.get('parameter_weights')
    # Default parameter weights
    parameter_weights = {
        'college_interests': 1.0,
        'post_grad_goal': 1.0,
        'long_term_goal': 0.5
    }
    
    # Extract separate weights for courses and clubs (optional)
    course_parameter_weights = data.get('course_parameter_weights', parameter_weights)
    club_parameter_weights = data.get('club_parameter_weights', parameter_weights)
    
    print(f"Major: {major}")
    print(f"College interests: {college_interests}")
    print(f"Post-grad goal: {post_grad_goal}")
    print(f"Long-term goal: {long_term_goal}")
    print(f"Course parameter weights: {course_parameter_weights}")
    print(f"Club parameter weights: {club_parameter_weights}")

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
    
    try:
        scored_major_course_recs, scored_other_course_recs = score_recommended_courses(major_course_recs, other_course_recs, all_unique_courses, course_parameter_weights)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

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

            formatted_course = None

            # Check if course is a major recommendation and/or a prerequisite
            if course_code in all_major_course_codes:
                if course_code in major_recommendations_map:
                    reference_major_course = major_recommendations_map[course_code]
                    formatted_course = reference_major_course.copy()
                    
                    # Rename scores
                    formatted_course['majorTotalScore'] = formatted_course['totalScore']
                    formatted_course['majorParameterScores'] = formatted_course['parameterScores']
                    del formatted_course['totalScore']
                    del formatted_course['parameterScores']
                else:
                    formatted_course = format_course(course_code)
                    if formatted_course is None:
                        print(f"Warning: Could not format course {course_code}, skipping...")
                        continue
                    formatted_course['isPrerequisite'] = True
                formatted_course['isMajor'] = True
                
            # Check if course is a complementary recommendation and/or a prerequisite
            if course_code in all_complementary_course_codes:
                if course_code in complementary_recommendations_map:
                    reference_complementary_course = complementary_recommendations_map[course_code]
                    temp_course = reference_complementary_course.copy()

                    # In case complementary course is not a major recommendation, format it
                    if formatted_course is not None:
                        formatted_course['complementaryTotalScore'] = temp_course['totalScore']
                        formatted_course['complementaryParameterScores'] = temp_course['parameterScores']
                    else:
                        formatted_course = temp_course
                        formatted_course['complementaryTotalScore'] = formatted_course['totalScore']
                        formatted_course['complementaryParameterScores'] = formatted_course['parameterScores']

                        del formatted_course['totalScore']
                        del formatted_course['parameterScores']
                else:
                    # In case complementary course is not a major recommendation, format it
                    if formatted_course is None:
                        formatted_course = format_course(course_code)
                        if formatted_course is None:
                            print(f"Warning: Could not format course {course_code}, skipping...")
                            continue

                    formatted_course['isPrerequisite'] = True
                formatted_course['isComplementary'] = True

            # Skip if no formatted course was created
            if formatted_course is None:
                print(f"Warning: No formatted course created for {course_code}, skipping...")
                continue
            
            # Backup defaults
            formatted_course.setdefault('isMajor', False)
            formatted_course.setdefault('isComplementary', False)
            formatted_course.setdefault('isPrerequisite', False)
            formatted_course.setdefault('majorTotalScore', None)
            formatted_course.setdefault('majorParameterScores', None)
            formatted_course.setdefault('complementaryTotalScore', None)
            formatted_course.setdefault('complementaryParameterScores', None)
            
            term_courses.append(formatted_course)
        
        course_path.append(term_courses)

    # Get club recommendations
    club_recommendations, club_metadata = get_club_recommendations(major, student_parameters)
    
    try:
        formatted_club_recommendations = format_club(club_recommendations, club_metadata, club_parameter_weights)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # 1. Insert dreampath_iterations
    iteration_resp = supabase.table('dreampath_iterations').insert({
        'user_id': user_id,
        'profile_id': profile_id,
        'iteration_name': iteration_name,
        'status': 'active'
    }).execute()
    iteration_id = iteration_resp.data[0]['id']

    # 2. Insert course recommendations
    course_id_map = {}
    
    # First, insert major recommendations
    for course in major_recommendations:
        course_data = {
            'dreampath_id': iteration_id,
            'course_code': course.get('courseCode'),
            'course_title': course.get('courseTitle'),
            'description': course.get('description'),
            'prerequisites': course.get('prerequisites'),
            'degree_req': course.get('degreeReq'),
            'is_major': True,  # All major recommendations are major courses
            'is_complementary': False,
            'is_prerequisite': False,
            'major_total_score': course.get('totalScore'),
            'major_parameter_scores': course.get('parameterScores'),
            'complementary_total_score': None,
            'complementary_parameter_scores': None,
            'term': None
        }
        resp = supabase.table('dreampath_course_recommendations').insert(course_data).execute()
        course_id_map[course.get('courseCode')] = resp.data[0]['id']

    # Then, insert complementary recommendations
    for course in complementary_recommendations:
        course_data = {
            'dreampath_id': iteration_id,
            'course_code': course.get('courseCode'),
            'course_title': course.get('courseTitle'),
            'description': course.get('description'),
            'prerequisites': course.get('prerequisites'),
            'degree_req': course.get('degreeReq'),
            'is_major': False,
            'is_complementary': True,  # All complementary recommendations are complementary courses
            'is_prerequisite': False,
            'major_total_score': None,
            'major_parameter_scores': None,
            'complementary_total_score': course.get('totalScore'),
            'complementary_parameter_scores': course.get('parameterScores'),
            'term': None
        }
        resp = supabase.table('dreampath_course_recommendations').insert(course_data).execute()
        course_id_map[course.get('courseCode')] = resp.data[0]['id']

    # Finally, handle term courses (which may include prerequisites)
    for term_order, term_courses in enumerate(course_path):
        term_name = f"Term {term_order+1}"
        term_resp = supabase.table('dreampath_course_terms').insert({
            'dreampath_id': iteration_id,
            'term_order': term_order,
            'term_name': term_name
        }).execute()
        term_id = term_resp.data[0]['id']

        for course in term_courses:
            course_code = course.get('courseCode')
            
            # If course not already in course_id_map (i.e., it's a prerequisite), insert it
            if course_code not in course_id_map:
                course_data = {
                    'dreampath_id': iteration_id,
                    'course_code': course_code,
                    'course_title': course.get('courseTitle'),
                    'description': course.get('description'),
                    'prerequisites': course.get('prerequisites'),
                    'degree_req': course.get('degreeReq'),
                    'is_major': course.get('isMajor', False),
                    'is_complementary': course.get('isComplementary', False),
                    'is_prerequisite': course.get('isPrerequisite', False),
                    'major_total_score': course.get('majorTotalScore'),
                    'major_parameter_scores': course.get('majorParameterScores'),
                    'complementary_total_score': course.get('complementaryTotalScore'),
                    'complementary_parameter_scores': course.get('complementaryParameterScores'),
                    'term': term_name
                }
                resp = supabase.table('dreampath_course_recommendations').insert(course_data).execute()
                course_id_map[course_code] = resp.data[0]['id']
            else:
                # Update the term for the existing course recommendation
                supabase.table('dreampath_course_recommendations').update({'term': term_name}).eq('id', course_id_map[course_code]).execute()

            # Link course to term
            supabase.table('dreampath_term_courses').insert({
                'term_id': term_id,
                'course_recommendation_id': course_id_map[course_code]
            }).execute()

    # 3. Insert club recommendations
    for club_name, club in formatted_club_recommendations.items():
        club_data = {
            'dreampath_id': iteration_id,
            'club_name': club.get('clubName'),
            'description': club.get('clubBlurb'),
            'category': club.get('clubCategory'),
            'tags': club.get('tags'),
            'score': club.get('totalScore'),
        }
        supabase.table('dreampath_club_recommendations').insert(club_data).execute()

    return jsonify({
        'iterationId': iteration_id,
        'majorRecommendations': major_recommendations,
        'complementaryRecommendations': complementary_recommendations,
        'coursePath': course_path,
        'clubRecommendations': formatted_club_recommendations
    })

@app.route('/api/recommendations/<iteration_id>', methods=['GET'])
def get_recommendations_by_iteration(iteration_id):
    # Fetch course recommendations
    course_recs_resp = supabase.table('dreampath_course_recommendations').select('*').eq('dreampath_id', iteration_id).execute()
    course_recs = course_recs_resp.data if course_recs_resp.data else []

    # Fetch club recommendations
    club_recs_resp = supabase.table('dreampath_club_recommendations').select('*').eq('dreampath_id', iteration_id).execute()
    club_recs = club_recs_resp.data if club_recs_resp.data else []

    # Fetch course terms
    terms_resp = supabase.table('dreampath_course_terms').select('*').eq('dreampath_id', iteration_id).order('term_order', desc=False).execute()
    terms = terms_resp.data if terms_resp.data else []

    # Fetch only relevant term courses
    term_ids = [term['id'] for term in terms]
    if term_ids:
        term_courses_resp = supabase.table('dreampath_term_courses').select('*').in_('term_id', term_ids).execute()
        term_courses = term_courses_resp.data if term_courses_resp.data else []
    else:
        term_courses = []

    # Helper to normalize course recs to camelCase and match format_course
    def normalize_course(c):
        return {
            'courseCode': c.get('course_code'),
            'courseTitle': c.get('course_title'),
            'description': c.get('description'),
            'prerequisites': c.get('prerequisites'),
            'degreeReq': c.get('degree_req'),
            'isMajor': c.get('is_major', False),
            'isComplementary': c.get('is_complementary', False),
            'isPrerequisite': c.get('is_prerequisite', False),
            'majorTotalScore': c.get('major_total_score'),
            'majorParameterScores': c.get('major_parameter_scores'),
            'complementaryTotalScore': c.get('complementary_total_score'),
            'complementaryParameterScores': c.get('complementary_parameter_scores'),
            'term': c.get('term'),
        }

    # Helper to normalize club recs to match format_club
    def normalize_club(c):
        return {
            'clubName': c.get('club_name'),
            'clubCategory': c.get('category'),
            'clubBlurb': c.get('description'),
            'tags': c.get('tags'),
            'score': c.get('score'),
        }

    # Organize major and complementary recommendations
    major_recs = [normalize_course(c) for c in course_recs if c.get('is_major')]
    complementary_recs = [normalize_course(c) for c in course_recs if c.get('is_complementary')]
    club_recs_dict = {c['club_name']: normalize_club(c) for c in club_recs}

    # Assemble course path by term (list of lists of normalized courses)
    course_path = []
    for term in terms:
        courses_in_term = [tc for tc in term_courses if tc['term_id'] == term['id']]
        course_objs = []
        for tc in courses_in_term:
            course_obj = next((c for c in course_recs if c['id'] == tc['course_recommendation_id']), None)
            if course_obj:
                course_objs.append(normalize_course(course_obj))
        course_path.append(course_objs)

    return jsonify({
        'iterationId': iteration_id,
        'majorRecommendations': major_recs,
        'complementaryRecommendations': complementary_recs,
        'coursePath': course_path,
        'clubRecommendations': club_recs_dict
    })

# Course formatting
def format_course(course_code, courses_df=None, details=None):
    # If department courses dataframe is provided, use it; otherwise produce course information
    if courses_df is None:
        course_info = retrieve_enhanced_course_from_course_code(course_code)
    else:
        # Check if course exists in DataFrame before accessing
        matching_courses = courses_df[courses_df['course_code'] == course_code]
        if matching_courses.empty:
            print(f"Warning: Course {course_code} not found in courses DataFrame")
            return None
        course_info = matching_courses.iloc[0]

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

# Club formatting
def format_club(club_recommendations, club_metadata, parameter_weights=None):
    """
    Formats club recommendations with optional parameter weights.
    
    Args:
        club_recommendations (dict): Dictionary of club recommendations with parameter scores.
        club_metadata (dict): Dictionary of club metadata.
        parameter_weights (dict, optional): Dictionary of weights for each parameter.
            Should contain keys: 'college_interests', 'post_grad_goal', 'long_term_goal'
            Values should be in range [0,1]. At least one must be > 0.
            Defaults to {'college_interests': 1.0, 'post_grad_goal': 1.0, 'long_term_goal': 0.5}.
    
    Returns:
        dict: Formatted club recommendations with weighted scores.
    """
    from dreampath_processing.clubs.semantic_club_search import score_club_recommendations
    
    # Score clubs with weights
    scored_clubs = score_club_recommendations(club_recommendations, club_metadata, parameter_weights)
    
    unified_club_data = {}
    for club_name, scored_data in scored_clubs.items():
        metadata = scored_data['metadata']
        unified_club_data[club_name] = {
            'clubName': club_name,
            'clubCategory': metadata.get('club_category', ''),
            'clubBlurb': metadata.get('club_blurb', ''),
            'tags': metadata.get('tags', []),
            'urls': metadata.get('urls', []),
            'parameterScores': scored_data['parameterScores'],
            'totalScore': scored_data['totalScore']
        }

    # Sort dict of clubs by total score
    return unified_club_data
    
if __name__ == '__main__':
    app.run(debug=True, port=5001)