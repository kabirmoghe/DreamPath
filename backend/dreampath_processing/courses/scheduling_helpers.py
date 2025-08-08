from dreampath_processing.courses.build_major_course_path import build_prereq_tree, merge_prereq_trees_to_graph, build_course_path, schedule_courses_by_term
from dreampath_processing.courses.course_relationship_handling import get_direct_prereqs, prune_prereqs_from_tree, compute_max_prereq_depth, rebuild_prereq_graph
from collections import defaultdict, deque
from typing import Tuple, List, Set, Dict, Any
import copy
from schedule_modules.course_path import CoursePath
from schedule_modules.course import Course, MAJOR, COMPLEMENTARY

# -----------------------------------------------------
# SCHEDULING FUNCTIONS
# -----------------------------------------------------

def validate_plan(course_path: List[List[str]], course_bank: Dict[str, Course]):
    """
    Validate a course plan by checking for duplicates and prerequisite violations

    Args:
        course_plan (list): List of lists, where each inner list represents a term and contains course codes
    """
    print(f"Validating plan...")
    # 1. Build a mapping from course → list of terms it appears in
    occurrences = defaultdict(list)
    for term_idx, term_courses in enumerate(course_path):
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

    # Build direct prereq. map
    direct_prereq_map = {}
    for term in course_path:
        for course in term:
            # In case course prereq. tree is already built, use it; otherwise, build it
            course_obj = course_bank.get(course, None)
            if course_obj and course_obj.prereq_tree is not None:
                print(f"* Using prereq. tree for course {course} from course bank.")
                prereq_tree = course_obj.prereq_tree
            else:
                print(f"* Building prereq. tree for course {course}.")
                prereq_tree, _ = build_prereq_tree(course)

            direct_prereqs = get_direct_prereqs(prereq_tree, course)
            direct_prereq_map[course] = direct_prereqs

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

# -----------------------------------------------------
# RE-SCHEDULING FOR MUST-HAVE COURSES (i.e., courses that must be scheduled in a given window)
# -----------------------------------------------------

