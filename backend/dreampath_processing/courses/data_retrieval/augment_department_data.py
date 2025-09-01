import pandas as pd
from backend.dreampath_processing.courses.data_retrieval.prerequisite_parsing import get_course_prereqs
from backend.dreampath_processing.courses.data_retrieval.college_info_retrieval import load_undergraduate_links_by_major
from dreampath_processing.courses.semantic_course_search import load_vector_store
import json

def add_prereqs_to_major_data(major_cleaned):
    major_df = pd.read_csv(f'dreampath_processing/courses/data/{major_cleaned}_courses_with_descriptions.csv') 
    major_df['best_prereq_path'] = major_df.apply(get_course_prereqs, axis=1, overwrite=False)
    
    return major_df

def produce_department_alias(major_raw):
    major_cleaned = major_raw.replace(" ", "_").lower()
    course_df = pd.read_csv(f'dreampath_processing/courses/data/{major_cleaned}_courses_with_descriptions.csv')

    department_alias = course_df['dept'].mode()[0]
    return department_alias

if __name__ == "__main__":
    department_df = pd.read_csv('dreampath_processing/courses/data/dartmouth_majors.csv')
    majors_raw = department_df['Major'].unique()
    majors_cleaned = [major_raw.replace(" ", "_").lower() for major_raw in majors_raw]

    build_major_links = False
    build_major_vector_stores = False
    build_department_aliases = False
    build_major_prereqs = True

    # Producing undergraduate links for each major
    if build_major_links:
        print('Producing undergraduate links for each major...\n==')
        for major in majors_raw:
            load_undergraduate_links_by_major(major)
            print('--')

    # Producing vector stores for each major
    if build_major_vector_stores:
        print('Building vector stores for each major...\n==')
        for major in majors_raw:
            load_vector_store(major)
            print('--')

    # Producing department alias for each major
    if build_department_aliases:
        print('Producing department alias for each major...\n==')
        department_aliases_path = 'dreampath_processing/courses/data/department_aliases.json'
        department_aliases = {}

        for major in majors_raw:
            department_alias = produce_department_alias(major)
            department_aliases[department_alias] = major
            print(f'Department alias for {major} -->{department_alias}')
            print('--')

        with open(department_aliases_path, 'w') as f:
            json.dump(department_aliases, f)

    # Adding prereqs to major data
    if build_major_prereqs:
        print('Adding prereqs to major data...\n==')
        for major in majors_cleaned:
            print(f'Augmenting {major} data with prereqs...')
            try: 
                major_df = add_prereqs_to_major_data(major)
                major_df.to_csv(f'dreampath_processing/courses/data/{major}_courses_with_descriptions.csv', index=False)
            except Exception as e:
                print(f'Error augmenting {major} data with prereqs: {e}\nSkipping...')
        print('--')

