from dreampath_processing.courses.data_retrieval.course_path_visualization import flatten_graph_dict, visualize_graph
from dreampath_processing.courses.course_relationship_handling import build_prereq_tree, merge_prereq_trees_to_graph, construct_course
from dreampath_processing.courses.scheduling_helpers import schedule_courses_by_term
from dreampath_processing.courses.schedule_modules.course_path import CoursePath

# major_courses, complementary_courses, 
def build_course_path(recommended_courses, course_bank, visualize_course_connections=False) -> CoursePath:
    # Build prereq trees
    prereq_trees = []

    print('Building prereq. trees for recommended courses...')
    # Modify course objects in course bank
    for course in recommended_courses:
        course_prereq_tree, course_prereqs = build_prereq_tree(course)
        prereq_trees.append(course_prereq_tree)
        course_bank[course].prereq_tree = course_prereq_tree

        # Add prereq. objects to course bank
        for prereq in course_prereqs:
            print(f"Prereq: {prereq}, parent course: {course}")
            prereq_obj = course_bank.get(prereq, construct_course(course_code=prereq, hardcoded_type=course_bank[course].course_type))

            if prereq_obj is None:
                print(f"Unknown prereq course code '{prereq}'.")
                continue

            prereq_obj.is_prereq = True
            course_bank[prereq] = prereq_obj

    # Build course graph
    prereq_graph = merge_prereq_trees_to_graph(prereq_trees)

    print("---")

    if visualize_course_connections:
        flattened_graph = flatten_graph_dict(prereq_graph.children)
        visualize_graph(flattened_graph, prereq_graph.all_courses)

    # Build course path
    course_path_components = schedule_courses_by_term(course_graph=prereq_graph, course_bank=course_bank, max_terms=12, max_courses_per_term=3, verbose=True)
    course_path = course_path_components["plan"]

    # Formalize output course path
    output_course_path = CoursePath(course_path=course_path,
                                    recommended_courses=recommended_courses,
                                    course_bank=course_bank,
                                    prereq_graph=prereq_graph)

    return output_course_path