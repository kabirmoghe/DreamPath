from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import os
from collections import Counter

from dreampath_processing.courses.schedule_modules.course import Course, MAJOR, COMPLEMENTARY
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.change_management.change_requests import add_course, remove_course
from dreampath_processing.courses.scheduling_helpers import rebuild_course_path_with_must_haves

openai_api_key = os.getenv("OPENAI_API_KEY")

if __name__ == "__main__":
    # topic = "AI"
    # major = "Computer Science"

    # major_course_counts, complementary_course_counts = get_courses_for_topic(topic=topic, major=major)

    # print(f'Major course counts: {major_course_counts.most_common(10)}')
    # print(f'Compl. course counts: {complementary_course_counts.most_common(10)}')

    # -- 1. Build original course path --
    major = 'Computer Science'
    major_courses = {'COSC89.27', 'COSC55', 'COSC89.20', 'COSC35', 'COSC89.17', 'COSC89.28', 'COSC62', 'COSC69.17', 'COSC89.19', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}
    
    # Construct recommended courses set and course bank
    recommended_courses = major_courses | complementary_courses
    course_bank = {c: Course(course_code=c, course_type=MAJOR if c in major_courses else COMPLEMENTARY) for c in recommended_courses}

    # Build initial course path + course bank updated with prereqs + scheduling info
    initial_course_path = build_course_path(recommended_courses, course_bank)

    print(f"\n-- ORIGINAL COURSE PATH --")
    print(initial_course_path.course_path)
    for c in initial_course_path.course_bank.values():
        print(c)

    #  # Test removal functionality
    # # removed_course_path = safely_remove_course(initial_course_path, 'COSC74', 8)
    # # print(f"\n-- REMOVED COURSE PATH --")
    # # print(removed_course_path.course_path)

    # 2. Make changes
    sample_must_have_course_map = {'COSC52': Course(course_code='COSC52', course_type=MAJOR, must_have_window=(7, 8)),
                         'COSC58': Course(course_code='COSC58', course_type=MAJOR, must_have_window=(2, 2)),
                         'COSC74': Course(course_code='COSC74', course_type=MAJOR, must_have_window=(6,9))}
    
    modified_course_path = rebuild_course_path_with_must_haves(initial_course_path, window_start_term=2, must_have_course_map=sample_must_have_course_map, verbose=3)

    print(f"\n-- MODIFIED COURSE PATH v1--")
    print(modified_course_path.course_path)
    print(f"Must-have courses: {modified_course_path.must_have_courses}")
    for c in modified_course_path.course_bank.values():
        print(c)

    # 1. Testing ADD Course
    new_course = Course(course_code='COSC59', course_type=MAJOR, must_have_window=(7, 11))

    try:
        add_course_path = add_course(modified_course_path, new_course)
        print(f"\n-- MODIFIED COURSE PATH v2--")
        print(add_course_path.course_path)
        print(f"Must-have courses: {add_course_path.must_have_courses}")
        for c in add_course_path.course_bank.values():
            print(c)
    except ValueError as e:
        print(f"* Error adding course: {e}")
        pass

    # 2. Testing REMOVE Course
    try: 
        remove_course_path = remove_course(add_course_path, 'COSC59')
        print(f"\n-- MODIFIED COURSE PATH v3--")
        print(remove_course_path.course_path)
        print(f"Must-have courses: {remove_course_path.must_have_courses}")
        for c in remove_course_path.course_bank.values():
            print(c)
    except ValueError as e:
        print(f"* Error removing course: {e}")
        pass

    # # 3. Make more changes
    # additional_must_have_course_map = {'QSS41': Course(course_code='QSS41', course_type=COMPLEMENTARY, must_have_window=(9, 9))}
    # modified_course_path = rebuild_course_path_with_must_haves(modified_course_path, window_start_term=6, must_have_course_map=additional_must_have_course_map, verbose=True)

    # print(f"\n-- MODIFIED COURSE PATH v2--")
    # print(modified_course_path.course_path)
    # print(f"Must-have courses: {modified_course_path.must_have_courses}")
    # for c in modified_course_path.course_bank.values():
    #     print(c)