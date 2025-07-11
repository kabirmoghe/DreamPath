from dreampath_processing.courses.build_major_course_path import build_prereq_tree, merge_prereq_trees_to_graph, build_course_path, schedule_courses_by_term
from collections import defaultdict, deque
from typing import Tuple, List, Set, Dict, Any
import copy
from schedule_modules.course_path import CoursePath

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

def schedule_general_courses_by_term(course_graph, all_courses, existing_plan=None, max_terms=12, max_courses_per_term=3):
    # Build in-degree and adjacency
    in_degree = defaultdict(int)
    adjacency = defaultdict(list)

    for prereq, courses in course_graph.items():
        for course in courses:
            in_degree[course] += 1
            adjacency[prereq].append(course)
            
    for course in all_courses:
        in_degree.setdefault(course, 0)

    # Initial ready queue (sorted for determinism)
    print(course_graph)
    print(all_courses)
    print(in_degree)
    ready = deque(sorted([c for c in in_degree if in_degree[c] == 0]))
    scheduled = set()
    
    # Init plan object copy for tentative changes
    if existing_plan:
        plan = copy.deepcopy(existing_plan)
    else:
        plan = [[] for _ in range(max_terms)]

    term_idx = 0
    while ready and term_idx < max_terms:
        print(f"Term_idx: {term_idx}")
        print(ready)
        courses_this_term = plan[term_idx]
        next_ready = []

        # Split ready queue by type
        courses_ready = sorted([c for c in ready if c in all_courses])

        # Add courses
        for course in courses_ready:
            if len(courses_this_term) < max_courses_per_term:
                existing_courses = set([course for term in plan[:term_idx + 1] for course in term])
                if course not in existing_courses:
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
        plan[term_idx] = courses_this_term
        term_idx += 1

    unscheduled = set(all_courses) - scheduled

    if unscheduled:
        print(f"Unscheduled courses: {sorted(unscheduled)}")

    return plan, scheduled, unscheduled, term_idx

def schedule_must_have_courses(course_path: List[List[str]], window_start_term: int, must_have_courses: Dict[str, Tuple[int, int]], verbose: bool = False) -> Dict[str, Any]: 
    max_terms = len(course_path)
   
    # Validate curr_term pointer
    if (window_start_term <= 0) or (window_start_term >= max_terms): 
        raise ValueError("Window start term pointer must be within course_path list.")
    
    external_courses = set([course for term in course_path[:window_start_term] for course in term])
    courses_by_end_term = {}

    # Group courses by end term (i.e., latest term they must be scheduled by) | 
    for c, must_have_window in must_have_courses.items(): 
        # Get window and validate
        c_start_term = must_have_window[0]
        c_end_term = must_have_window[1]

        if c_start_term > c_end_term or c_start_term < window_start_term or c_end_term > max_terms:
            raise ValueError(f"Invalid scheduling window {must_have_window} for course {c}.")

        curr_c_by_end_term = courses_by_end_term.get(c_end_term, set())
        curr_c_by_end_term.add(c)
        courses_by_end_term[c_end_term] = curr_c_by_end_term

    # Begin modifying the course path
    mod_course_path = [[] for _ in range(max_terms - window_start_term)]
    all_scheduled_courses = set()

    # Iterate in order of earliest end-term requirement
    for end_term_idx, term_courses in sorted(courses_by_end_term.items(), key=lambda item: item[0]):
        course_prereq_map = {}
        course_prereq_tree_depth = {}
        
        for c in term_courses:
            c_prereq_tree, _ = build_prereq_tree(c)
            course_prereq_map[c] = c_prereq_tree
            course_prereq_tree_depth[c] = compute_max_prereq_depth(c_prereq_tree)    
        
        course_prereq_scheduling_priority = sorted(course_prereq_tree_depth, key=course_prereq_tree_depth.get, reverse=True)

        # Iterate through courses from course with most prereqs, to least
        for curr_priority_course in course_prereq_scheduling_priority:
            curr_prereq_tree = course_prereq_map[curr_priority_course]
            window_prereq_tree = prereq_difference(curr_prereq_tree, external_courses)

            if verbose:
                print(f"Original prereq tree for course {curr_priority_course}: {curr_prereq_tree}")
                print(f"Window prereq tree: {window_prereq_tree}")

            # Invert dependency order to prereq --> course(s) that requires it
            window_prereq_graph, all_window_courses = merge_prereq_trees_to_graph([window_prereq_tree])
            window_prereqs_only = all_window_courses.difference({curr_priority_course})
            num_terms_for_window = end_term_idx - window_start_term + 1

            # Schedule with course window in mind, adjusting for relativity to modified path
            curr_priority_course_raw_window = must_have_courses[curr_priority_course]
            curr_priority_course_relative_window = {curr_priority_course: 
                                                        (curr_priority_course_raw_window[0] - window_start_term, curr_priority_course_raw_window[1] - window_start_term)
                                                    }
            
            tentative_course_path, scheduled_courses, unscheduled_courses = schedule_courses_by_term(course_graph=window_prereq_graph,
                                     all_major_courses=window_prereqs_only,
                                     all_complementary_courses={},
                                     existing_plan=mod_course_path,
                                     course_scheduling_windows=curr_priority_course_relative_window,
                                     max_terms=num_terms_for_window,
                                     verbose=True)
                
            # Check if any unscheduled courses
            if not unscheduled_courses: 
                # Update modified course path
                mod_course_path = tentative_course_path
            
                if verbose:
                    print(f"For course: {curr_priority_course}")
                    print(course_path[:window_start_term])
                    print(mod_course_path)
                    print(f'* Scheduled Courses: {scheduled_courses}')
                    print("===========================")

                # Update list of scheduled courses
                all_scheduled_courses = all_scheduled_courses | scheduled_courses
                all_scheduled_courses.add(curr_priority_course)
            else:
                print(f"* Cannot schedule course: {curr_priority_course} | Unscheduled courses: {unscheduled_courses}")

    return {"course_path": course_path[:window_start_term] + mod_course_path,
            "newly_scheduled_courses": all_scheduled_courses,
            "pre_window_courses": external_courses} 
        
