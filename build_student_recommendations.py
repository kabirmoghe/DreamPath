from semantic_course_search import get_courses_across_student_parameters, create_vector_store
from college_info_retrieval import produce_courses_for_major
import os
import pandas as pd
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

openai_api_key = os.getenv('OPENAI_API_KEY')

def parse_student_interests(student_interest_text):
    return student_interest_text.split(',')

def produce_parameter_based_recommendations(student_parameters, vectorstore):
    if 'college_interests' in student_parameters:
        college_interests = parse_student_interests(student_parameters['college_interests'])
        student_parameters['college_interests'] = college_interests

    return get_courses_across_student_parameters(student_parameters, vectorstore)

if __name__ == "__main__":

    # Get major and corresponding courses
    major_examples = ['Computer Science', 'African and African American Studies', 'Biological Sciences', 'Biophysical Chemistry']

    # anthropology to fix
    college_interest_examples = [
        'cybersecurity, cloud computing, artificial intelligence and security',
        'Race and media, postcolonial theory, diaspora studies',
        'Genetics, neuroscience, microbiology',
        'Protein folding, computational chemistry, spectroscopy'
    ]

    post_grad_goal_examples = [
        'data scientist and machine learning engineer',
        'Work at a racial justice nonprofit as a policy analyst',
        'Apply to MD/PhD programs',
        'Join a research lab focused on protein-based drug design'
    ]

    long_term_goal_examples = [
        'Lead the development of ethical, large-scale AI systems that enhance global cybersecurity infrastructure and advocate for responsible AI use in government or corporate policy.',
        'Shape national civil rights legislation or advise international human rights organizations by producing influential policy research rooted in race and cultural studies.',
        'Direct a translational neuroscience research lab and pioneer treatments for neurodegenerative diseases while mentoring the next generation of physician-scientists.',
        'Lead R&D at a biotech company developing novel therapeutics through protein engineering, and help revolutionize treatment approaches for rare diseases.'
    ]

    for i in range(len(major_examples)):
        major = major_examples[i]
        college_interests = college_interest_examples[i]
        post_grad_goal = post_grad_goal_examples[i]
        long_term_goal = long_term_goal_examples[i]
        print(f'Building recommendations for:\n*Major: {major}\n*College Interests: {college_interests}\n*Post Grad Goal: {post_grad_goal}\n*Long Term Aspirations: {long_term_goal}')

        student_parameters = {
            'college_interests': college_interests,
            'post_grad_goal': post_grad_goal,
            'long_term_goal': long_term_goal
        }

        major_cleaned = major.lower().replace(" ", "_")

        if os.path.exists(f'{major_cleaned}_courses_with_descriptions.csv'):
            courses_with_descriptions_df = pd.read_csv(f'{major_cleaned}_courses_with_descriptions.csv')
            courses_with_descriptions = courses_with_descriptions_df.to_dict('records')
        else:
            courses_with_descriptions = produce_courses_for_major(major)
            courses_with_descriptions_df = pd.DataFrame(courses_with_descriptions)
            courses_with_descriptions_df.to_csv(f'{major_cleaned}_courses_with_descriptions.csv', index=False)

        # Create vector store for courses if it doesn't exist
        if not os.path.exists(f'vectorstores/{major_cleaned}'):
            vectorstore = create_vector_store(courses_with_descriptions=courses_with_descriptions, vectorstore_name=major_cleaned)
        else:
            vectorstore = FAISS.load_local(f"vectorstores/{major_cleaned}", OpenAIEmbeddings(api_key=openai_api_key), allow_dangerous_deserialization=True)

        # Produce recommendations
        course_recommendation_details = produce_parameter_based_recommendations(student_parameters, vectorstore)

        # Sort recommendations by total count
        course_recommendation_details = sorted(course_recommendation_details.items(), key=lambda x: x[1]['total_count'], reverse=True)

        # Print the course recommendation details
        num_courses_to_print = 10
        for course_code, details in course_recommendation_details:
            print(f"Course: {course_code}")
            print(f"  - Total Recommendations: {details['total_count']}")
            for parameter, count in details['parameter_counts'].items():
                print(f"    - {parameter}: {count}")
            print(f"Description: {courses_with_descriptions_df[courses_with_descriptions_df['course_code'] == course_code]['description'].iloc[0][:150]}...")
            print("----------------------------")
            num_courses_to_print -= 1
            if num_courses_to_print == 0:
                break
        
        print("================================================")