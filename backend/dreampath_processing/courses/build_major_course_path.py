import pandas as pd
import re
import json
from collections import defaultdict, deque
import copy
from dreampath_processing.courses.course_path_visualization import flatten_graph_dict, visualize_graph
from schedule_modules.course_path import CoursePath
from schedule_modules.course import Course, MAJOR, COMPLEMENTARY

# Building prerequisite tree for individual courses
def get_department_from_course_code(course_code):
    course_components = re.match(r'^([A-Z]+)(.*)', course_code)
    
    if course_components:
        dept_alias = course_components.group(1)
        number = course_components.group(2)

        try:
            number = float(number)
        except ValueError:
            number = None

        return dept_alias, number
    
    return None, None

# Get department alias from department name
def get_department_alias_from_dept_name(dept_name):
    dept_alias_to_name = json.load(open('dreampath_processing/courses/data/department_aliases.json'))
    dept_name_to_alias = {v: k for k, v in dept_alias_to_name.items()}
    dept_alias = dept_name_to_alias.get(dept_name, None)

    # Ensure provided department name has corresponding alias
    if not dept_alias:
        raise ValueError(f"Department name {dept_name} does not exist.")
    
    return dept_alias

def retrieve_enhanced_course_from_course_code(course_code):
    # get department name from course code
    dept_alias, _ = get_department_from_course_code(course_code)
    dept_alias_map = json.load(open('dreampath_processing/courses/data/department_aliases.json'))
    dept_raw = dept_alias_map[dept_alias]
    dept_cleaned = dept_raw.replace(' ', '_').lower()

    # get department courses
    dept_courses = pd.read_csv(f'dreampath_processing/courses/data/{dept_cleaned}_courses_with_descriptions.csv')
    candidate_course = dept_courses[dept_courses['course_code'] == course_code]

    if len(candidate_course) == 0:
        return None

    return candidate_course.iloc[0]

# Checking if course is a major course
def is_major_course(course_code, major_name):
    department_alias_for_course = get_department_from_course_code(course_code)
    major_alias = get_department_alias_from_dept_name(major_name)

    return (department_alias_for_course == major_alias)

def build_prereq_tree(course_code, base_tokens=("IP"), visited=None, prereq_accumulator=None):
    if visited is None:
        visited = set()
    if prereq_accumulator is None:
        prereq_accumulator = set()
    if course_code in visited:
        return {course_code: "cyclic"}  # or just skip if preferred
    visited.add(course_code)

    enhanced_course = retrieve_enhanced_course_from_course_code(course_code)
    if enhanced_course is None:
        print(f"Course {course_code} not found")
        return {}, set()

    prereq_children = eval(enhanced_course['best_prereq_path'])

    tree_children = []
    for child in prereq_children:
        if child in base_tokens:
            tree_children.append(child)
        elif child not in ('AP', 'LP'):
            prereq_accumulator.add(child)
            subtree, _ = build_prereq_tree(child, base_tokens, visited.copy(), prereq_accumulator)
            tree_children.append(subtree)

    return {course_code: tree_children}, prereq_accumulator

# Building course graph for major and complementary courses
def merge_prereq_trees_to_graph(prereq_trees):
    """
    trees: list of nested dicts (each representing one course's tree)
    returns:
        - dict of {prereq: set of courses that depend on it}
        - full set of all courses mentioned (nodes in the graph)
    """
    graph = defaultdict(set)
    all_courses = set()

    def extract_edges(tree):
        edges = []

        def dfs(course, children):
            all_courses.add(course)
            for child_dict in children:
                if isinstance(child_dict, dict):
                    for prereq, grand_children in child_dict.items():
                        edges.append((prereq, course))
                        all_courses.add(prereq)
                        dfs(prereq, grand_children)
                else:
                    print(f'Likely IP/AP/LP encountered: {child_dict}')

        for course, prereq_children in tree.items():
            dfs(course, prereq_children)

        return edges

    for prereq_tree in prereq_trees:
        edges = extract_edges(prereq_tree)
        for prereq, course in edges:
            graph[prereq].add(course)

    # Ensure nodes with no edges still appear
    for course in all_courses:
        graph.setdefault(course, set())

    return graph, all_courses

def handle_course_queue(in_degree, term, course_scheduling_windows={}, verbose=False):
    simple_ready = []
    for c in in_degree:
        if in_degree[c] == 0:
            if c in course_scheduling_windows:
                c_start_term, c_end_term = course_scheduling_windows[c]
                if term >= c_start_term and term <= c_end_term:
                    simple_ready.append(c)
                elif verbose:
                    print(f"Course {c} not ready, curr_term={term} but requires {course_scheduling_windows[c]}")
            else:
                simple_ready.append(c)

    return deque(sorted(simple_ready))