def rebuild_course_path_post_modification(mod_course_path: List[List[str]], 
                                          locked_courses: Set[str], 
                                          prior_prereq_graph: Dict[str, List[dict]], 
                                          prior_all_major_courses: Set[str], 
                                          prior_all_complementary_courses: Set[str], 
                                          verbose: bool = False) -> CoursePath:
    if verbose:
        print("-----\nPruning overlapping courses, determining earliest term requirements...")

    # Build map from tentative modified course path, for courses to term scheduled to allow for prereq. awareness
    mod_course_to_term = {}
    for term_idx, term_courses in enumerate(mod_course_path):
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

    # Scheduling existing courses within modified plan
    modified_course_path_schedule, scheduled_courses, unscheduled_courses = schedule_courses_by_term(course_graph=unscheduled_graph,       
                             all_major_courses=prior_all_major_courses,
                             all_complementary_courses=prior_all_complementary_courses,
                             existing_plan=mod_course_path,
                             course_scheduling_windows=earliest_possible_term)
    
    complete_modified_course_path = CoursePath(course_path=modified_course_path_schedule,
                                     recommended_major_courses=prior_all_major_courses,
                                     all_major_courses=prior_all_major_courses,
                                     recommended_complementary_courses=prior_all_complementary_courses,
                                     all_complementary_courses=prior_all_complementary_courses,
                                     scheduled_courses=scheduled_courses,
                                     unscheduled_courses=unscheduled_courses,
                                     prereq_graph=prior_prereq_graph)

    return complete_modified_course_path

if __name__=='__main__':
    # -- 1. Build original course path --
    major_courses = {'COSC89.27', 'COSC55', 'COSC89.20', 'COSC35', 'COSC89.17', 'COSC89.28', 'COSC62', 'COSC69.17', 'COSC89.19', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}

    initial_course_path = build_course_path(major_courses, complementary_courses)

    print(f"\n-- ORIGINAL --")
    print(initial_course_path.course_path)

    # -- 2. Make changes --
    
    # 2.1. Remove courses test
    # sample_major_courses, sample_complementary_courses = remove_recommended_courses(major_courses, complementary_courses, {'COSC89.27', 'COGS44'})

    # 2.2. Schedule specific courses
    mod_schedule_output = schedule_must_have_courses(course_path=initial_course_path.course_path, window_start_term=7, must_have_courses={
        'COSC52': (7, 8),
        'COSC58': (8, 12),
        'COSC74': (7,11)
    }, verbose=True)

    ex_mod_course_path = mod_schedule_output['course_path']
    ex_newly_scheduled_courses = mod_schedule_output['newly_scheduled_courses']
    ex_pre_window_courses = mod_schedule_output['pre_window_courses']

    print("\n-- MODIFIED --")
    print(ex_mod_course_path)

    # -- 3. Rebuild course path --
    ex_locked_courses = ex_newly_scheduled_courses | ex_pre_window_courses

    ex_complete_modified_plan = rebuild_course_path_post_modification(mod_course_path=ex_mod_course_path,
                                          locked_courses=ex_locked_courses,
                                          prior_prereq_graph=initial_course_path.prereq_graph,
                                          prior_all_major_courses=initial_course_path.all_major_courses,
                                          prior_all_complementary_courses=initial_course_path.all_complementary_courses)
    print('\n-- FINAL PLAN --')
    print(ex_complete_modified_plan.course_path)
    if ex_complete_modified_plan.unscheduled_courses:
        print(f"* Unscheduled courses: {ex_complete_modified_plan.unscheduled_courses}")
