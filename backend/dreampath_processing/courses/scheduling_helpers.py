from dreampath_processing.courses.course_relationship_handling import build_prereq_tree, merge_prereq_trees_to_graph, get_direct_prereqs, prune_prereqs_from_tree, compute_max_prereq_depth, rebuild_prereq_graph, PrereqGraph
from collections import defaultdict, deque
from typing import List, Set, Dict, Any, Tuple, Deque, Optional
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
def schedule_courses_by_term_legacy(course_graph: Dict[str, List[str]], 
                             course_bank: Dict[str, Course], 
                             existing_plan: List[List[str]] = None, 
                             course_scheduling_windows: Dict[str, Tuple[int, int]] = {}, 
                             window_start_term: int = 0, 
                             max_terms: int = 12, 
                             max_courses_per_term: int = 3, 
                             verbose: bool = False) -> Dict[str, Any]:
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

    if verbose:
        print(f"Scheduling courses by term...")
        print(f"Course graph: {course_graph}")

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
            ready_with_term_reqs = set()
            for course, term_reqs in course_scheduling_windows.items():
                if course not in scheduled:
                    if in_degree[course] == 0:
                        c_start_term, c_end_term = term_reqs
                        next_term = term + 1
                        if next_term >= c_start_term and next_term <= c_end_term:
                            next_ready.add(course)
                            ready_with_term_reqs.add(course)
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
            for ready_c in ready_with_term_reqs:
                course_scheduling_windows.pop(ready_c)    

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

                # Update external_courses to include newly scheduled courses
                external_courses = external_courses | scheduled_courses

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
        locked_courses: Courses scheduled outside of window
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

# ---------------------------------------
# Topological order (on the pruned subgraph)
# ---------------------------------------
def _topo_order(children: Dict[str, Set[str]], parents: Dict[str, Set[str]], nodes: Set[str]) -> List[str]:
    indeg = {v: len(parents.get(v, set())) for v in nodes}
    q = deque([v for v, d in indeg.items() if d == 0])
    order: List[str] = []
    while q:
        v = q.popleft()
        order.append(v)
        for w in children.get(v, set()):
            indeg[w] -= 1
            if indeg[w] == 0:
                q.append(w)
    if len(order) != len(nodes):
        raise ValueError("Cycle detected in prerequisite subgraph.")
    return order

# ---------------------------------------
# ASAP (forward pass)
# ---------------------------------------
def compute_asap_for_graph(prereq_graph, window_start_term: int, topo_order: List[str] = None) -> Dict[str, int]:
    """
    prereq_graph: PrereqGraph(children, parents, all_courses) on the pruned in-window DAG
    Returns: dict course -> earliest feasible term (ASAP)
    """
    parents = prereq_graph.parents

    order = topo_order
    asap: Dict[str, int] = {}
    for v in order:
        ps = parents.get(v, set())
        if ps:
            asap[v] = 1 + max(asap[p] for p in ps)
        else:
            asap[v] = window_start_term
    return asap

# ---------------------------------------
# ALAP (backward pass)
# ---------------------------------------
def compute_alap_for_graph(prereq_graph,
                           target_deadline_hi: Dict[str, int],
                           default_hi: int,
                           topo_order: List[str] = None) -> Dict[str, int]:
    """
    target_deadline_hi: deadlines for sink/target nodes (v -> latest term); others fall back to default_hi
    default_hi: e.g., max_terms - 1
    Returns: dict course -> latest feasible term (ALAP)
    """
    children = prereq_graph.children

    order = topo_order
    alap: Dict[str, int] = {}
    for v in reversed(order):
        cs = children.get(v, set())
        if cs:
            cand = min(alap[c] - 1 for c in cs)
        else:
            cand = target_deadline_hi.get(v, default_hi)
        if v in target_deadline_hi:
            cand = min(cand, target_deadline_hi[v])
        alap[v] = cand
    return alap

