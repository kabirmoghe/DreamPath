import re
import json
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Set
from dreampath_processing.courses.schedule_modules.course import Course

# -----------------------------------------------------
# External course information extraction / confirmation
# -----------------------------------------------------
def get_department_from_course_code(course_code):
    """
    Get the department from a given course code

    Args:
        course_code: str - Course code to get the department from

    Returns:
        Tuple[str, str] - Tuple of department alias and course number
    """
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

def get_department_alias_from_dept_name(dept_name):
    """
    Get the department alias from a given department name

    Args:
        dept_name: str - Department name to get the alias from

    Returns:
        str - Department alias
    """
    dept_alias_to_name = json.load(open('dreampath_processing/courses/data/department_aliases.json'))
    dept_name_to_alias = {v: k for k, v in dept_alias_to_name.items()}
    dept_alias = dept_name_to_alias.get(dept_name, None)

    # Ensure provided department name has corresponding alias
    if not dept_alias:
        raise ValueError(f"Department name {dept_name} does not exist.")
    
    return dept_alias

def retrieve_enhanced_course_from_course_code(course_code):
    """
    Retrieve the enhanced course from a given course code

    Args:
        course_code: str - Course code to retrieve the enhanced course from

    Returns:
        DataFrame - DataFrame of the enhanced course
    """
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

def course_code_exists(course_code: str) -> bool:
    """Check if a course code exists in the master course list"""
    enhanced_course = retrieve_enhanced_course_from_course_code(course_code)

    return enhanced_course is not None

def is_major_course(course_code: str, major_name: str) -> bool:
    """Check if a course code is a major course"""
    department_alias_for_course = get_department_from_course_code(course_code)
    major_alias = get_department_alias_from_dept_name(major_name)

    return (department_alias_for_course == major_alias)

# -----------------------------------------------------
# Prereq. operations
# -----------------------------------------------------

# Building prerequisite tree for individual courses
def build_prereq_tree(course_code, base_tokens=("IP"), visited=None, prereq_accumulator=None):
    """
    Build the prereq. tree for a given course code

    Args:
        course_code: str - Course code to build the prereq. tree for
        base_tokens: Set[str] - Set of base tokens to treat as childless nodes
        visited: Set[str] - Set of visited courses
        prereq_accumulator: Set[str] - Set of courses that have been added to the prereq. tree

    Returns:
        Dict[str, Set[str]] - Dictionary of prereq. trees
    """
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
                    pass
                    # print(f'Likely IP/AP/LP encountered: {child_dict}')

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

# Rebuild prereq graph for bank of courses
def rebuild_prereq_graph(course_bank: Dict[str, Course], courses: Set[str]=None) -> Dict[str, Set[str]]:
    """
    Rebuild the prereq. graph for a given set of courses

    Args:
        course_bank: Dict[str, Course] - Dictionary of courses
        courses: Set[str] - Set of courses to rebuild the prereq. graph for

    Returns:
        Dict[str, Set[str]] - Dictionary of prereq. trees
    """
    course_prereq_trees = []

    if not courses:
        courses = course_bank.keys()

    for c in courses:
        c_object = course_bank.get(c)

        if c_object is None:
            raise ValueError(f"Course '{c}' not found in course bank.")
        
        c_prereq_tree = c_object.prereq_tree
        if c_prereq_tree:
            pass
            # print(f"Using existing prereq_tree for course '{c}'.")
        else:
            # print(f"Building new prereq_tree for course '{c}...")
            c_prereq_tree, _ = build_prereq_tree(c)
            c_object.prereq_tree = c_prereq_tree

        course_prereq_trees.append(c_prereq_tree)
    
    rebuilt_prereq_graph, all_courses_post_merge = merge_prereq_trees_to_graph(course_prereq_trees)

    return rebuilt_prereq_graph

# Get direct prereqs (i.e., direct children) for course
def get_direct_prereqs(prereq_tree, course_code):
    """
    Get direct prereqs for a given course code from a prereq. tree

    Args:
        prereq_tree (dict): Prereq. tree for a course
        course_code (str): Course code to get direct prereqs for

    Returns:
        list: List of direct prereqs for the given course code
    """
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
        pass
        # print(f'Error getting direct prereqs for {course_code}')
        # print(prereq_tree)
    return direct_children

# Remove prereq. branches for a given set of courses
def prune_prereqs_from_tree(prereq_tree, to_prune):
    """
    Prune any branch whose root is in `to_remove`, and return the pruned tree

    Args:
        prereq_tree (dict): Prereq. tree to prune
        to_remove (set): Set of course codes to remove from the prereq. tree

    Returns:
        dict: Pruned prereq. tree
    """

    def _prune(node):
        pruned = {}
        for course, children in node.items():
            if course in to_prune:
                continue
            pruned_children = []
            for child in children:
                # recursively prune subtrees
                pruned_sub = _prune(child)
                if pruned_sub:
                    pruned_children.append(pruned_sub)
            pruned[course] = pruned_children
        return pruned

    pruned_tree = _prune(prereq_tree)

    return pruned_tree

# Helper for calculating # of ancestral prereqs. for a given course's prereq. tree
def compute_max_prereq_depth(prereq_tree): 
    """
    Compute the maximum depth of a prereq. tree

    Args:
        prereq_tree (dict): Prereq. tree to compute the maximum depth of

    Returns:
        int: Maximum depth of the prereq. tree
    """
    def _depth_traverse(prereq_tree: dict, depth: int) -> int: 
        root_node = list(prereq_tree.keys())[0]
        children = prereq_tree[root_node]
        if children: 
            return max([_depth_traverse(prereq_child_tree, depth + 1) for prereq_child_tree in children])
        else:
            return depth
    
    return _depth_traverse(prereq_tree, 0)