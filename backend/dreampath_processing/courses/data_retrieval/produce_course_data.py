from dreampath_processing.courses.data_retrieval.college_info_retrieval import get_dartmouth_majors, produce_courses_for_department, get_department_data, DATA_DIR, add_prereqs_to_department_data
import os
import json

def main():
    # Get Dartmouth departments
    print("Getting Dartmouth departments data...")
    if not os.path.exists(f"{DATA_DIR}/undergrad_department_links.json"):
        department_data, dept_aliases = get_department_data()

        # save department links to file
        with open(f"{DATA_DIR}/undergrad_department_links.json", "w") as f:
            json.dump(department_data, f, indent=2)

        # save department aliases to file
        with open(f"{DATA_DIR}/undergrad_department_aliases.json", "w") as f:
            json.dump(dept_aliases, f, indent=2)

    # Get Dartmouth degrees
    print("Getting Dartmouth degrees...")

    if not os.path.exists(f"{DATA_DIR}/dartmouth_majors.csv"):
        degree_df = get_dartmouth_majors()
        degree_df.to_csv(f"{DATA_DIR}/dartmouth_majors.csv", index=False)

    # Get courses for each department
    print("Getting courses for each department...")
    department_data = json.load(open(f"{DATA_DIR}/undergrad_department_links.json"))
    dept_aliases = json.load(open(f"{DATA_DIR}/undergrad_department_aliases.json"))

    for department_name in department_data.keys():
        # Grab alias from file
        department_alias = dept_aliases[department_name]

        # Check if courses already exist
        courses_path = f"{DATA_DIR}/courses/{department_alias}_courses.csv"
        if os.path.exists(courses_path):
            print(f"Skipping {department_name} because it already exists")
            continue

        # Get courses
        print(f"Getting courses for {department_name}...")
        courses = produce_courses_for_department(department_data, department_name)

        # Add prereqs
        if courses is not None:
            courses = add_prereqs_to_department_data(courses)
            courses.to_csv(courses_path, index=False)
            print(f"Saved courses for {department_name} to {courses_path}")

if __name__ == "__main__":
    main()