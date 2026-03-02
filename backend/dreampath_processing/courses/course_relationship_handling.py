from collections import defaultdict
from typing import Dict, List, Set, Optional, Tuple
from dreampath_processing.courses.schedule_modules.course import Course, MAJOR, COMPLEMENTARY, CourseType
from dreampath_processing.weaviate.course_service import WeaviateCourseService

DATA_DIR = "dreampath_processing/courses/data"

# Lazy initialization of Weaviate service
_weaviate_service = None

def get_weaviate_service():
    global _weaviate_service
    if _weaviate_service is None:
        _weaviate_service = WeaviateCourseService()
    return _weaviate_service

def is_major_course(course_code: str, major: str) -> bool:
    return get_weaviate_service().is_major_course(course_code, major)

def construct_course(course_code: str, major: Optional[str] = None, hardcoded_type: Optional[CourseType] = None, must_have_window: Optional[List[int]] = None) -> Course:
    """Construct a Course object from a course code and major name.

    Populates all available Weaviate metadata fields.
    """
    # Fetch from Weaviate
    wv_course = get_weaviate_service().get_course_by_code(course_code)

    if wv_course is None:
        print(f"Unknown course code '{course_code}'.")
        return None

    # Determine course type
    if not hardcoded_type:
        if not major:
            raise ValueError("Must provide major name if hardcoded_type is not provided")
        ctype = MAJOR if is_major_course(course_code, major) else COMPLEMENTARY
    else:
        ctype = hardcoded_type

    print(f"Constructing course: {course_code} | {ctype} | {must_have_window}")

    return Course(
        # Required
        course_code=course_code,
        course_type=ctype,
        # Scheduling state
        scheduled=False,
        is_prereq=False,
        prereq_tree=None,
        must_have_window=must_have_window,
        term_idx=None,
        term_idx_in_term=None,
        # DreamPath-specific (set later)
        aligned_parameters=None,
        # Basic course info
        course_title=wv_course.get('course_title'),
        course_description=wv_course.get('description'),
        department=wv_course.get('department'),
        prerequisites=wv_course.get('prerequisites'),
        course_url=wv_course.get('course_url'),
        num_prereqs=wv_course.get('num_prereqs'),
        total_reviews=wv_course.get('total_reviews'),
        # Difficulty metrics
        global_difficulty_percentile=wv_course.get('global_difficulty_percentile'),
        global_difficulty_classification=wv_course.get('global_difficulty_classification'),
        dept_difficulty_percentile=wv_course.get('dept_difficulty_percentile'),
        dept_difficulty_classification=wv_course.get('dept_difficulty_classification'),
        difficulty_blurb=wv_course.get('difficulty_blurb'),
        # Value metrics
        global_value_percentile=wv_course.get('global_value_percentile'),
        global_value_classification=wv_course.get('global_value_classification'),
        dept_value_percentile=wv_course.get('dept_value_percentile'),
        dept_value_classification=wv_course.get('dept_value_classification'),
        learning_value_blurb=wv_course.get('learning_value_blurb'),
        # Target audience
        target_audience_blurb=wv_course.get('target_audience_blurb'),
    )

# -----------------------------------------------------
# Prereq. operations
# -----------------------------------------------------
class PrereqGraph:
    def __init__(self, children, parents, all_courses):
        self.children: Dict[str, Set[str]] = children
        self.parents: Dict[str, Set[str]] = parents
        self.all_courses: Set[str] = all_courses

# -----------------------------------------------------
# Building prerequisite tree for individual courses
# -----------------------------------------------------
def build_prereq_tree(course_code, base_tokens=("IP", "AP", "LP"), visited=None, prereq_accumulator=None, verbose=False):
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

    enhanced_course = get_weaviate_service().get_course_by_code(course_code)
    if enhanced_course is None:
        if verbose:
            print(f"Course '{course_code}' not found...")
        return {}, set()

    prereq_children = eval(enhanced_course['best_prereq_path'])

    tree_children = []
    for child in prereq_children:
        if child not in base_tokens:
            prereq_accumulator.add(child)
            subtree, _ = build_prereq_tree(child, base_tokens, visited.copy(), prereq_accumulator, verbose)
            tree_children.append(subtree)
        elif verbose:
            print(f"Skipping base satisfaction token '{child}' for course '{course_code}'...")

    return {course_code: tree_children}, prereq_accumulator

# -----------------------------------------------------
# Merge prerequisite trees into a unified DAG
# -----------------------------------------------------
def merge_prereq_trees_to_graph(prereq_trees) -> PrereqGraph:
    """
    Merge prerequisite trees into a graph, represented as parents and children dictionaries
    """
    children = defaultdict(set)  # prereq -> dependents
    parents  = defaultdict(set)  # course -> prerequisites
    all_courses = set()

    def extract_edges(tree):
        edges = []
        def dfs(course, children_nodes):
            all_courses.add(course)
            for child in children_nodes:
                if isinstance(child, dict):
                    for prereq, grand_children in child.items():
                        edges.append((prereq, course))  # prereq -> course
                        all_courses.add(prereq)
                        dfs(prereq, grand_children)
                else:
                    # base tokens like IP/AP/LP: no edges
                    pass
                
        for course, kids in tree.items():
            dfs(course, kids)
        return edges

    for t in prereq_trees:
        for p, c in extract_edges(t):
            children[p].add(c)
            parents[c].add(p)

    for v in all_courses:
        children.setdefault(v, set())
        parents.setdefault(v, set())

    return PrereqGraph(children, parents, all_courses)

# -----------------------------------------------------
# Rebuild prereq graph from bank for specific courses and prune unwanted branches
# -----------------------------------------------------
def rebuild_prereq_graph(course_bank: Dict[str, Course], courses: Set[str]=None, to_prune: Set[str]=None) -> PrereqGraph:
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

        if to_prune:
            print(f"Pruning prereq. tree for course '{c}'...")
            c_prereq_tree = prune_prereqs_from_tree(c_prereq_tree, to_prune)

        course_prereq_trees.append(c_prereq_tree)
    
    rebuilt_prereq_graph = merge_prereq_trees_to_graph(course_prereq_trees)

    return rebuilt_prereq_graph

def find_lingering_courses(old_prereq_graph: PrereqGraph, new_prereq_graph: PrereqGraph) -> Set[str]:
    """
    Find lingering prereqs for a given set of courses
    """
    lingering_courses = set()
    for course in old_prereq_graph.children.keys():
        if course not in new_prereq_graph.children:
            lingering_courses.add(course)

    return lingering_courses

# Get direct prereqs (i.e., direct children) for course
def get_direct_prereqs(prereq_tree, course_code, verbose=False):
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
            elif verbose:
                    print(f"Empty prereq. tree for course '{course_code}'...")

        return direct_children
    except:
        if verbose:
            print(f"Error getting direct prereqs for course '{course_code}'...")
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