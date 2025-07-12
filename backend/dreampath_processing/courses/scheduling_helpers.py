from dreampath_processing.courses.build_major_course_path import build_prereq_tree, merge_prereq_trees_to_graph, build_course_path, schedule_courses_by_term, is_major_course
from collections import defaultdict, deque
from typing import Tuple, List, Set, Dict, Any
import copy
from schedule_modules.course_path import CoursePath
from schedule_modules.course import Course, MAJOR, COMPLEMENTARY

# ─────────────────────────────────────────────────────────────────────────────
# COURSE CHANGE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def forcefully_remove_course(course_path, term_idx, course_to_remove):
    # Validate term_idx
    if term_idx < 0 or term_idx >= len(course_path):
        raise ValueError(f"term_idx must be in range [0, {len(course_path) - 1}]")
    
    if course_to_remove in course_path[term_idx]:
        course_path[term_idx].remove(course_to_remove) 
    else:
        raise ValueError(f"Course '{course_to_remove}' not in specified term '{term_idx}' for course_path.")
    
def remove_recommended_courses(major_course_recommendations: set, complementary_course_recommendations: set, courses_to_remove: set) -> Tuple[set, set]:
    mod_major_course_recommendations = copy.deepcopy(major_course_recommendations)
    mod_complementary_course_recommendations = complementary_course_recommendations
   
    for c in courses_to_remove:
        if c in major_course_recommendations:
            mod_major_course_recommendations.remove(c)
            print(f"Removed recommended major course '{c}")
        elif c in mod_complementary_course_recommendations:
            mod_complementary_course_recommendations.remove(c)
            print(f"Removed recommended complementary course '{c}")
        # Validate courses
        else:
            raise ValueError(f"Course '{c}' not in provided set of major or complementary course recommendations.")
        
    return mod_major_course_recommendations, mod_complementary_course_recommendations

def replace_course(course_path, term_idx, old_course, new_course):
    # Validate term_idx
    if term_idx < 0 or term_idx >= len(course_path):
        raise ValueError(f"term_idx must be in range [0, {len(course_path) - 1}]")

    # Extract position of old course in term
    old_course_idx = course_path[term_idx].index(old_course) if old_course in course_path[term_idx] else None

    if old_course_idx:
        # Replace old course with new course
        course_path_swapped = copy.deepcopy(course_path)
        course_path_swapped[term_idx][old_course_idx] = new_course

        return course_path_swapped
    else:
        raise ValueError(f"Course '{old_course}' not in specified term '{term_idx}' for course_path.") # Invalid course for replacement

# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

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
        print(f'Error getting direct prereqs for {course_code}')
        print(prereq_tree)
    return direct_children

def validate_plan(course_plan, direct_prereq_map):
    """
    Validate a course plan by checking for duplicates and prerequisite violations

    Args:
        course_plan (list): List of lists, where each inner list represents a term and contains course codes
        direct_prereq_map (dict): Dictionary mapping course codes to their direct prereqs
    """
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