def schedule_must_have_courses(course_path: List[List[str]], prior_course_bank: Dict[str, Course], window_start_term: int, must_have_course_map: Dict[str, Course], verbose: bool = False) -> Dict[str, Any]: 
    max_terms = len(course_path)
   
    # Validate curr_term pointer
    if (window_start_term < 0) or (window_start_term >= max_terms): 
        raise ValueError("Window start term pointer must be within course_path list.")
    
    external_courses = set([course for term in course_path[:window_start_term] for course in term])
    courses_by_end_term = {}

    # Group courses by end term (i.e., latest term they must be scheduled by)
    for c, c_object in must_have_course_map.items():
        if c in external_courses:
            print(f"Skipping must-have course '{c}', already scheduled outside window")
            continue

        # Get window and validate
        must_have_window = c_object.must_have_window
        c_start_term = must_have_window[0]
        c_end_term = must_have_window[1]

        # Invalid window
        if c_start_term > c_end_term or c_end_term > max_terms or c_start_term < 0:
            raise ValueError(f"Invalid scheduling window {must_have_window} for course {c}.")

        # Can still attempt to schedule course if c_start_term < window_start_term but have to adjust window to start at window_start_term (for scheduling only)
        if c_start_term < window_start_term and c_end_term >= window_start_term:
            print(f"* Warning: adjusting course '{c} scheduling window from [{c_start_term}, {c_end_term}] to [{window_start_term}, {c_end_term}]")

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
            must_have_course_bank[c] = must_have_course_bank.get(c, must_have_course_map[c])
            must_have_course_bank[c].prereq_tree = c_prereq_tree
            must_have_course_bank[c].must_have_window = must_have_course_map[c].must_have_window

            c_course_type = must_have_course_map[c].course_type
            for prereq in c_prereq_set:
                must_have_course_bank[prereq] = must_have_course_bank.get(prereq, Course(course_code=prereq, course_type=c_course_type))
                must_have_course_bank[prereq].is_prereq = True

                # To maintain scheduling accuracy for pre-window courses upon mereging must-have and prior course banks
                if prereq in prior_course_bank:
                    must_have_course_bank[prereq].scheduled = prior_course_bank[prereq].scheduled
                    must_have_course_bank[prereq].term_idx = prior_course_bank[prereq].term_idx

        # Iterate through courses from course with most prereqs, to least
        course_prereq_scheduling_priority = sorted(course_prereq_tree_depth, key=course_prereq_tree_depth.get, reverse=True)

        for curr_priority_course in course_prereq_scheduling_priority:
            # Eliminate prereqs that are already scheduled in pre-window
            curr_prereq_tree = course_prereq_map[curr_priority_course]
            window_prereq_tree = prune_prereqs_from_tree(curr_prereq_tree, external_courses)

            if verbose:
                print(f"Original prereq tree for course {curr_priority_course}: {curr_prereq_tree}")
                print(f"Window prereq tree: {window_prereq_tree}")

            # Invert dependency order to prereq --> course(s) that requires it
            window_prereq_graph, _ = merge_prereq_trees_to_graph([window_prereq_tree])
            num_terms_for_window = end_term_idx - window_start_term + 1

            # Schedule with course window in mind, adjusting for relativity to modified path
            curr_priority_course_raw_window = must_have_course_map[curr_priority_course].must_have_window

            curr_priority_course_rel_start = max(0, curr_priority_course_raw_window[0] - window_start_term) # Account for start < curr_window
            curr_priority_course_rel_end = curr_priority_course_raw_window[1] - window_start_term
            curr_priority_course_relative_window = {curr_priority_course: (curr_priority_course_rel_start, curr_priority_course_rel_end)}
            
            tentative_course_path, scheduled_courses, unscheduled_courses = schedule_courses_by_term(course_graph=window_prereq_graph,
                                     course_bank=must_have_course_bank,
                                     existing_plan=must_have_course_path,
                                     course_scheduling_windows=curr_priority_course_relative_window,
                                     max_terms=num_terms_for_window)
                
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
                    must_have_course_bank[c].scheduled = True
                    must_have_course_bank[c].term_idx += window_start_term
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
            earliest_term_for_dependents = mod_course_to_term[c] + 1

            if verbose:
                print(f"* Found overlapping course scheduled. {c} in term={mod_course_to_term[c]}\n-> Earliest term for dependents = {earliest_term_for_dependents}")
                print(f"\t--> Dependents={c_dependents}")

            for d in c_dependents:
                adjusted_earliest_term_for_d = max(earliest_term_for_dependents, earliest_possible_term.get(d, (0,))[0])

                if adjusted_earliest_term_for_d > earliest_term_for_dependents:
                    print(f"\t\t[Retaining previous earliest term for dependent {d} = {adjusted_earliest_term_for_d}]")

                earliest_possible_term[d] = (adjusted_earliest_term_for_d, float('inf'))

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

    print("Prior course bank:")
    for c in prior_course_bank.values():
        print(c)

    print("Must-have course bank:")
    for c in must_have_course_bank.values():
        print(c)

    # Scheduling existing courses within modified plan
    modified_course_path_schedule, _, _ = schedule_courses_by_term(course_graph=unscheduled_graph, 
                             course_bank=complete_course_bank, 
                             existing_plan=must_have_course_path, 
                             course_scheduling_windows=earliest_possible_term,
                             verbose=verbose)
    
    print("Complete course bank:")
    for c in complete_course_bank.values():
        print(c)
                             

    return modified_course_path_schedule, complete_course_bank

