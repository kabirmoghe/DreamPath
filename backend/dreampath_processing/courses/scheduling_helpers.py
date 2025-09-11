from dreampath_processing.courses.course_relationship_handling import build_prereq_tree, merge_prereq_trees_to_graph, get_direct_prereqs, prune_prereqs_from_tree, compute_max_prereq_depth, rebuild_prereq_graph
from collections import defaultdict, deque
from typing import List, Set, Dict, Any, Tuple, Deque
import copy
from dreampath_processing.courses.schedule_modules.course import Course, MAJOR, COMPLEMENTARY

# -----------------------------------------------------
# SCHEDULING FUNCTIONS
# -----------------------------------------------------

def validate_plan(course_path: List[List[str]], course_bank: Dict[str, Course], verbose: bool = False) -> List[Dict]:
    """
    Validate a course plan by checking for duplicates and prerequisite violations

    Args:
        course_plan (list): List of lists, where each inner list represents a term and contains course codes
        course_bank (dict): Dictionary of course codes to Courses
        verbose (bool): Whether to print verbose output

    Returns:
        list: List of dictionaries, each containing a violation
    """
    if verbose:
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
    #    Note: if duplicate, this will pick the last occurrence, but that doesn't block
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

# -----------------------------------------------------
# SCHEDULE COURSES BY TERM
# -----------------------------------------------------

def _handle_course_queue(in_degree: Dict[str, int], term: int, course_scheduling_windows: Dict[str, Tuple[int, int]] = {}, verbose: bool = False) -> Deque[str]:
    """
    Handle the course queue

    Args:
        in_degree: Dictionary of course codes to in-degree
        term: Current term
        course_scheduling_windows: Dictionary of course codes to scheduling windows
        verbose: Whether to print verbose output

    Returns:
        Deque: Queue of courses
    """
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
def schedule_courses_by_term(course_graph: Dict[str, List[str]], 
                             course_bank: Dict[str, Course], 
                             existing_plan: List[List[str]] = None, 
                             course_scheduling_windows: Dict[str, Tuple[int, int]] = {}, 
                             window_start_term: int = 0, 
                             max_terms: int = 12, 
                             max_courses_per_term: int = 3, 
                             verbose: bool = False) -> List[List[str]]:
    """
    Schedule courses by term by prioritizing majors, then compls, then any remaining courses

    Args:
        course_graph: Dictionary of course codes to list of prerequisite courses
        course_bank: Dictionary of course codes to Courses
        existing_plan: Existing plan
        course_scheduling_windows: Dictionary of course codes to scheduling windows
        window_start_term: Current term
        max_terms: Maximum number of terms
        max_courses_per_term: Maximum number of courses per term
        verbose: Whether to print verbose output

    Returns:
        dict: Dictionary containing the plan, scheduled courses, and unscheduled courses
    """
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
    term = window_start_term
    ready = _handle_course_queue(in_degree, term, course_scheduling_windows)
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
                course_bank[course].term_idx = term
                majors_added += 1

        # Phase 2: Always try to add 1 complementary
        for course in comps_ready:
            if len(courses_this_term) < max_courses_per_term and comps_added < 1:
                courses_this_term.append(course)
                ready.remove(course)
                scheduled.add(course)
                course_bank[course].scheduled = True
                course_bank[course].term_idx = term
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
            course_bank[course].term_idx = term

        # Update in-degrees and build next ready list
        for course in courses_this_term:
            for dependent in adjacency[course]:
                in_degree[dependent] = max(0, in_degree[dependent] - 1)
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
            course_bank[c].term_idx = None

    return {
        "plan": plan,
        "scheduled": scheduled,
        "unscheduled": unscheduled
    }

# -----------------------------------------------------
# RE-SCHEDULING FOR MUST-HAVE COURSES (i.e., courses that must be scheduled in a given window)
# -----------------------------------------------------