def build_scheduling_windows(prereq_graph,
                             asap: Dict[str, int],
                             alap: Dict[str, int],
                             window_start_term: int,
                             max_terms: int,
                             must_have_course_map: Dict[str, "Course"]) -> Dict[str, Tuple[int, int]]:
    """
    Clamp targets to their (lo, hi); others to full in-window horizon.
    """
    nodes = prereq_graph.all_courses
    windows: Dict[str, Tuple[int, int]] = {}
    for v in nodes:
        lo = asap[v]
        hi = alap[v]
        if v in must_have_course_map and must_have_course_map[v].must_have_window:
            tlo, thi = must_have_course_map[v].must_have_window
            lo = max(lo, tlo)
            hi = min(hi, thi)
        else:
            lo = max(lo, window_start_term)
            hi = min(hi, max_terms - 1)
        if lo > hi:
            raise ValueError(f"Infeasible window for {v}: [{lo}, {hi}]")
        windows[v] = (lo, hi)
    return windows

def schedule_courses_by_term(course_graph: PrereqGraph, 
                             course_bank: Dict[str, Course], 
                             existing_plan: List[List[str]] = None, 
                             course_scheduling_windows: Dict[str, Tuple[int, int]] = {}, 
                             window_start_term: int = 0, 
                             max_terms: int = 12, 
                             max_courses_per_term: int = 3,
                             verbose: bool = False) -> Dict[str, Any]:
    
    # Set up in-degree for each course
    in_degree = defaultdict(int)
    for _, child_courses in course_graph.children.items():
        for child_course in child_courses:
            in_degree[child_course] += 1
    
    for course in course_graph.all_courses:
        in_degree.setdefault(course, 0)

    # Initialize plan
    plan = copy.deepcopy(existing_plan)
    if not plan:
        plan = [[] for _ in range(max_terms)]

    def _in_window(course: str, term: int) -> bool:
        if course in course_scheduling_windows:
            return course_scheduling_windows[course][0] <= term <= course_scheduling_windows[course][1]
        return True
    
    # Set up priority function
    term = window_start_term
    scheduled = set()
    ready_since: Dict[str, int] = {}

    def _priority(course: str) -> Tuple[int, int, int, str]:
        # 1. Window
        lo, hi = course_scheduling_windows.get(course, (window_start_term, max_terms))

        # 2. Slack
        slack = max(0, hi - lo)

        # 3. Major / comp. split
        major_first = 0 if course_bank[course].course_type == MAJOR else 1

        # 4. Age
        age = max(0, term - ready_since.get(course, term) - 1)

        return (hi, slack, major_first, -age, course)

    # Initialize ready queue
    def handle_course_queue(placed_now: List[str]) -> Deque[str]:
        ready_course_list = []

        # Update in-degree for courses whose prereqs have been placed
        for c in placed_now:
            for child_course in course_graph.children[c]:
                in_degree[child_course] = max(0, in_degree[child_course] - 1)

        # Add courses that are ready to be scheduled
        for course in course_graph.all_courses:
            if course not in scheduled and in_degree[course] == 0 and _in_window(course, term):
                if course not in ready_since:
                    ready_since[course] = term
                ready_course_list.append(course) 

        return deque(sorted(ready_course_list, key=lambda c: _priority(c)))
    
    ready = handle_course_queue(placed_now=[])

    # Begin scheduling
    while (scheduled != course_graph.all_courses) and term < max_terms:
        courses_this_term = [] # clear out previous version of term
        slots = max_courses_per_term - len(courses_this_term)
        placed_now: List[str] = []

        if verbose:
            print(f"--\nTerm={term} | Cap.={slots} | Ready={ready} | Ready since={ready_since}")

        # Layer A — Feasibility first: due-now = hi == term
        due_now = [c for c in ready if course_scheduling_windows.get(c, (window_start_term, max_terms))[1] == term]

        if verbose:
            print(f"Due now: {due_now}")

        # Place all due-now first
        if len(due_now) > 0:
            # deterministic order within due-now: major first, then code
            due_now.sort(key=lambda c: (0 if (c in course_bank and course_bank[c].course_type == MAJOR) else 1, c))
            if len(due_now) > slots:
                # hard infeasibility
                raise ValueError(f"Infeasible at term {term}: {len(due_now)} courses due now but only {slots} slots. Due: {due_now}")
            for c in due_now:
                courses_this_term.append(c)
                placed_now.append(c)
                scheduled.add(c)    
                ready_since.pop(c)

                if c in course_bank:
                    course_bank[c].scheduled = True
                    course_bank[c].term_idx = term

            slots = max_courses_per_term - len(courses_this_term)

        # Layer B — Fill remaining by priority (EDF/min-slack), enforcing ≤2 majors/term
        if verbose:
            print(f"Layer B: {slots} slots remaining")

        if slots > 0:
            pool = [c for c in ready if c not in due_now]
            pool.sort(key=_priority)

            for c in pool:
                majors_used = sum(1 for c in courses_this_term if (c in course_bank and course_bank[c].course_type == MAJOR))

                if slots == 0:
                    break

                is_major = (c in course_bank and course_bank[c].course_type == MAJOR)
                # policy: ≤2 majors/term (soft—feasibility already handled in Layer A)
                if is_major and majors_used >= 2:
                    continue
                # place
                courses_this_term.append(c)
                placed_now.append(c)
                scheduled.add(c)
                ready_since.pop(c)

                if c in course_bank:
                    course_bank[c].scheduled = True
                    course_bank[c].term_idx = term
                slots -= 1

        # Update plan
        plan[term] = courses_this_term

        if verbose:
            print(f"Placed: {courses_this_term}")

        # Increment term and update ready queue
        term += 1
        ready = handle_course_queue(placed_now=placed_now)

    unscheduled = course_graph.all_courses - scheduled
    if unscheduled:
        print(f"Warning: Unscheduled courses: {unscheduled}")

        for c in unscheduled: 
            course_bank[c].scheduled = False
            course_bank[c].term_idx = None

    return {"plan": plan, "scheduled": scheduled, "unscheduled": unscheduled}

