from dreampath_processing.courses.course_relationship_handling import build_prereq_tree, get_direct_prereqs, PrereqGraph
from collections import defaultdict, deque
from typing import List, Set, Dict, Any, Tuple, Deque
import copy
from dreampath_processing.courses.schedule_modules.course import Course, MAJOR

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
                if verbose:
                    print(f"* Using prereq. tree for course {course} from course bank.")
                prereq_tree = course_obj.prereq_tree
            else:
                if verbose:
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

# ---------------------------------------
# Build scheduling windows using ASAP and ALAP
# ---------------------------------------
def build_scheduling_windows(prereq_graph,
                             asap: Dict[str, int],
                             alap: Dict[str, int],
                             window_start_term: int,
                             max_terms: int,
                             must_have_course_bank: Dict[str, "Course"]) -> Dict[str, List[int]]:
    """
    Clamp targets to their (lo, hi); others to full in-window horizon.
    """
    nodes = prereq_graph.all_courses
    windows: Dict[str, List[int]] = {}
    for v in nodes:
        lo = asap[v]
        hi = alap[v]
        if v in must_have_course_bank and must_have_course_bank[v].must_have_window:
            tlo, thi = must_have_course_bank[v].must_have_window[0], must_have_course_bank[v].must_have_window[1]
            lo = max(lo, tlo)
            hi = min(hi, thi)
        else:
            lo = max(lo, window_start_term)
            hi = min(hi, max_terms - 1)
        if lo > hi:
            raise ValueError(f"Infeasible window for {v}: [{lo}, {hi}]")
        windows[v] = [lo, hi]
    return windows

# ---------------------------------------
# Schedule courses by term
# ---------------------------------------
def initialize_plan(existing_plan: List[List[str]], course_bank: Dict[str, Course], window_start_term: int, max_terms: int, verbose: bool=False) -> List[List[str]]:
    plan = copy.deepcopy(existing_plan)

    # Initialize plan if DNE
    if not plan:
        plan = [[] for _ in range(max_terms)]

    # Clear all courses in window_start_term onwards to prevent lingering courses during rescheduling (in case loop terminates early)
    cleared = set()

    for term_idx in range(window_start_term, len(plan)):
        for course in plan[term_idx]:
            course_bank[course].scheduled = False
            course_bank[course].term_idx = None
            cleared.add(course)

        plan[term_idx] = []

    if verbose:
        print(f"Cleared previously scheduled courses: {cleared}")

    return plan

def schedule_courses_by_term(course_graph: PrereqGraph, 
                             course_bank: Dict[str, Course], 
                             existing_plan: List[List[str]] = None, 
                             course_scheduling_windows: Dict[str, List[int]] = {}, 
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
    plan = initialize_plan(existing_plan=existing_plan, course_bank=course_bank, window_start_term=window_start_term, max_terms=max_terms, verbose=verbose)

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
        lo, hi = course_scheduling_windows.get(course, [window_start_term, max_terms])

        # 2. Slack
        slack = max(0, hi - lo)

        # 3. Major / comp. split
        major_first = 0 if course_bank[course].course_type == MAJOR else 1

        # 4. Age
        age = max(0, term - ready_since.get(course, term) - 1)

        return (hi, slack, major_first, -age, course)

    # Initialize ready queue
    def _handle_course_queue(placed_now: List[str]) -> Deque[str]:
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
    
    ready = _handle_course_queue(placed_now=[])

    # Begin scheduling
    while (scheduled != course_graph.all_courses) and term < max_terms:
        courses_this_term = [] # clear out previous version of term
        slots = max_courses_per_term - len(courses_this_term)
        placed_now: List[str] = []

        if verbose:
            print(f"--\nTerm={term} | Cap.={slots} | Ready={ready} | Ready since={ready_since}")

        # Layer A — Feasibility first: due-now = hi == term
        due_now = [c for c in ready if course_scheduling_windows.get(c, [window_start_term, max_terms])[1] == term]

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

        skipped_major = None  # Track first major skipped due to limit (for Layer C)

        if slots > 0:
            pool = [c for c in ready if c not in due_now]
            pool.sort(key=_priority)

            for c in pool:
                majors_used = sum(1 for c in courses_this_term if (c in course_bank and course_bank[c].course_type == MAJOR))

                if slots == 0:
                    break

                # policy: ≤2 majors/term (soft—feasibility already handled in Layer A)
                is_major = (c in course_bank and course_bank[c].course_type == MAJOR)
                if is_major and majors_used >= 2:
                    if skipped_major is None:
                        skipped_major = c
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

        # Layer C — Fill remaining slot if skipped a major and no complementary was available
        if slots > 0 and skipped_major:
            if verbose:
                print(f"Layer C: Filling remaining slot with skipped major {skipped_major}")

            courses_this_term.append(skipped_major)
            placed_now.append(skipped_major)
            scheduled.add(skipped_major)
            ready_since.pop(skipped_major)

            if skipped_major in course_bank:
                course_bank[skipped_major].scheduled = True
                course_bank[skipped_major].term_idx = term
            slots -= 1

        # Update plan
        plan[term] = courses_this_term

        if verbose:
            print(f"Placed: {courses_this_term}")

        # Increment term and update ready queue
        term += 1
        ready = _handle_course_queue(placed_now=placed_now)

    unscheduled = course_graph.all_courses - scheduled
    if unscheduled:
        print(f"Warning: Unscheduled courses: {unscheduled}")

        for c in unscheduled: 
            course_bank[c].scheduled = False
            course_bank[c].term_idx = None

    return {"plan": plan, "scheduled": scheduled, "unscheduled": unscheduled}