def schedule_must_have_courses(course_path: List[List[str]], prior_course_bank: Dict[str, Course], window_start_term: int, must_have_course_map: Dict[str, Course], verbose: bool = False) -> Dict[str, Any]: 
    """
    Schedule must-have courses by term

    Args:
        course_path: List of lists, where each inner list represents a term and contains course codes
        prior_course_bank: Dictionary of course codes to Courses from previous course path
        window_start_term: Current term
        must_have_course_map: Dictionary of course codes to Courses that must be scheduled in a given window
        verbose: Whether to print verbose output

    Returns:
        dict: Dictionary containing the must-have course path, must-have course bank, newly scheduled courses, newly scheduled must-have courses, and pre-window courses
    """
    max_terms = len(course_path)

    # Validate curr_term pointer
    if (window_start_term < 0) or (window_start_term >= max_terms): 
        raise ValueError("Window start term pointer must be within course_path list.")
    
    external_courses = set([course for term in course_path[:window_start_term] for course in term])
    courses_by_end_term = {}

    # Group courses by end term (i.e., latest term they must be scheduled by)
    for c, c_object in must_have_course_map.items():
        if c in external_courses:
            if verbose:
                print(f"Skipping must-have course '{c}', already scheduled outside window")
            continue

        # Get window and validate
        if c_object.must_have_window is None:
            c_object.must_have_window = (0, max_terms - 1) # Default to full term if no window

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
    newly_scheduled_must_have_courses = set()
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
            
            tentative_course_path_components = schedule_courses_by_term(course_graph=window_prereq_graph,
                                     course_bank=must_have_course_bank,
                                     existing_plan=must_have_course_path,
                                     course_scheduling_windows=curr_priority_course_relative_window,
                                     max_terms=num_terms_for_window,
                                     verbose=verbose)
            
            tentative_course_path = tentative_course_path_components["plan"]
            scheduled_courses = tentative_course_path_components["scheduled"]
            unscheduled_courses = tentative_course_path_components["unscheduled"]

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
                newly_scheduled_must_have_courses.add(curr_priority_course)

                # Update mod_course_bank to indicate scheduled courses
                for c in scheduled_courses:
                    must_have_course_bank[c].scheduled = True
                    must_have_course_bank[c].term_idx += window_start_term
            elif verbose:
                print(f"* Cannot schedule course: {curr_priority_course} | Unscheduled courses: {unscheduled_courses}")

    return {"must_have_course_path": course_path[:window_start_term] + must_have_course_path,
            "must_have_course_bank": must_have_course_bank,
            "newly_scheduled_courses": all_scheduled_courses,
            "newly_scheduled_must_have_courses": newly_scheduled_must_have_courses,
            "pre_window_courses": external_courses} 
        
def integrate_recommendations_and_must_have_courses(must_have_course_path: List[List[str]], 
                                          locked_courses: Set[str], 
                                          prior_prereq_graph: Dict[str, List[dict]], 
                                          must_have_course_bank: Dict[str, Course],
                                          prior_course_bank: Dict[str, Course],
                                          window_start_term: int,
                                          verbose: bool = False) -> Dict[str, Any]: 
    """
    Integrate previous recommendations and must-have courses

    Args:
        must_have_course_path: List of lists, where each inner list represents a term and contains course codes
        locked_courses: Set of courses that must be scheduled in a given window
        prior_prereq_graph: Dictionary of course codes to list of prerequisite courses
        must_have_course_bank: Dictionary of course codes to Courses that must be scheduled in a given window
        prior_course_bank: Dictionary of course codes to Courses from previous course path
        window_start_term: Current term
        verbose: Whether to print verbose output

    Returns:
        dict: Dictionary containing the modified course path post-must-have course integration and complete course bank
    """

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

                if adjusted_earliest_term_for_d > earliest_term_for_dependents and verbose:
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

    if verbose:
        print("Prior course bank:")
        for c in prior_course_bank.values():
            print(c)

        print("Must-have course bank:")
        for c in must_have_course_bank.values():
            print(c)

    # Scheduling existing courses within modified plan
    modified_course_path_components = schedule_courses_by_term(course_graph=unscheduled_graph, 
                             course_bank=complete_course_bank, 
                             existing_plan=must_have_course_path, 
                             course_scheduling_windows=earliest_possible_term,
                             window_start_term=window_start_term,
                             verbose=verbose)
    
    modified_course_path = modified_course_path_components["plan"]
    
    if verbose:
        print("Complete course bank:")
        for c in complete_course_bank.values():
            print(c)
                             

    return {
        "modified_course_path": modified_course_path,
        "complete_course_bank": complete_course_bank
    }