# ─────────────────────────────────────────────────────────────────────────────
# PREREQ. OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def prereq_difference(prereq_tree: Dict[str, List[dict]], to_remove: Set[str]) -> Dict[str, List[dict]]:
    """
    Prune any branch whose root is in `to_remove`, and return the pruned tree

    Args:
        prereq_tree (dict): Prereq. tree to prune
        to_remove (set): Set of course codes to remove from the prereq. tree

    Returns:
        dict: Pruned prereq. tree
    """

    def _prune(node: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
        pruned: Dict[str, List[dict]] = {}
        for course, children in node.items():
            if course in to_remove:
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

# ─────────────────────────────────────────────────────────────────────────────
# RE-SCHEDULING
# ─────────────────────────────────────────────────────────────────────────────

def schedule_must_have_courses(course_path: List[List[str]], prior_course_bank: Dict[str, Course], window_start_term: int, must_have_courses: Dict, verbose: bool = False) -> Dict[str, Any]: 
    max_terms = len(course_path)
   
    # Validate curr_term pointer
    if (window_start_term <= 0) or (window_start_term >= max_terms): 
        raise ValueError("Window start term pointer must be within course_path list.")
    
    external_courses = set([course for term in course_path[:window_start_term] for course in term])
    courses_by_end_term = {}

    # Group courses by end term (i.e., latest term they must be scheduled by)
    for c, c_info in must_have_courses.items(): 
        # Get window and validate
        must_have_window = c_info['window']
        c_start_term = must_have_window[0]
        c_end_term = must_have_window[1]

        if c_start_term > c_end_term or c_start_term < window_start_term or c_end_term > max_terms:
            raise ValueError(f"Invalid scheduling window {must_have_window} for course {c}.")

        curr_c_by_end_term = courses_by_end_term.get(c_end_term, set())
        curr_c_by_end_term.add(c)
        courses_by_end_term[c_end_term] = curr_c_by_end_term

    # Begin modifying the course path with must have courses | Keep track of newly scheduled courses 
    must_have_course_path = [[] for _ in range(max_terms - window_start_term)]
    all_scheduled_courses = set()
    must_have_course_bank = {}

    # Iterate in order of earliest end-term requirement
    for end_term_idx, term_courses in sorted(courses_by_end_term.items(), key=lambda item: item[0]):
        course_prereq_map = {}
        course_prereq_tree_depth = {}
        
        for c in term_courses:
            c_prereq_tree, c_prereq_set = build_prereq_tree(c)
            course_prereq_map[c] = c_prereq_tree
            course_prereq_tree_depth[c] = compute_max_prereq_depth(c_prereq_tree)  

            # Update must_have_course_bank with course + prereqs
            must_have_course_bank[c] = must_have_course_bank.get(c, must_have_courses[c]['course_object'])
            must_have_course_bank[c].prereq_tree = c_prereq_tree

            c_course_type = must_have_courses[c]['course_object'].course_type
            for prereq in c_prereq_set:
                must_have_course_bank[prereq] = must_have_course_bank.get(prereq, Course(course_code=prereq, course_type=c_course_type))
                must_have_course_bank[prereq].is_prereq = True

                # Avoids case where prereq has been scheduled in pre-window, meaning will not be scheduled in window
                if prereq in prior_course_bank:
                    must_have_course_bank[prereq].scheduled = prior_course_bank[prereq].scheduled

        # Iterate through courses from course with most prereqs, to least
        course_prereq_scheduling_priority = sorted(course_prereq_tree_depth, key=course_prereq_tree_depth.get, reverse=True)

        for curr_priority_course in course_prereq_scheduling_priority:
            curr_prereq_tree = course_prereq_map[curr_priority_course]
            window_prereq_tree = prereq_difference(curr_prereq_tree, external_courses)

            if verbose:
                print(f"Original prereq tree for course {curr_priority_course}: {curr_prereq_tree}")
                print(f"Window prereq tree: {window_prereq_tree}")

            # Invert dependency order to prereq --> course(s) that requires it
            window_prereq_graph, all_window_courses = merge_prereq_trees_to_graph([window_prereq_tree])
            # window_prereqs_only = all_window_courses.difference({curr_priority_course})
            num_terms_for_window = end_term_idx - window_start_term + 1

            # Schedule with course window in mind, adjusting for relativity to modified path
            curr_priority_course_raw_window = must_have_courses[curr_priority_course]['window']
            curr_priority_course_relative_window = {curr_priority_course: 
                                                        (curr_priority_course_raw_window[0] - window_start_term, curr_priority_course_raw_window[1] - window_start_term)
                                                    }
            
            tentative_course_path, scheduled_courses, unscheduled_courses = schedule_courses_by_term(course_graph=window_prereq_graph,
                                     course_bank=must_have_course_bank,
                                     existing_plan=must_have_course_path,
                                     course_scheduling_windows=curr_priority_course_relative_window,
                                     max_terms=num_terms_for_window,
                                     verbose=True)
                
            # Check if any unscheduled courses
            if not unscheduled_courses: 
                # Update modified course path
                must_have_course_path = tentative_course_path
            
                if verbose:
                    print(f"For course: {curr_priority_course}")
                    print(course_path[:window_start_term])
                    print(must_have_course_path)
                    print(f'* Scheduled Courses: {scheduled_courses}')
                    print("===========================")

                # Update list of scheduled courses
                all_scheduled_courses = all_scheduled_courses | scheduled_courses
                all_scheduled_courses.add(curr_priority_course)

                # Update mod_course_bank to indicate scheduled courses
                for c in scheduled_courses:
                    must_have_course_bank[c].is_scheduled = True
            else:
                print(f"* Cannot schedule course: {curr_priority_course} | Unscheduled courses: {unscheduled_courses}")

    return {"must_have_course_path": course_path[:window_start_term] + must_have_course_path,
            "must_have_course_bank": must_have_course_bank,
            "newly_scheduled_courses": all_scheduled_courses,
            "pre_window_courses": external_courses} 
        
def integrate_recommendations_and_must_have_courses(must_have_course_path: List[List[str]], 
                                          locked_courses: Set[str], 
                                          prior_prereq_graph: Dict[str, List[dict]], 
                                          must_have_course_bank: Dict[str, Course],
                                          prior_course_bank: Dict[str, Course],
                                          verbose: bool = False):
    if verbose:
        print("-----\nPruning overlapping courses, determining earliest term requirements...")

    # Build map from tentative modified course path, for courses to term scheduled to allow for prereq. awareness
    mod_course_to_term = {}
    for term_idx, term_courses in enumerate(must_have_course_path):
        for c in term_courses:
            mod_course_to_term[c] = term_idx

    # Remove scheduled courses from prior prereq. graph, keep track of earliest existing courses can be scheduled given modifications
    unscheduled_graph = copy.deepcopy(prior_prereq_graph)
    earliest_possible_term = {}
    for c in locked_courses:
        if c in prior_prereq_graph:
            c_dependents = unscheduled_graph.pop(c)
            earliest_term_for_dependents =  mod_course_to_term[c] + 1 # earliest possible term for c's dependents

            if verbose:
                print(f"* Found overlapping course scheduled. {c} in term={mod_course_to_term[c]}\n-> Earliest term for dependents = {earliest_term_for_dependents}")
                print(f"\t--> Dependents={c_dependents}")

            for d in c_dependents:
                earliest_possible_term[d] = (earliest_term_for_dependents, float('inf'))

    # If removed course (because of overlap), then remove from earliest can take
    for c in locked_courses:
        if c in earliest_possible_term:
            earliest_possible_term.pop(c)
            if verbose:
                print(f"Removed course {c} from unscheduled, removing from earliest-term requirements.")

    if verbose:
        print(f"Map for earliest valid term per course: {earliest_possible_term}")
        print("-----\nRunning Rescheduling...")

    # Create complete course bank from prior/existing course bank + "must have" course bank
    complete_course_bank = prior_course_bank | must_have_course_bank

    # Scheduling existing courses within modified plan
    modified_course_path_schedule, _, _ = schedule_courses_by_term(course_graph=unscheduled_graph, 
                             course_bank=complete_course_bank, 
                             existing_plan=must_have_course_path, 
                             course_scheduling_windows=earliest_possible_term)
                             

    return modified_course_path_schedule, complete_course_bank

def rebuild_modified_course_path(initial_course_path: CoursePath, 
                                 must_have_courses: Dict[str, Dict[str, Any]],
                                 verbose: bool = False) -> CoursePath:
    
    # 1. Schedule must have courses
    must_have_schedule_output = schedule_must_have_courses(course_path=initial_course_path.course_path, 
                                                           prior_course_bank=initial_course_path.course_bank, 
                                                           window_start_term=7, 
                                                           must_have_courses=must_have_courses,
                                                           verbose=verbose)
    
    # Get newly scheduled courses & pre-window courses
    must_have_course_path = must_have_schedule_output['must_have_course_path']
    must_have_course_bank = must_have_schedule_output['must_have_course_bank']
    newly_scheduled_courses = must_have_schedule_output['newly_scheduled_courses']
    pre_window_courses = must_have_schedule_output['pre_window_courses']

    # Define "locked" courses
    locked_courses = newly_scheduled_courses | pre_window_courses

    # 2. Integrate recommendations and must have courses
    modified_course_path_schedule, complete_course_bank = integrate_recommendations_and_must_have_courses(must_have_course_path=must_have_course_path,
                                                                                                        locked_courses=locked_courses,
                                                                                                        prior_prereq_graph=initial_course_path.prereq_graph,
                                                                                                        must_have_course_bank=must_have_course_bank,
                                                                                                        prior_course_bank=initial_course_path.course_bank,
                                                                                                        verbose=verbose)
    
    # 3. Rebuild course path

    # Combine recommended courses with top-level must-have courses
    complete_recommended_courses = initial_course_path.recommended_courses | must_have_courses.keys()

    # Build prereq. graph for complete course bank
    complete_course_prereq_trees = []
    for c in complete_course_bank:
        c_prereq_tree, c_prereq_set = build_prereq_tree(c)
        complete_course_prereq_trees.append(c_prereq_tree)
    
    complete_course_prereq_graph, _ = merge_prereq_trees_to_graph(complete_course_prereq_trees)

    # Build course path
    modified_course_path = CoursePath(course_path=modified_course_path_schedule,
                                      course_bank=complete_course_bank,
                                      prereq_graph=complete_course_prereq_graph,
                                      recommended_courses=complete_recommended_courses)

    return modified_course_path

if __name__=='__main__':
    
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

    # 2. Make changes
    must_have_courses = {'COSC52': {'course_object': Course(course_code='COSC52', course_type=MAJOR), 'window': (7, 8)},
                         'COSC58': {'course_object': Course(course_code='COSC58', course_type=MAJOR), 'window': (8, 12)},
                         'COSC74': {'course_object': Course(course_code='COSC74', course_type=MAJOR), 'window': (7,11)}}
    
    modified_course_path = rebuild_modified_course_path(initial_course_path, must_have_courses)

    print(f"\n-- MODIFIED COURSE PATH --")
    print(modified_course_path.course_path)