def rebuild_v1(cp, window_start_term: Optional[int] = None, must_have_course_map: Dict[str, Course] = {}, max_terms: int = 12, for_op: bool = False, verbose: bool = False) -> Dict[str, Any]:
    if window_start_term is None:
        window_start_term = cp.curr_window_start

    # 1. Combine existing must-have courses with new must-have courses
    existing_must_have_courses_map = {c: cp.course_bank[c] for c in cp.must_have_courses}
    complete_must_have_courses_map = existing_must_have_courses_map | must_have_course_map

    print(complete_must_have_courses_map)

    # Get external courses
    external_courses = set([course for term in cp.course_path[:window_start_term] for course in term])

    # 2. Compute feasibility windows for must-have courses
    must_have_course_bank = {}

    for c, c_object in complete_must_have_courses_map.items():

        # Construct course object for bank
        must_have_course_bank[c] = must_have_course_bank.get(c, c_object)
        c_prereq_tree, c_prereq_set = build_prereq_tree(c)
        must_have_course_bank[c].prereq_tree = c_prereq_tree
        must_have_course_bank[c].must_have_window = c_object.must_have_window

        for c_prereq in c_prereq_set:
            must_have_course_bank[c_prereq] = must_have_course_bank.get(c_prereq, Course(course_code=c_prereq, course_type=must_have_course_bank[c].course_type))
            must_have_course_bank[c_prereq].is_prereq = True

            ## To maintain schedulign accuracy for pre-window courses upon merging must-have and prior course banks
            if c_prereq in cp.course_bank:
                must_have_course_bank[c_prereq].scheduled = cp.course_bank[c_prereq].scheduled
                must_have_course_bank[c_prereq].term_idx = cp.course_bank[c_prereq].term_idx

    print(must_have_course_bank)

    must_have_graph = rebuild_prereq_graph(course_bank=must_have_course_bank, courses=must_have_course_map.keys(), to_prune=external_courses)
    print(must_have_graph.children)

    # 4. Compute ASAP and ALAP, build scheduling windows
    must_have_topo_order = _topo_order(must_have_graph.children, must_have_graph.parents, must_have_graph.all_courses)
    asap_for_courses = compute_asap_for_graph(must_have_graph, window_start_term, topo_order=must_have_topo_order)
    target_deadline_hi = {c: obj.must_have_window[1] for c, obj in complete_must_have_courses_map.items()}
    alap_for_courses = compute_alap_for_graph(must_have_graph, target_deadline_hi, default_hi=max_terms - 1, topo_order=must_have_topo_order)
    scheduling_windows = build_scheduling_windows(must_have_graph, asap_for_courses, alap_for_courses, window_start_term, max_terms, must_have_course_map)
 
    # 5. Rebuild master course graph
    complete_course_bank = cp.course_bank | must_have_course_bank
    build_for = must_have_course_map.keys() | cp.recommended_courses
    master_graph = rebuild_prereq_graph(course_bank=complete_course_bank, courses=build_for, to_prune=external_courses)

    # 6. Schedule courses by term
    course_path_components = schedule_courses_by_term(course_graph=master_graph, 
                                                      course_bank=complete_course_bank, 
                                                      existing_plan=cp.course_path, 
                                                      course_scheduling_windows=scheduling_windows, 
                                                      window_start_term=window_start_term, 
                                                      max_terms=max_terms, 
                                                      verbose=verbose)

    
    # 7. Consolidate into CoursePath object

    from dreampath_processing.courses.schedule_modules.course_path import CoursePath
    new_cp = CoursePath(course_path=course_path_components["plan"],
                        recommended_courses=set(),
                        course_bank={},
                        prereq_graph=master_graph,
                        curr_window_start=window_start_term,
                        must_have_courses=set(),
                        lingering_courses=set()
                        )
    
    violations = CoursePath._validate_plan(course_path=course_path_components["plan"], course_bank=complete_course_bank)
    if violations:
        print(f"Violations: {violations}")

    return new_cp