# Producing course path
def schedule_courses_by_term(course_graph, course_bank, existing_plan=None, course_scheduling_windows={}, max_terms=12, max_courses_per_term=3, verbose=False):
    # Build in-degree and adjacency
    in_degree = defaultdict(int)
    adjacency = defaultdict(list)

    for prereq, courses in course_graph.items():
        for course in courses:
            in_degree[course] += 1
            adjacency[prereq].append(course)

    all_courses = set(course_graph.keys()) | {c for cs in course_graph.values() for c in cs}
    for course in all_courses:
        in_degree.setdefault(course, 0)

    # Begin scheduling, initial ready queue (sorted for determinism)
    term = 0
    ready = handle_course_queue(in_degree, term, course_scheduling_windows)
    scheduled = set()

    plan = copy.deepcopy(existing_plan)
    if not plan:
        plan = [[] for _ in range(max_terms)]

    # Iterate while there are still unscheduled courses and not yet reached max # of terms
    while (scheduled != all_courses) and term < max_terms:
        courses_this_term = plan[term]

        if verbose: 
            print(f"--------\nCurrentTerm: {term} | courses={courses_this_term}")

        next_ready = set()

        # Split ready queue by type
        majors_ready = sorted([c for c in ready if (c in course_bank and course_bank[c].course_type == MAJOR)])
        comps_ready = sorted([c for c in ready if (c in course_bank and course_bank[c].course_type == COMPLEMENTARY)])

        if verbose:
            print(f"--> All ready: {ready}")
            print(f"--> Majors_ready: {majors_ready}")
            print(f"--> Compl ready: {comps_ready}")

        majors_added = 0
        comps_added = 0

        # Phase 1: Add up to 2 majors
        for course in majors_ready:
            if len(courses_this_term) < max_courses_per_term and majors_added < 2:
                courses_this_term.append(course)
                ready.remove(course)
                scheduled.add(course)
                course_bank[course].scheduled = True
                majors_added += 1

        # Phase 2: Always try to add 1 complementary
        for course in comps_ready:
            if len(courses_this_term) < max_courses_per_term and comps_added < 1:
                courses_this_term.append(course)
                ready.remove(course)
                scheduled.add(course)
                course_bank[course].scheduled = True
                comps_added += 1

        # Phase 3: Fill remaining slots with any ready courses (prefer complementary)
        remaining_ready = sorted(list(ready), key=lambda course: (
            0 if (course in course_bank and course_bank[course].course_type == COMPLEMENTARY) else 1,
            course
        ))

        for course in remaining_ready:
            if len(courses_this_term) >= max_courses_per_term:
                break
            courses_this_term.append(course)
            ready.remove(course)
            scheduled.add(course)
            course_bank[course].scheduled = True

        # Update in-degrees and build next ready list
        for course in courses_this_term:
            for dependent in adjacency[course]:
                in_degree[dependent] -= 1
                # Add courses that have preerqs scheduled, haven't been scheduled yet, and don't have specific windows (those w/ windows handled next)
                if in_degree[dependent] == 0 and dependent not in scheduled and dependent not in course_scheduling_windows:
                    next_ready.add(dependent)

        # Handle courses with term requirements (if present)
        if course_scheduling_windows:
            scheduled_with_term_reqs = set()
            for course, term_reqs in course_scheduling_windows.items():
                if course not in scheduled:
                    if in_degree[course] == 0:
                        c_start_term, c_end_term = term_reqs
                        next_term = term + 1
                        if next_term >= c_start_term and next_term <= c_end_term:
                            next_ready.add(course)
                            scheduled_with_term_reqs.add(course)
                        else:
                            if verbose:                                
                                print(f"* Unscheduled course {course} not ready, curr_term={term+1} but requires {term_reqs}")
                            if course in ready: # Meaning, course was previously within window but is now outside and thus cannot be scheduled
                                ready.remove(course)
                                if verbose:
                                    print(f"--> Removed course {course} from 'ready' due to passing scheduling window")

                    elif verbose:
                            print(f"* Unscheduled course {course} not ready, indeg={in_degree[course]} (next_term={term+1}, requires {term_reqs})")

            # Remove scheduled courses from term_req map
            for scheduled_c in scheduled_with_term_reqs:
                course_scheduling_windows.pop(scheduled_c)    

        ready = deque(sorted(set(ready) | next_ready))
        plan[term] = courses_this_term
        term += 1

    # Determine which courses were not scheduled and update course bank
    unscheduled = set(all_courses) - scheduled
    if unscheduled:
        print(f"* Unscheduled courses: {sorted(unscheduled)}")

        for c in unscheduled:
            course_bank[c].scheduled = False

    # Confirmation that scheduled set is the same of course_bank scheduled set
    scheduled_from_bank = {c for c in course_bank if course_bank[c].scheduled}
    if scheduled != scheduled_from_bank:
        print(f"* Scheduled from bank: {scheduled_from_bank}")
        print(f"* Scheduled: {scheduled}")
        print(f"* Scheduled set mismatch: {scheduled} != {scheduled_from_bank}")
    else:
        print(f"* Scheduled set matches bank: {scheduled} == {scheduled_from_bank}")

    return plan, scheduled, unscheduled

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
            prereq_obj = course_bank.get(prereq, Course(course_code=prereq, course_type=course_bank[course].course_type))
            prereq_obj.is_prereq = True
            course_bank[prereq] = prereq_obj

    # Build course graph
    prereq_graph, all_courses = merge_prereq_trees_to_graph(prereq_trees)

    print("---")

    if visualize_course_connections:
        flattened_graph = flatten_graph_dict(prereq_graph)
        visualize_graph(flattened_graph, all_courses)

    # Build course path
    course_path, _, _ = schedule_courses_by_term(course_graph=prereq_graph, course_bank=course_bank, max_terms=12, max_courses_per_term=3)

    # Formalize output course path
    output_course_path = CoursePath(course_path=course_path,
                                    recommended_courses=recommended_courses,
                                    course_bank=course_bank,
                                    prereq_graph=prereq_graph)

    return output_course_path


if __name__ == '__main__':
    major_courses = {'COSC89.27', 'COSC55', 'COSC89.20', 'COSC35', 'COSC89.17', 'COSC89.28', 'COSC62', 'COSC69.17', 'COSC89.19', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}

    course_path = build_course_path(major_courses, complementary_courses)
    print(course_path)
