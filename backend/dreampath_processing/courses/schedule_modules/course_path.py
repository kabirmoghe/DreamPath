from dataclasses import dataclass, field
from typing import List, Set, Dict, Tuple, Optional, Any
from .course import Course
from copy import deepcopy
from collections import defaultdict
from dreampath_processing.courses.course_relationship_handling import build_prereq_tree, get_direct_prereqs, rebuild_prereq_graph, find_lingering_courses, PrereqGraph, construct_course
from dreampath_processing.courses.scheduling_helpers import (_topo_order,
                                                             compute_asap_for_graph,
                                                             compute_alap_for_graph,
                                                             build_scheduling_windows,
                                                             schedule_courses_by_term)

# Exceptions
class TermCapacityError(Exception): ...
class RebuildError(Exception): ...

@dataclass
class CoursePath:
    course_path: List[List[str]]
    recommended_courses: Set[str]
    course_bank: Dict[str, Course]
    prereq_graph: PrereqGraph
    curr_window_start: int = 0
    must_have_courses: Set[str] = field(default_factory=set)
    lingering_courses: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Validate the data after initialization"""
        if not isinstance(self.course_path, list):
            raise ValueError("course_path must be a list")
        if not isinstance(self.curr_window_start, int): 
            raise ValueError("curr_window_start must be an int" )
        if not isinstance(self.recommended_courses, set):
            raise ValueError("recommended_courses must be a set")
        if not isinstance(self.course_bank, dict):
            raise ValueError("course_bank must be a dict")
        if not isinstance(self.prereq_graph, PrereqGraph):
            raise ValueError("prereq_graph must be a dict")
        if not isinstance(self.must_have_courses, set):
            raise ValueError("must_have_courses must be a set")
        
    def visualize(self, course_path=None):
        """Print the course path in a pretty format"""
        # Normalize to strings and handle None
        cols = [[str(x) for x in term if x is not None] for term in course_path or self.course_path]

        # Column widths = longest course in each term, but at least as wide as "(n)"
        widths = []
        for i, col in enumerate(cols, start=1):
            max_course = max((len(c) for c in col), default=0)
            widths.append(max(max_course, len(f"({i})")))

        # Number of rows = longest column length
        max_rows = max((len(c) for c in cols), default=0)

        # Build header
        lines = []
        pad = 2
        if widths:
            header = (" " * pad).join(f"({i})".center(widths[i]) for i in range(len(cols)))
            sep = (" " * pad).join("-" * w for w in widths)
            lines.append(header)
            lines.append(sep)

        # Build body rows
        for r in range(max_rows):
            cells = []
            for c, w in zip(cols, widths):
                val = c[r] if r < len(c) else ""
                cells.append(val.ljust(w))
            lines.append((" " * pad).join(cells))

        return "\n".join(lines)
    
    def _produce_mock_course_path(self):
        """Produce a mock course path using the course_bank"""
        mock_course_path = [[] for _ in range(len(self.course_path))]
        for course_code, course_obj in self.course_bank.items():
            if course_obj.term_idx is not None and course_obj.scheduled:
                mock_course_path[course_obj.term_idx].append(course_code)
        return mock_course_path

    def visualize_by_term_idx(self, calculate_diff=True):
        """Print the course path in a pretty format by term index"""
        # Construct mock course path using course_bank
        mock_course_path = self._produce_mock_course_path()

        if calculate_diff:
            diff = {}

            for term_idx, term in enumerate(self.course_path):
                in_mock = set(mock_course_path[term_idx]) - set(term)
                in_self = set(term) - set(mock_course_path[term_idx])

                if in_mock:
                    diff["removed"] = diff.get("removed", []) + [{"course_code": list(in_mock), "term_idx": term_idx}]
                if in_self:
                    diff["added"] = diff.get("added", []) + [{"course_code": list(in_self), "term_idx": term_idx}]

            print(f"Diff: {diff}")

        return self.visualize(mock_course_path)
        
    def __str__(self):
        cp_str = ""
        for term_idx, term in enumerate(self.course_path):
            cp_str += f"#### Term {term_idx} Courses{' [**Current Term**]' if term_idx == self.curr_window_start else ''}:\n"
            
            # Add actual courses
            for course in term:
                course_obj = self.course_bank[course]
                cp_str += f"{course_obj.course_code}: '{course_obj.course_title.strip() if course_obj.course_title is not None else ''}' |"

                if course_obj.is_prereq:
                    cp_str += f" Prereq.\n"
                else:
                    cp_str += f" {course_obj.course_type} Course\n"
            
            # Add empty slots if term has fewer than 3 courses
            for _ in range(len(term), 3):
                cp_str += "*Empty*\n"

            cp_str += "\n"
        return cp_str

    # ─────────────────────────────────────────────────────────────────────────────
    # VALIDATE COURSE PLAN
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _validate_plan(course_path: List[List[str]], course_bank: Dict[str, Course], verbose: bool=False) -> List[Dict]:
        """
        Validate a course plan by checking for duplicates and prerequisite violations

        Args:
            course_plan (list): List of lists, where each inner list represents a term and contains course codes

        Returns:
            List[Dict]: List of violations
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
        #    Note: if duplicate, this will pick the last occurrence, but that doesn't block us
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

    @staticmethod
    def _format_violations(violations: list[dict[str, Any]]) -> str:
        return "\n".join([f"- {violation}" for violation in violations])
    
    # ─────────────────────────────────────────────────────────────────────────────
    # REBUILD COURSE PATH
    # ─────────────────────────────────────────────────────────────────────────────
    def rebuild(self, window_start_term: Optional[int] = None, must_have_course_map: Dict[str, Course] = {}, max_terms: int = 12, for_op: bool = False, verbose: int = 2):
        if window_start_term is None:
            window_start_term = self.curr_window_start

        # 1. Combine existing must-have courses with new must-have courses
        existing_must_have_courses_map = {c: self.course_bank[c] for c in self.must_have_courses}
        complete_must_have_courses_map = existing_must_have_courses_map | must_have_course_map

        if verbose >= 1:
            print("Complete must-have courses map:")
            for c, obj in complete_must_have_courses_map.items():
                print(f"{c}: {obj.must_have_window}")

        # Get external courses
        external_courses = set([course for term in self.course_path[:window_start_term] for course in term])

        # 2. Compute feasibility windows for must-have courses
        must_have_course_bank = {}
        scheduling_windows = {}

        for c, c_object in complete_must_have_courses_map.items():

            # Construct course object for bank
            must_have_course_bank[c] = must_have_course_bank.get(c, c_object)
            c_prereq_tree, c_prereq_set = build_prereq_tree(c)
            must_have_course_bank[c].prereq_tree = c_prereq_tree
            must_have_course_bank[c].must_have_window = c_object.must_have_window

            for c_prereq in c_prereq_set:
                must_have_course_bank[c_prereq] = must_have_course_bank.get(c_prereq, construct_course(course_code=c_prereq, hardcoded_type=must_have_course_bank[c].course_type))
                must_have_course_bank[c_prereq].is_prereq = True

                # To maintain scheduling accuracy for pre-window courses upon merging must-have and prior course banks
                if c_prereq in self.course_bank:
                    must_have_course_bank[c_prereq].scheduled = self.course_bank[c_prereq].scheduled
                    must_have_course_bank[c_prereq].term_idx = self.course_bank[c_prereq].term_idx

        # If there are must-have courses, compute ASAP and ALAP, build scheduling windows
        if must_have_course_bank: 
            print(f"Building prereq. graph for must-have courses...")
            must_have_graph = rebuild_prereq_graph(course_bank=must_have_course_bank, courses=complete_must_have_courses_map.keys(), to_prune=external_courses)

            print(f"Computing ASAP and ALAP for must-have courses...")
            # 4. Compute ASAP and ALAP, build scheduling windows
            must_have_topo_order = _topo_order(must_have_graph.children, must_have_graph.parents, must_have_graph.all_courses)
            asap_for_courses = compute_asap_for_graph(must_have_graph, window_start_term, topo_order=must_have_topo_order)
            target_deadline_hi = {c: obj.must_have_window[1] for c, obj in complete_must_have_courses_map.items()}
            alap_for_courses = compute_alap_for_graph(must_have_graph, target_deadline_hi, default_hi=max_terms - 1, topo_order=must_have_topo_order)
            scheduling_windows = build_scheduling_windows(must_have_graph, asap_for_courses, alap_for_courses, window_start_term, max_terms, must_have_course_bank)
        
        if verbose >= 1:
            print(f"Scheduling windows: {scheduling_windows}")

        # 5. Rebuild master course graph
        complete_course_bank = self.course_bank | must_have_course_bank
        build_for = must_have_course_map.keys() | self.recommended_courses
        master_graph = rebuild_prereq_graph(course_bank=complete_course_bank, courses=build_for, to_prune=external_courses)

        # 6. Schedule courses by term
        course_path_components = schedule_courses_by_term(course_graph=master_graph, 
                                                        course_bank=complete_course_bank, 
                                                        existing_plan=self.course_path, 
                                                        course_scheduling_windows=scheduling_windows, 
                                                        window_start_term=window_start_term, 
                                                        max_terms=max_terms, 
                                                        verbose=verbose >= 1)

        if for_op and len(course_path_components["unscheduled"] & must_have_course_map.keys()) > 0:
            raise RebuildError("Rebuild failed for operation, could not prioritize must-have operation course(s).")
        
        # 7. Consolidate into CoursePath object
        self.course_path = course_path_components["plan"]
        self.recommended_courses = self.recommended_courses | must_have_course_map.keys()
        self.course_bank = complete_course_bank
        self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
        self.must_have_courses = set(complete_must_have_courses_map.keys())

        # Handle lingering courses
        if self.lingering_courses:
            print(f"* Warning: lingering courses={self.lingering_courses}")

        self.lingering_courses = set()
        
        return self

    # ─────────────────────────────────────────────────────────────────────────────
    # REMOVE COURSE
    # ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_remove_course(course_path: List[List[str]], course_to_remove: Course) -> List[List[str]]:
        """
        Attempt to remove course from course path

        Args:
            course_path (List[List[str]]): Course path to remove course from
            course_to_remove (Course): Course to remove from course path

        Returns:
            List[List[str]]: Course path list with course removed
        """
        
        remove_course_path = deepcopy(course_path)
        remove_course_path[course_to_remove.term_idx].remove(course_to_remove.course_code) 

        return remove_course_path

    def remove_course(self, course_code_to_remove: str, reschedule: bool=False, verbose: bool=False):
        """
        Remove courses from a course path

        Args:
            course_path_obj (CoursePath): Course path to remove courses from
            courses_to_remove (set): Set of course codes to remove from the course path

        Returns:
            CoursePath: Course path object with course removed
        """
        course_to_remove = self.course_bank.get(course_code_to_remove, None)
        if course_to_remove is None:
            raise Exception(f"Course code '{course_code_to_remove}' does not exist in course bank.")

        if course_to_remove.term_idx is None:
            raise Exception(f"Course '{course_to_remove.course_code}' not scheduled / missing term index.")

        if course_to_remove.term_idx < 0 or course_to_remove.term_idx >= len(self.course_path):
            raise Exception(f"Term index must be in range [0, {len(self.course_path) - 1}]")

        if course_to_remove.term_idx < self.curr_window_start:
            raise Exception(f"Term index {course_to_remove.term_idx} for removal must be within current window.")

        # Attempt to remove course and check for validity
        try:
            remove_course_path = self._attempt_remove_course(course_path=self.course_path, course_to_remove=course_to_remove)
            removal_violations = self._validate_plan(course_path=remove_course_path, course_bank=self.course_bank)

        except Exception as e:
            raise Exception(f"Error attempting to remove course {course_code_to_remove}: {e}")

        # If removal violates prereq. graph, check if course is recommended and remove from recommended courses; if prereq., raise error
        if removal_violations:
            if verbose:
                print(f"* Violations for REMOVE course '{course_code_to_remove}' in term {course_to_remove.term_idx}:\n{removal_violations}")
            
            if course_code_to_remove not in self.recommended_courses or self.course_bank[course_code_to_remove].is_prereq:
                raise Exception(f"\n* Course '{course_code_to_remove}' is a pre-requisite for a recommended course, cannot be removed.")
            
            # Reschedule if requested
            elif reschedule:
                if verbose:
                    print(f"\n* Course '{course_code_to_remove}' is a recommended course, removing from recommended courses and rescheduling...")

                course_to_remove.scheduled = False
                course_to_remove.term_idx = None
                course_to_remove.must_have_window = None

                self.recommended_courses = self.recommended_courses - {course_code_to_remove}
                self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
                self.must_have_courses = self.must_have_courses - {course_code_to_remove}

                # Rebuild course path with must-have courses
                self.rebuild(window_start_term=self.curr_window_start, for_op=True)
            else:
                # Add violations to error message line by line
                error_msg = f"Cannot remove course '{course_code_to_remove}' due to scheduling violations, requires rescheduling. Violations:"
                error_msg += self._format_violations(removal_violations)
                raise Exception(error_msg)

        # Simple removal successful, update course info
        else:
            course_to_remove.scheduled = False
            course_to_remove.term_idx = None
            course_to_remove.must_have_window = None
            
            self.course_path = remove_course_path
            self.recommended_courses = self.recommended_courses - {course_code_to_remove}
            self.must_have_courses = self.must_have_courses - {course_code_to_remove}

            # Update prereq. graph & handle lingering courses
            remove_prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
            new_lingering_courses = find_lingering_courses(old_prereq_graph=self.prereq_graph, new_prereq_graph=remove_prereq_graph)
            new_lingering_courses.discard(course_code_to_remove)
            
            self.prereq_graph = remove_prereq_graph
            self.lingering_courses = self.lingering_courses | new_lingering_courses

        if verbose:
            print(f"* Course '{course_code_to_remove}' removed successfully.")

        return self
    
    # ─────────────────────────────────────────────────────────────────────────────
    # ADD COURSE
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_add_course(course_path: List[List[str]], course_code_to_add: str, must_have_window: Optional[List[int]]=None, window_start_term: int=0, max_classes_per_term=3) -> Tuple[List[List[str]], int]:
        add_course_path = deepcopy(course_path)

        # Check if must_have term location / window specified
        if must_have_window is not None:
            # Assumes valid window
            course_start_term, course_end_term = must_have_window[0], must_have_window[1]
            adjusted_start_term = max(window_start_term, course_start_term)

            for term_idx in range(adjusted_start_term, course_end_term + 1):
                if len(add_course_path[term_idx]) < max_classes_per_term:
                    add_course_path[term_idx].append(course_code_to_add)

                    return add_course_path, term_idx
                
            raise TermCapacityError(f"Course '{course_code_to_add}' cannot be directly added in scheduling window {must_have_window}.")
        else:
            for term_idx in range(window_start_term, len(add_course_path)):
                if len(add_course_path[term_idx]) < max_classes_per_term:
                    add_course_path[term_idx].append(course_code_to_add)
                    return add_course_path, term_idx
                
            raise TermCapacityError(f"Course '{course_code_to_add}' cannot be directly added to any term in current window.")

    def add_course(self, course_to_add: Course, max_classes_per_term: int=3, reschedule: bool=False, verbose: bool=False):
        # Check if must_have term location / window specified 
        if course_to_add.must_have_window:
            max_terms = len(self.course_path)

            # Validate scheduling window pointers
            course_start_term, course_end_term = course_to_add.must_have_window[0], course_to_add.must_have_window[1]
        
            if (course_start_term > course_end_term) or (course_start_term < 0) or (course_end_term >= max_terms):
                raise Exception(f"Invalid scheduling window {course_to_add.must_have_window} for course {course_to_add.course_code}.")
            
            if course_end_term < self.curr_window_start:
                raise Exception(f"Cannot add course '{course_to_add.course_code}', requested scheduling window {course_to_add.must_have_window} outside of current window.")
        else:
            course_to_add.must_have_window = [self.curr_window_start, len(self.course_path) - 1]

        # Checking if course is already scheduled
        existing_course = self.course_bank.get(course_to_add.course_code, None)
        if existing_course and existing_course.term_idx is not None:
            raise Exception(f"Course '{course_to_add.course_code}' is already scheduled (scheduled={existing_course.scheduled}).")
        
        # Proceed with addition
        try:
            add_course_path, new_course_term_idx = self._attempt_add_course(course_path=self.course_path, course_code_to_add=course_to_add.course_code, must_have_window=course_to_add.must_have_window, window_start_term=self.curr_window_start, max_classes_per_term=max_classes_per_term)
            add_violations = self._validate_plan(course_path=add_course_path, course_bank=self.course_bank)
        except TermCapacityError as e:
            # Reschedule if requested
            add_violations = [{"course": course_to_add.course_code, "issue": str(e)}]
            
        # If violations, make must-have and schedule around
        if add_violations:
            if verbose:
                print(f"* Violations for ADD course '{course_to_add.course_code}':\n{add_violations}")

            # Reschedule if requested
            if reschedule:
                add_as_must_have = {course_to_add.course_code: course_to_add}
                self.rebuild(window_start_term=self.curr_window_start, must_have_course_map=add_as_must_have, for_op=True)
            else:
                error_msg = f"Cannot add course '{course_to_add.course_code}' due to scheduling violations, requires rescheduling. Violations:\n"
                error_msg += self._format_violations(add_violations)
                raise Exception(error_msg)
            
        # Simple addition successful, update course info
        else: 
            course_to_add.scheduled = True
            course_to_add.term_idx = new_course_term_idx

            self.course_path = add_course_path
            self.recommended_courses = self.recommended_courses | {course_to_add.course_code}
            self.course_bank = self.course_bank | {course_to_add.course_code: course_to_add}
            self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
            self.must_have_courses = self.must_have_courses | {course_to_add.course_code}

        if verbose:
            print(f"* Course '{course_to_add.course_code}' added successfully.")
        return self
        
    # ─────────────────────────────────────────────────────────────────────────────
    # MOVE COURSE
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_move_course(course_path: List[List[str]], course_to_move: Course, move_window: List[int], window_start_term: int=0, max_classes_per_term: int=3) -> Tuple[List[List[str]], int]:
        # First, remove course from original term
        remove_course_path = CoursePath._attempt_remove_course(course_path=course_path, course_to_remove=course_to_move)
        
        # Then, move course to new term
        move_course_path = deepcopy(remove_course_path)
        move_start_term, move_end_term = move_window[0], move_window[1]
        adjusted_start_term = max(window_start_term, move_start_term)

        for term_idx in range(adjusted_start_term, move_end_term + 1):
            if len(move_course_path[term_idx]) < max_classes_per_term:
                move_course_path[term_idx].append(course_to_move.course_code)
                return move_course_path, term_idx
            
        raise TermCapacityError(f"Course '{course_to_move.course_code}' cannot be moved due to max capacity in scheduling window {move_window}.")
        
    def move_course(self, course_code_to_move: str, move_window: List[int], max_classes_per_term: int=3, reschedule: bool=False, verbose: bool=False):
        # Validate course to move
        course_to_move = self.course_bank.get(course_code_to_move, None)
        if course_to_move is None:
            raise Exception(f"Course code '{course_code_to_move}' does not exist in course bank.")

        if course_to_move.term_idx is None:
            raise Exception(f"Cannot move unscheduled course '{course_code_to_move}'.")

        # Validate move window
        move_start_term, move_end_term = move_window[0], move_window[1]
        if move_start_term > move_end_term or move_start_term < 0 or move_end_term >= len(self.course_path):
            raise Exception(f"Invalid move window {move_window} for course {course_code_to_move}.")

        if move_end_term < self.curr_window_start:
            raise Exception(f"Cannot move course '{course_code_to_move}', requested scheduling window {move_window} outside of current window.")
        
        if move_start_term <= course_to_move.term_idx <= move_end_term:
            raise Exception(f"Course '{course_code_to_move}' is already in move window {move_window}.")
        
        if course_to_move.term_idx < self.curr_window_start:
            raise Exception(f"Term index {course_to_move.term_idx} for move must be within current window.")
        
        # Proceed with move
        try:
            move_course_path, move_term_idx = self._attempt_move_course(course_path=self.course_path, course_to_move=course_to_move, move_window=move_window, window_start_term=self.curr_window_start, max_classes_per_term=max_classes_per_term)
            move_violations = self._validate_plan(course_path=move_course_path, course_bank=self.course_bank)
        except TermCapacityError as e:
            move_violations = [{"course": course_to_move.course_code, "issue": str(e)}]

        # If violations, make must-have and schedule around
        if move_violations:
            if verbose:
                print(f"* Violations for MOVE course '{course_code_to_move}' in window {move_window}:\n{move_violations}")

            # Reschedule if requested
            if reschedule:
                course_to_move.must_have_window = move_window

                if course_to_move.course_code not in self.must_have_courses:
                    self.must_have_courses = self.must_have_courses | {course_to_move.course_code}

                # Override must-have course map to treat course as new
                self.rebuild(must_have_course_map={course_to_move.course_code: course_to_move}, window_start_term=self.curr_window_start, for_op=True)
            else:
                error_msg = f"Cannot move course '{course_code_to_move}' due to scheduling violations, requires rescheduling. Violations:"
                error_msg += self._format_violations(move_violations)
                raise Exception(error_msg)

        # Simple move successful, update course info
        else:
            course_to_move.term_idx = move_term_idx
            course_to_move.must_have_window = move_window

            self.course_path = move_course_path
            self.must_have_courses = self.must_have_courses | {course_to_move.course_code}

        if verbose:
            print(f"* Course '{course_code_to_move}' moved successfully.")
        return self
    
    # ─────────────────────────────────────────────────────────────────────────────
    # REPLACE COURSE
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_replace_course(course_path: List[List[str]], new_course: Course, old_course: Course, window_start_term: int=0) -> Tuple[List[List[str]], int]:
        # First, remove old course
        remove_course_path = CoursePath._attempt_remove_course(course_path=course_path, course_to_remove=old_course)

        # Then, add new course
        if old_course.must_have_window:
            new_course.must_have_window = old_course.must_have_window
        else:
            new_course.must_have_window = [old_course.term_idx, old_course.term_idx]

        # Reframe ADD error as REPLACE error
        try:
            add_course_path, new_course_term_idx = CoursePath._attempt_add_course(course_path=remove_course_path, course_code_to_add=new_course.course_code, must_have_window=new_course.must_have_window, window_start_term=window_start_term, max_classes_per_term=3)

        except Exception as e:
            raise Exception(f"Error attempting to replace course '{old_course.course_code}' with '{new_course.course_code}': {e}")

        return add_course_path, new_course_term_idx

    def replace_course(self, new_course: Course, old_course_code: str, reschedule: bool=False, verbose: bool=False):
        # Validate course to replace
        old_course = self.course_bank.get(old_course_code, None)
        if old_course is None:
            raise Exception(f"Course code '{old_course_code}' does not exist in course bank.")
        
        if old_course.term_idx is None:
            raise Exception(f"Course '{old_course_code}' not scheduled / missing term index.")
        
        if old_course.term_idx < self.curr_window_start:
            raise Exception(f"Cannot replace course '{old_course_code}', outside of current window.")

        # Validate new course
        if new_course.course_code in self.course_bank and self.course_bank[new_course.course_code].term_idx is not None:
            raise Exception(f"Course '{new_course.course_code}' is already scheduled (scheduled={self.course_bank[new_course.course_code].scheduled})")
        
        if new_course.must_have_window:
            if new_course.must_have_window[1] < self.curr_window_start:
                raise Exception(f"Cannot replace course '{old_course_code}' with '{new_course.course_code}', requested scheduling window {new_course.must_have_window} outside of current window.")
            
            if new_course.must_have_window[0] > new_course.must_have_window[1] or new_course.must_have_window[0] < 0 or new_course.must_have_window[1] >= len(self.course_path):
                raise Exception(f"Cannot replace course '{old_course_code}' with '{new_course.course_code}', requested scheduling window {new_course.must_have_window} is invalid.")
            
            if verbose:
                print(f"Warning: replacing course '{old_course_code}' with course '{new_course.course_code}' may override existing must-have window.")

        # Attempt to replace course
        replace_course_path, replace_term_idx = self._attempt_replace_course(course_path=self.course_path, new_course=new_course, old_course=old_course, window_start_term=self.curr_window_start)
        replacement_violations = self._validate_plan(course_path=replace_course_path, course_bank=self.course_bank)

        # If violations, make must-have and schedule around
        if replacement_violations:
            if verbose:
                print(f"* Replacement violations for course '{old_course_code}' in term {replace_term_idx}: {replacement_violations}")

            if old_course_code not in self.recommended_courses or self.course_bank[old_course_code].is_prereq:
                raise Exception(f"Course '{old_course_code}' is a pre-requisite for a recommended course, cannot be replaced.")
            
            # Reschedule if requested
            elif reschedule:
                if verbose:
                    print(f"* Course '{old_course_code}' is a recommended course, replacing with '{new_course.course_code}' and rescheduling...")
                
                old_course.scheduled = False
                old_course.term_idx = None
                old_course.must_have_window = None

                self.recommended_courses = self.recommended_courses - {old_course_code}
                self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
                self.must_have_courses = self.must_have_courses - {old_course_code}

                # Rebuild course path with must-have courses
                self.rebuild(window_start_term=self.curr_window_start, must_have_course_map={new_course.course_code: new_course}, for_op=True)
            else:
                error_msg = f"Cannot replace course '{old_course_code}' with '{new_course.course_code}' due to scheduling violations, requires rescheduling. Violations:"
                error_msg += self._format_violations(replacement_violations)
                raise Exception(error_msg)

        # Simple replacement successful, update course info
        else:
            new_course.scheduled = True
            new_course.term_idx = replace_term_idx
            new_course.must_have_window = old_course.must_have_window

            old_course.scheduled = False
            old_course.term_idx = None
            old_course.must_have_window = None

            if old_course_code in self.recommended_courses:
                self.recommended_courses = self.recommended_courses - {old_course_code} | {new_course.course_code}

            self.course_bank = self.course_bank | {new_course.course_code: new_course}
            
            # Update prereq. graph & handle lingering courses
            replace_prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
            new_lingering_courses = find_lingering_courses(old_prereq_graph=self.prereq_graph, new_prereq_graph=replace_prereq_graph) 
            new_lingering_courses.discard(old_course_code)
            self.prereq_graph = replace_prereq_graph
            self.lingering_courses = self.lingering_courses | new_lingering_courses

            if old_course_code in self.must_have_courses:
                self.must_have_courses = self.must_have_courses - {old_course_code} | {new_course.course_code}

            self.course_path = replace_course_path

        if verbose:
            print(f"* Course '{old_course_code}' replaced with '{new_course.course_code}' successfully.")
        return self

    # ─────────────────────────────────────────────────────────────────────────────
    # SWAP COURSES
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_swap_courses(course_path: List[List[str]], course_to_swap_1: Course, course_to_swap_2: Course) -> Tuple[List[List[str]], int, int]:
        # First, remove course 1 and move course 2 to course 1's term
        remove_course_path = CoursePath._attempt_remove_course(course_path=course_path, course_to_remove=course_to_swap_1)
        course_2_move_window = [course_to_swap_1.term_idx, course_to_swap_1.term_idx]
        move_course_path, course_2_new_term_idx = CoursePath._attempt_move_course(course_path=remove_course_path, course_to_move=course_to_swap_2, move_window=course_2_move_window, max_classes_per_term=3)

        # Then, add course 1 to course 2's term
        course_1_add_window = [course_to_swap_2.term_idx, course_to_swap_2.term_idx]
        add_course_path, course_1_new_term_idx = CoursePath._attempt_add_course(course_path=move_course_path, course_code_to_add=course_to_swap_1.course_code, must_have_window=course_1_add_window, max_classes_per_term=3)

        return add_course_path, course_1_new_term_idx, course_2_new_term_idx

    def swap_courses(self, course_code_1: str, course_code_2: str, verbose: bool=False):
        # Validate courses to swap
        course_1 = self.course_bank.get(course_code_1, None)
        if course_1 is None:
            raise Exception(f"Course code '{course_code_1}' does not exist in course bank.")
        
        course_2 = self.course_bank.get(course_code_2, None)
        if course_2 is None:
            raise Exception(f"Course code '{course_code_2}' does not exist in course bank.")

        # Validate term indices
        if course_1.term_idx is None:
            raise Exception(f"Course '{course_code_1}' not scheduled / missing term index.")
        
        if course_2.term_idx is None:
            raise Exception(f"Course '{course_code_2}' not scheduled / missing term index.")
        
        if course_1.term_idx == course_2.term_idx:
            raise Exception(f"Cannot swap courses '{course_code_1}' and '{course_code_2}' in the same term.")
        
        if course_1.term_idx < self.curr_window_start:
            raise Exception(f"Cannot swap courses, course '{course_code_1}' is outside of current window.")

        if course_2.term_idx < self.curr_window_start:
            raise Exception(f"Cannot swap courses, course '{course_code_2}' is outside of current window.")
        
        # Validate indices in case of windows
        if course_1.must_have_window and (course_1.must_have_window[0] > course_2.term_idx or course_1.must_have_window[1] < course_2.term_idx):
            raise Exception(f"Cannot swap courses '{course_code_1}' and '{course_code_2}'; term {course_2.term_idx} is outside of course '{course_code_1}' must-have window.")

        if course_2.must_have_window and (course_2.must_have_window[0] > course_1.term_idx or course_2.must_have_window[1] < course_1.term_idx):
            raise Exception(f"Cannot swap courses '{course_code_1}' and '{course_code_2}'; term {course_1.term_idx} is outside of course '{course_code_2}' must-have window.")

        # Attempt to swap courses
        swap_course_path, course_1_new_term_idx, course_2_new_term_idx = CoursePath._attempt_swap_courses(course_path=self.course_path, course_to_swap_1=course_1, course_to_swap_2=course_2)
        swap_violations = self._validate_plan(course_path=swap_course_path, course_bank=self.course_bank)

        # If violations, cannot swap directly
        if swap_violations:
            if verbose:
                print(f"* Swap violations for courses '{course_code_1}' and '{course_code_2}': {swap_violations}")
            error_msg = f"Cannot swap courses '{course_code_1}' [term={course_1.term_idx} -> {course_1_new_term_idx}] and '{course_code_2}' [term={course_2.term_idx} -> {course_2_new_term_idx}] due to scheduling violations. Violations:"
            error_msg += self._format_violations(swap_violations)
            raise Exception(error_msg)
        
        # Simple swap successful, update course info
        course_1.term_idx = course_1_new_term_idx
        course_2.term_idx = course_2_new_term_idx

        self.course_path = swap_course_path

        if verbose:
            print(f"* Courses '{course_code_1}' and '{course_code_2}' swapped successfully.")
        return self