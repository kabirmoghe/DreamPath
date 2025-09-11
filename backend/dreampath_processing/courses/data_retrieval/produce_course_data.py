from dreampath_processing.courses.data_retrieval.college_info_retrieval import get_dartmouth_majors, produce_courses_for_department, get_department_data, DATA_DIR, add_prereqs_to_department_data, load_dataframes
import os
import json
import glob

def main():
    # Get Dartmouth departments
    print("Getting Dartmouth departments data...")
    if not os.path.exists(f"{DATA_DIR}/undergrad_department_links.json"):
        department_data, dept_ids = get_department_data()

        # save department links to file
        with open(f"{DATA_DIR}/undergrad_department_links.json", "w") as f:
            json.dump(department_data, f, indent=2)

        # save department aliases to file
        with open(f"{DATA_DIR}/undergrad_department_ids.json", "w") as f:
            json.dump(dept_ids, f, indent=2)

    # Load department data
    department_data = json.load(open(f"{DATA_DIR}/undergrad_department_links.json"))
    dept_ids = json.load(open(f"{DATA_DIR}/undergrad_department_ids.json"))

    # Get Dartmouth degrees
    print("Getting Dartmouth degrees...")
    if not os.path.exists(f"{DATA_DIR}/dartmouth_majors.csv"):
        degree_df = get_dartmouth_majors(dept_ids)
        degree_df.to_csv(f"{DATA_DIR}/dartmouth_majors.csv", index=False)

    # Get courses for each department
    print("Getting courses for each department...")
    department_data = json.load(open(f"{DATA_DIR}/undergrad_department_links.json"))
    dept_ids = json.load(open(f"{DATA_DIR}/undergrad_department_ids.json"))

    for department in department_data.keys():
        # Grab id from file
        department_id = dept_ids[department]

        # Check if courses already exist
        courses_path = f"{DATA_DIR}/courses/{department}_courses.csv"
        if os.path.exists(courses_path):
            print(f"Skipping {department} because it already exists")
            continue

        # Get courses
        print(f"Getting courses for {department}...")
        courses = produce_courses_for_department(department_data, department, department_id)

        # Add prereqs
        if courses is not None:
            courses = add_prereqs_to_department_data(courses)
            courses.to_csv(courses_path, index=False)
            print(f"Saved courses for {department} [{department_id}] to {courses_path}")

    # Aggregate all courses into a single dataframe
    print("Aggregating all courses into a single dataframe...")
    all_courses_path = f"{DATA_DIR}/all_courses.csv"
    if not os.path.exists(all_courses_path):
        course_files = glob.glob(f"{DATA_DIR}/courses/*.csv")
        if course_files:
            all_courses = load_dataframes(course_files)
            all_courses = all_courses[all_courses['course_code'].notna()]
            all_courses.to_csv(all_courses_path, index=False)
        else:
            print(f"No CSV files found in {DATA_DIR}/courses/")
    else:
        print(f"Skipping aggregation because {all_courses_path} already exists")

if __name__ == "__main__":
    main()