def rebuild_course_path_with_must_haves(initial_course_path: CoursePath, 
                                 window_start_term: int,
                                 must_have_course_map: Dict[str, Course] = {},
                                 verbose: int = 0) -> CoursePath:
    """
    Rebuild a course path with must-have courses and recommendations

    Args:
        initial_course_path (CoursePath): initial course path to rebuild
        window_start_term (int): term to start scheduling must-have courses
        must_have_course_map (dict): dictionary of must-have courses (containing must_have_window field)
        verbose (int): verbosity level (0 - 3)

    Returns:
        CoursePath: rebuilt course path with must-have courses and recommendations
    """
    
    # 1. Combine existing must-have courses with new must-have courses
    existing_must_have_courses_map = {c: initial_course_path.course_bank[c] for c in initial_course_path.must_have_courses}
    complete_must_have_courses_map = existing_must_have_courses_map | must_have_course_map

    # 2. Schedule must have courses
    must_have_schedule_output = schedule_must_have_courses(course_path=initial_course_path.course_path, 
                                                           prior_course_bank=initial_course_path.course_bank, 
                                                           window_start_term=window_start_term, 
                                                           must_have_course_map=complete_must_have_courses_map,
                                                           verbose=True if verbose >= 2 else False)
    
    # Get newly scheduled courses & pre-window courses
    must_have_course_path = must_have_schedule_output['must_have_course_path']
    must_have_course_bank = must_have_schedule_output['must_have_course_bank']
    newly_scheduled_courses = must_have_schedule_output['newly_scheduled_courses']
    pre_window_courses = must_have_schedule_output['pre_window_courses']

    if verbose >= 1:
        print(f"\n-- MUST-HAVE COURSE PATH --")
        print(must_have_course_path)
        print(f"\n* Newly scheduled courses: {newly_scheduled_courses}")
        print("-----\n")

    # 3. Remove window from unscheduled must-have courses
    unscheduled_new_must_haves = set(must_have_course_map.keys()) - newly_scheduled_courses
    for c in unscheduled_new_must_haves:
        must_have_course_bank[c].must_have_window = None
        complete_must_have_courses_map.pop(c)
        must_have_course_map.pop(c)
        must_have_course_bank.pop(c)

        if verbose >= 1:
            print(f"[Unable to schedule must-have course '{c}', removed from must-have courses]")

    # Define "locked" courses
    locked_courses = newly_scheduled_courses | pre_window_courses

    # 4. Integrate recommendations and must have courses
    modified_course_path_schedule, complete_course_bank = integrate_recommendations_and_must_have_courses(must_have_course_path=must_have_course_path,
                                                                                                        locked_courses=locked_courses,
                                                                                                        prior_prereq_graph=initial_course_path.prereq_graph,
                                                                                                        must_have_course_bank=must_have_course_bank,
                                                                                                        prior_course_bank=initial_course_path.course_bank,
                                                                                                        verbose=True if verbose >= 3 else False)
    
    # 5. Rebuild course path

    # Combine recommended courses with top-level must-have courses
    complete_recommended_courses = initial_course_path.recommended_courses | set(must_have_course_map.keys())

    # Build prereq. graph for complete course bank
    complete_course_prereq_graph = rebuild_prereq_graph(course_bank=complete_course_bank)

    # Update set of must-have courses; removed because gets rid of unscheduled must-haves from object even though may want to schedule moving fwd
    # scheduled_must_have_courses = set(must_have_courses.keys()) & newly_scheduled_courses
    # complete_must_have_courses = scheduled_must_have_courses | initial_course_path.must_have_courses 
    complete_must_have_courses = set(complete_must_have_courses_map.keys())
 
    # Build course path
    modified_course_path = CoursePath(course_path=modified_course_path_schedule,
                                      recommended_courses=complete_recommended_courses,
                                      course_bank=complete_course_bank,
                                      prereq_graph=complete_course_prereq_graph,
                                      must_have_courses=complete_must_have_courses)

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
    for c in initial_course_path.course_bank.values():
        print(c)

    #  # Test removal functionality
    # # removed_course_path = safely_remove_course(initial_course_path, 'COSC74', 8)
    # # print(f"\n-- REMOVED COURSE PATH --")
    # # print(removed_course_path.course_path)

    # 2. Make changes
    sample_must_have_course_map = {'COSC52': Course(course_code='COSC52', course_type=MAJOR, must_have_window=(7, 8)),
                         'COSC58': Course(course_code='COSC58', course_type=MAJOR, must_have_window=(2, 2)),
                         'COSC74': Course(course_code='COSC74', course_type=MAJOR, must_have_window=(6,9))}
    
    modified_course_path = rebuild_course_path_with_must_haves(initial_course_path, window_start_term=2, must_have_course_map=sample_must_have_course_map, verbose=True)

    print(f"\n-- MODIFIED COURSE PATH v1--")
    print(modified_course_path.course_path)
    print(f"Must-have courses: {modified_course_path.must_have_courses}")
    for c in modified_course_path.course_bank.values():
        print(c)

    # # 3. Make more changes
    # additional_must_have_course_map = {'QSS41': Course(course_code='QSS41', course_type=COMPLEMENTARY, must_have_window=(9, 9))}
    # modified_course_path = rebuild_course_path_with_must_haves(modified_course_path, window_start_term=6, must_have_course_map=additional_must_have_course_map, verbose=True)

    # print(f"\n-- MODIFIED COURSE PATH v2--")
    # print(modified_course_path.course_path)
    # print(f"Must-have courses: {modified_course_path.must_have_courses}")
    # for c in modified_course_path.course_bank.values():
    #     print(c)