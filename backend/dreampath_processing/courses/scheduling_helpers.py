from dreampath_processing.courses.build_major_course_path import build_prereq_tree, merge_prereq_trees_to_graph
from collections import defaultdict
import copy

def swap_courses(course_path, term_idx, old_course, new_course):
    # Extract position of old course in term
    old_course_idx = course_path[term_idx].index(old_course)

    # Swap courses
    course_path_swapped = copy.deepcopy(course_path)
    course_path_swapped[term_idx][old_course_idx] = new_course

    return course_path_swapped

def get_direct_prereqs(prereq_tree, course_code):
    try:
        direct_children = []
        
        for child_dict in prereq_tree.get(course_code, []):

            # In case of missing course code for prereq.
            if child_dict:
                direct_children.append(list(child_dict.keys())[0])
            else:
                print("Empty")

        return direct_children
    except:
        print(f'Error getting direct prereqs for {course_code}')
        print(prereq_tree)
    return direct_children

def check_violations(course_plan, direct_prereq_map):
    # 1. Build a mapping from course → list of terms it appears in
    occurrences = defaultdict(list)
    for term_idx, term_courses in enumerate(course_plan):
        for c in term_courses:
            occurrences[c].append(term_idx)

    violations = []

    # 2. Flag any duplicates
    for course, terms in occurrences.items():
        if len(terms) > 1:
            violations.append({
                "course": course,
                "course_terms": terms,
                "issue": "Duplicate course scheduled in multiple terms."
            })

    # 3. Build reverse map from course → single term (for prereq checking)
    #    Note: if duplicate, this will pick the last occurrence, but that doesn't block us
    term_of = {course: terms[-1] for course, terms in occurrences.items()}

    # 4. Prerequisite violations
    for c, prereqs in direct_prereq_map.items():
        # skip any course not in the plan
        if c not in term_of:
            continue

        c_term = term_of[c]
        for p in prereqs:
            if p not in term_of:
                violations.append({
                    "course": c,
                    "course_term": c_term,
                    "prereq": p,
                    "prereq_term": None,
                    "issue": "Prerequisite not scheduled."
                })
            elif term_of[p] >= c_term:
                violations.append({
                    "course": c,
                    "course_term": c_term,
                    "prereq": p,
                    "prereq_term": term_of[p],
                    "issue": "Prerequisite not complete in time."
                })
            # else: prereq is satisfied

    return violations

if __name__=='__main__':
    major_courses = ['COSC74']
    curr_course = major_courses[0]

    course_path = [
        # Term 1
        ["COSC1",     "COSC89.17", "ECON1"],
        # Term 2
        ["COSC10",    "COSC51",    "ECON10"],
        # Term 3
        ["COSC50",    "MATH3",     "ECON70.02"],
        # Term 4
        ["COSC55",    "COSC58",    "ENGS50"],
        # Term 5
        ["COSC61",    "COSC70",    "MATH1"],
        # Term 6
        ["COSC74",    "COSC89.19", "ECON3"],
        # Term 7
        ["COSC89.20", "COSC89.27", "ECON20"],
        # Term 8
        ["COSC89.28", "ECON21",    "ECON22"],
        # Term 9
        ["MATH8",     "QSS15",     "QSS17"],
        # Term 10
        ["ECON81",    "QSS19",     "QSS20"],
        # Term 11
        ["QSS30.09",  "QSS41",     "QSS45"],
        # Term 12
        []
    ]

    course_path_swapped = swap_courses(course_path, 0, "COSC1", "COSC10")

    direct_prereq_map = {}

    for term in course_path:
        for course in term:
            prereq_tree, _ = build_prereq_tree(course)
            direct_prereqs = get_direct_prereqs(prereq_tree, course)
            direct_prereq_map[course] = direct_prereqs

    violations = check_violations(course_path_swapped, direct_prereq_map)

    print(violations)