if __name__ == "__main__":
    major = 'Computer Science'
    major_courses = {'COSC89.27', 'COSC55', 'COSC89.20', 'COSC35', 'COSC89.28', 'COSC62', 'COSC69.17', 'COSC89.19', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
    complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'COGS44', 'COGS26'}
    
    # Construct recommended courses set and course bank
    recommended_courses = major_courses | complementary_courses
    course_bank = {c: Course(course_code=c, course_type=MAJOR if c in major_courses else COMPLEMENTARY) for c in recommended_courses}

    # Build initial course path + course bank updated with prereqs + scheduling info
    from dreampath_processing.courses.build_major_course_path import build_course_path

    test_course_path = build_course_path(recommended_courses, course_bank)
    test_course_path.curr_window_start = 6

    print(test_course_path.visualize())

    must_have_course_map = {'MATH40': Course(course_code='MATH40', course_type=COMPLEMENTARY, must_have_window=(8, 9)),
                            'MATH46': Course(course_code='MATH46', course_type=COMPLEMENTARY, must_have_window=(8, 10)),
                            'CHEM40': Course(course_code='CHEM40', course_type=COMPLEMENTARY, must_have_window=(8, 10))}

    new_cp = test_course_path.rebuild(must_have_course_map=must_have_course_map, verbose=3)
    print(new_cp.visualize())
    print(new_cp.visualize_by_term_idx())

    from dreampath_processing.courses.schedule_modules.course_path import CoursePath

    violations = CoursePath._validate_plan(course_path=new_cp.course_path, course_bank=new_cp.course_bank)
    if violations:
        print(f"Violations: {violations}")

    # print(new_cp.course_bank)
    print(new_cp.must_have_courses)
    print(new_cp.recommended_courses)
    print([new_cp.course_bank[c] for c in new_cp.must_have_courses])

    new_cp.add_course(course_to_add=Course(course_code='COSC58', course_type=MAJOR), reschedule=True, verbose=3)

    print(new_cp.visualize())
    print(new_cp.visualize_by_term_idx())

    violations = CoursePath._validate_plan(course_path=new_cp.course_path, course_bank=new_cp.course_bank)
    if violations:
        print(f"Violations: {violations}")

    # asap_for_courses = {}
    # alap_for_courses = {}

    # # Compute must_have graph
    # must_have_trees = []
    # external_courses = set([course for term in test_course_path.course_path[:test_course_path.curr_window_start] for course in term])

    # for course, course_object in must_have_course_map.items():
    #     course_object.prereq_tree, _ = build_prereq_tree(course)
    #     pruned_prereq_tree = prune_prereqs_from_tree(course_object.prereq_tree, external_courses)
    #     must_have_trees.append(pruned_prereq_tree)
        
    # must_have_graph = merge_prereq_trees_to_graph(must_have_trees)

    # print(must_have_graph.parents)
    # print(must_have_graph.children)

    # # Compute ASAP
    # asap_for_courses = compute_asap_for_graph(must_have_graph, test_course_path.curr_window_start)

    # # Compute ALAP
    # alap_for_courses = compute_alap_for_graph(must_have_graph, asap_for_courses, test_course_path.curr_window_start)

    # scheduling_windows = build_scheduling_windows(must_have_graph, asap_for_courses, alap_for_courses, test_course_path.curr_window_start, 12, must_have_course_map)
    # print(scheduling_windows)