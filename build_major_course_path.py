import pandas as pd
import re
import json
from collections import defaultdict, deque
from course_path_visualization import flatten_graph_dict, visualize_graph

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

def retrieve_enhanced_course_from_course_code(course_code):
    # get department name from course code
    dept_alias, _ = get_department_from_course_code(course_code)
    dept_alias_map = json.load(open('data/department_aliases.json'))
    dept_raw = dept_alias_map[dept_alias]
    dept_cleaned = dept_raw.replace(' ', '_').lower()

    # get department courses
    dept_courses = pd.read_csv(f'data/{dept_cleaned}_courses_with_descriptions.csv')
    candidate_course = dept_courses[dept_courses['course_code'] == course_code]

    if len(candidate_course) == 0:
        return None

    return candidate_course.iloc[0]

def build_prereq_tree(course_code, base_tokens=("IP"), visited=None):
    if visited is None:
        visited = set()
    if course_code in visited:
        return {course_code: "cyclic"}  # or just skip if preferred
    visited.add(course_code)

    enhanced_course = retrieve_enhanced_course_from_course_code(course_code)
    if enhanced_course is None:
        print(f"Course {course_code} not found")
        return []

    prereq_children = eval(enhanced_course['best_prereq_path'])

    tree_children = []
    for child in prereq_children:
        if child in base_tokens:
            tree_children.append(child)
        elif child not in ('AP', 'LP'):
            subtree = build_prereq_tree(child, base_tokens, visited.copy())
            tree_children.append(subtree)

    return {course_code: tree_children}

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

# Producing course path
def schedule_courses_by_term(course_graph, course_type, max_terms=12, max_courses_per_term=3):
    from collections import defaultdict, deque

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

    # Initial ready queue (sorted for determinism)
    ready = deque(sorted([c for c in in_degree if in_degree[c] == 0]))
    scheduled = set()
    plan = [[] for _ in range(max_terms)]

    term = 0
    while ready and term < max_terms:
        courses_this_term = []
        next_ready = []

        # Split ready queue by type
        majors_ready = sorted([c for c in ready if course_type.get(c, 'unknown') == 'major'])
        comps_ready = sorted([c for c in ready if course_type.get(c, 'unknown') == 'complementary'])

        majors_added = 0
        comps_added = 0

        # Phase 1: Add up to 2 majors
        for course in majors_ready:
            if len(courses_this_term) < max_courses_per_term and majors_added < 2:
                courses_this_term.append(course)
                ready.remove(course)
                scheduled.add(course)
                majors_added += 1

        # Phase 2: Always try to add 1 complementary
        for course in comps_ready:
            if len(courses_this_term) < max_courses_per_term and comps_added < 1:
                courses_this_term.append(course)
                ready.remove(course)
                scheduled.add(course)
                comps_added += 1

        # Phase 3: Fill remaining slots with any ready courses (prefer complementary)
        remaining_ready = sorted(list(ready), key=lambda course: (
            0 if course_type.get(course, '') == 'complementary' else 1,
            course
        ))

        for course in remaining_ready:
            if len(courses_this_term) >= max_courses_per_term:
                break
            courses_this_term.append(course)
            ready.remove(course)
            scheduled.add(course)

        # Update in-degrees and build next ready list
        for course in courses_this_term:
            for dependent in adjacency[course]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0 and dependent not in scheduled:
                    next_ready.append(dependent)

        ready = deque(sorted(set(ready) | set(next_ready)))
        plan[term] = courses_this_term
        term += 1

    unscheduled = set(all_courses) - scheduled
    if unscheduled:
        print(f"Unscheduled courses: {sorted(unscheduled)}")

    return plan

def build_course_path(major_courses, complementary_courses):
    # Define course type map
    course_type_map = {course: 'major' for course in major_courses}
    course_type_map.update({course: 'complementary' for course in complementary_courses})

    # Build prereq trees
    prereq_trees = []

    print('Building prereq. trees for major courses...')
    for course in major_courses:
        # print(f'Prereq tree for {course}:')
        course_prereq_tree = build_prereq_tree(course)
        # print(course_prereq_tree)
        prereq_trees.append(course_prereq_tree)
        # print('--')

    print('Building prereq. trees for complementary courses...')
    for course in complementary_courses:
        # print(f'Prereq tree for {course}:')
        course_prereq_tree = build_prereq_tree(course)
        # print(course_prereq_tree)
        prereq_trees.append(course_prereq_tree)
        # print('--')

    # Create complete course graph; add prereq. courses to course type map
    prereq_graph, all_courses = merge_prereq_trees_to_graph(prereq_trees)

    for course in all_courses:
        course_type_map.setdefault(course, 'prereq')

    # Build course path
    course_path = schedule_courses_by_term(prereq_graph, course_type_map, max_terms=15, max_courses_per_term=3)

    return course_path


if __name__ == '__main__':
    major_courses = ['BIOL76', 'BIOL45', 'BIOL13', 'BIOL47', 'BIOL78', 'BIOL95', 'BIOL71.02', 'BIOL9', 'BIOL11.07', 'BIOL51']
    complementary_courses = ['CHEM95.02', 'CHEM42', 'CHEM96.06', 'CHEM95.03', 'CHEM40', 'ENGS35', 'CHEM96.05', 'ENGS5', 'ENGS15.03', 'ENGS58']

    course_path = build_course_path(major_courses, complementary_courses, )
    print(course_path)
