from dreampath_processing.courses import *
from dreampath_processing.courses.prompts.course_matching_prompts import *
from dreampath_processing.courses.semantic_course_search import *
from dreampath_processing.courses.course_vector_db_ops import load_vector_store
from dreampath_processing.courses.build_major_course_path import get_department_alias_from_dept_name, get_department_from_course_code
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import os
from collections import Counter

openai_api_key = os.getenv("OPENAI_API_KEY")

if __name__ == "__main__":
    topic = "AI"
    major = "Computer Science"

    major_course_counts, complementary_course_counts = get_courses_for_topic(topic=topic, major=major)

    print(f'Major course counts: {major_course_counts.most_common(10)}')
    print(f'Compl. course counts: {complementary_course_counts.most_common(10)}')