from dataclasses import dataclass, field
from typing import List, Set, Dict, Tuple
from .course import Course
from copy import deepcopy
from collections import defaultdict
from dreampath_processing.courses.course_relationship_handling import build_prereq_tree, get_direct_prereqs, rebuild_prereq_graph
from dreampath_processing.courses.scheduling_helpers import schedule_must_have_courses, integrate_recommendations_and_must_have_courses

@dataclass
class CoursePath:
    course_path: List[List[str]]
    recommended_courses: Set[str]
    course_bank: Dict[str, Course]
    prereq_graph: Dict[str, List[str]]
    curr_window_start: int = 0
    must_have_courses: Set[str] = field(default_factory=set)
    
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
        if not isinstance(self.prereq_graph, dict):
            raise ValueError("prereq_graph must be a dict")
        if not isinstance(self.must_have_courses, set):
            raise ValueError("must_have_courses must be a set")

    # ─────────────────────────────────────────────────────────────────────────────
    # VALIDATE COURSE PLAN
    # ─────────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_plan(course_path: List[List[str]], course_bank: Dict[str, Course]):
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
    
    # ─────────────────────────────────────────────────────────────────────────────
    # REBUILD COURSE PATH
    # ─────────────────────────────────────────────────────────────────────────────

    def rebuild(self, window_start_term: int, must_have_course_map: Dict[str, Course] = {}, verbose: int = 0):
        """Rebuild a course path with must-have courses and recommendations"""
        
        # 1. Combine existing must-have courses with new must-have courses
        existing_must_have_courses_map = {c: self.course_bank[c] for c in self.must_have_courses}
        complete_must_have_courses_map = existing_must_have_courses_map | must_have_course_map

        # 2. Schedule must have courses
        must_have_schedule_output = schedule_must_have_courses(course_path=self.course_path, 
                                                            prior_course_bank=self.course_bank, 
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
                                                                                                            prior_prereq_graph=self.prereq_graph,
                                                                                                            must_have_course_bank=must_have_course_bank,
                                                                                                            prior_course_bank=self.course_bank,
                                                                                                            verbose=True if verbose >= 3 else False)
        
        # 5. Rebuild course path

        # Combine recommended courses with top-level must-have courses
        complete_recommended_courses = self.recommended_courses | set(must_have_course_map.keys())

        # Build prereq. graph for complete course bank
        complete_course_prereq_graph = rebuild_prereq_graph(course_bank=complete_course_bank)

        # Update set of must-have courses; removed because gets rid of unscheduled must-haves from object even though may want to schedule moving fwd
        complete_must_have_courses = set(complete_must_have_courses_map.keys())
    
        # Build course path
        self.course_path = modified_course_path_schedule
        self.recommended_courses = complete_recommended_courses
        self.course_bank = complete_course_bank
        self.prereq_graph = complete_course_prereq_graph
        self.must_have_courses = complete_must_have_courses

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

    def remove_course(self, course_code_to_remove: str, reschedule: bool=False):
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
            print(f"* Violations for REMOVE course '{course_code_to_remove}' in term {course_to_remove.term_idx}:\n{removal_violations}")
            
            if course_code_to_remove not in self.recommended_courses or self.course_bank[course_code_to_remove].is_prereq:
                raise Exception(f"\n* Course '{course_code_to_remove}' is a pre-requisite for a recommended course, cannot be removed. [prereq={course_to_remove.is_prereq}]")
            
            # Reschedule if requested
            elif reschedule:
                print(f"\n* Course '{course_code_to_remove}' is a recommended course, removing from recommended courses and rescheduling...")

                self.recommended_courses = self.recommended_courses - {course_code_to_remove}
                self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
                self.must_have_courses = self.must_have_courses - {course_code_to_remove}

                # Rebuild course path with must-have courses
                self.rebuild(window_start_term=self.curr_window_start, verbose=True)
            else:
                raise Exception(f"Cannot remove course '{course_code_to_remove}' due to scheduling violations.")

        # Simple removal successful, update course info
        else:
            course_to_remove.scheduled = False
            course_to_remove.term_idx = None
            
            self.course_path = remove_course_path
            self.recommended_courses = self.recommended_courses - {course_code_to_remove}
            self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
            self.must_have_courses = self.must_have_courses - {course_code_to_remove}

        print(f"* Course '{course_code_to_remove}' removed successfully.")
        return self
    
    # ─────────────────────────────────────────────────────────────────────────────
    # ADD COURSE
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_add_course(course_path: List[List[str]], course_code_to_add: str, must_have_window: Tuple[int, int]=None, max_classes_per_term=3) -> Tuple[List[List[str]], int]:
        add_course_path = deepcopy(course_path)

        # Check if must_have term location / window specified
        if must_have_window is not None:
            # Assumes valid window
            course_start_term, course_end_term = must_have_window

            for term_idx in range(course_start_term, course_end_term + 1):
                if len(add_course_path[term_idx]) < max_classes_per_term:
                    add_course_path[term_idx].append(course_code_to_add)

                    return add_course_path, term_idx
                
            raise Exception(f"Course '{course_code_to_add}' cannot be directly added in scheduling window {must_have_window}.")
        else:
            for term_idx in range(len(add_course_path)):
                if len(add_course_path[term_idx]) < max_classes_per_term:
                    add_course_path[term_idx].append(course_code_to_add)
                    return add_course_path, term_idx
                
            raise Exception(f"Course '{course_code_to_add}' cannot be directly added in any term.")

    def add_course(self, course_to_add: Course, max_classes_per_term: int=3, reschedule: bool=False):
        # Check if must_have term location / window specified 
        if course_to_add.must_have_window:
            max_terms = len(self.course_path)

            # Validate scheduling window pointers
            course_start_term, course_end_term = course_to_add.must_have_window
        
            if (course_start_term > course_end_term) or (course_start_term < 0) or (course_end_term >= max_terms):
                raise Exception(f"Invalid scheduling window {course_to_add.must_have_window} for course {course_to_add.course_code}.")
            
        # Checking if course is already scheduled
        existing_course = self.course_bank.get(course_to_add.course_code, None)
        if existing_course and existing_course.term_idx is not None:
            raise Exception(f"Course '{course_to_add.course_code}' is already scheduled (scheduled={existing_course.scheduled}).")
        
        # Proceed with addition
        add_course_path, new_course_term_idx = self._attempt_add_course(course_path=self.course_path, course_code_to_add=course_to_add.course_code, must_have_window=course_to_add.must_have_window, max_classes_per_term=max_classes_per_term)
        add_violations = self._validate_plan(course_path=add_course_path, course_bank=self.course_bank)

        # If violations, make must-have and schedule around
        if add_violations:
            print(f"* Violations for ADD course '{course_to_add.course_code}':\n{add_violations}")

            # Reschedule if requested
            if reschedule:
                add_as_must_have = {course_to_add.course_code: course_to_add}
                self.rebuild(window_start_term=self.curr_window_start, must_have_course_map=add_as_must_have)
            else:
                raise Exception(f"Cannot add course '{course_to_add.course_code}' due to scheduling violations.")
            
        # Simple addition successful, update course info
        else: 
            course_to_add.scheduled = True
            course_to_add.term_idx = new_course_term_idx

            self.course_path = add_course_path
            self.recommended_courses = self.recommended_courses | {course_to_add.course_code}
            self.course_bank = self.course_bank | {course_to_add.course_code: course_to_add}
            self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
            self.must_have_courses = self.must_have_courses | {course_to_add.course_code}

        print(f"* Course '{course_to_add.course_code}' added successfully.")
        return self
        
    # ─────────────────────────────────────────────────────────────────────────────
    # MOVE COURSE
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_move_course(course_path: List[List[str]], course_to_move: Course, move_window: Tuple[int, int], max_classes_per_term: int=3) -> Tuple[List[List[str]], int]:
        
        # First, remove course from original term
        remove_course_path = CoursePath._attempt_remove_course(course_path=course_path, course_to_remove=course_to_move)
        
        # Then, move course to new term
        move_course_path = deepcopy(remove_course_path)

        for term_idx in range(move_window[0], move_window[1] + 1):
            if len(move_course_path[term_idx]) < max_classes_per_term:
                move_course_path[term_idx].append(course_to_move.course_code)
                return move_course_path, term_idx
            
        raise Exception(f"Course '{course_to_move.course_code}' cannot be moved due to max capacity in scheduling window {move_window}.")
        
    def move_course(self, course_code_to_move: str, move_window: Tuple[int, int], max_classes_per_term: int=3, reschedule: bool=False):
        # Validate move window and move validity
        if move_window[0] > move_window[1] or move_window[0] < 0 or move_window[1] >= len(self.course_path):
            raise Exception(f"Invalid move window {move_window} for course {course_code_to_move}.")

        if move_window[0] < self.curr_window_start:
            raise Exception(f"Move window {move_window} must be within current window.")
        
        course_to_move = self.course_bank.get(course_code_to_move, None)
        if course_to_move is None:
            raise Exception(f"Course code '{course_code_to_move}' does not exist in course bank.")

        if course_to_move.term_idx is None:
            raise Exception(f"Cannot move unscheduled course '{course_code_to_move}'.")

        if move_window[0] <= course_to_move.term_idx <= move_window[1]:
            raise Exception(f"Course '{course_code_to_move}' is already in move window {move_window}.")

        # Proceed with move
        move_course_path, move_term_idx = self._attempt_move_course(course_path=self.course_path, course_to_move=course_to_move, move_window=move_window, max_classes_per_term=max_classes_per_term)
        move_violations = self._validate_plan(course_path=move_course_path, course_bank=self.course_bank)

        # If violations, make must-have and schedule around
        if move_violations:
            print(f"* Violations for MOVE course '{course_code_to_move}' in window {move_window}:\n{move_violations}")

            # Reschedule if requested
            if reschedule:
                course_to_move.must_have_window = move_window
                self.rebuild(window_start_term=self.curr_window_start)
            else:
                raise Exception(f"Cannot move course '{course_code_to_move}' due to scheduling violations.")

        # Simple move successful, update course info
        else:
            course_to_move.term_idx = move_term_idx
            course_to_move.must_have_window = move_window

            self.course_path = move_course_path

        print(f"* Course '{course_code_to_move}' moved successfully.")
        return self
    
    # ─────────────────────────────────────────────────────────────────────────────
    # REPLACE COURSE
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_replace_course(course_path: List[List[str]], new_course: Course, course_to_replace: Course) -> Tuple[List[List[str]], int]:
        # First, remove old course
        remove_course_path = CoursePath._attempt_remove_course(course_path=course_path, course_to_remove=course_to_replace)

        # Then, add new course
        if course_to_replace.must_have_window:
            new_course.must_have_window = course_to_replace.must_have_window
        else:
            new_course.must_have_window = (course_to_replace.term_idx, course_to_replace.term_idx)

        # Reframe ADD error as REPLACE error
        try:
            add_course_path, new_course_term_idx = CoursePath._attempt_add_course(course_path=remove_course_path, course_code_to_add=new_course.course_code, must_have_window=new_course.must_have_window, max_classes_per_term=3)

        except Exception as e:
            raise Exception(f"Error attempting to replace course '{course_to_replace.course_code}' with '{new_course.course_code}': {e}")

        return add_course_path, new_course_term_idx

    def replace_course(self, new_course: Course, course_code_to_replace: str, reschedule: bool=False):
    
        # Validate course to replace
        course_to_replace = self.course_bank.get(course_code_to_replace, None)
        if course_to_replace is None:
            raise Exception(f"Course code '{course_code_to_replace}' does not exist in course bank.")
        
        if course_to_replace.term_idx is None:
            raise Exception(f"Course '{course_code_to_replace}' not scheduled / missing term index.")

        # Validate new course
        if new_course.course_code in self.course_bank and new_course.term_idx is not None:
            raise Exception(f"Course '{new_course.course_code}' is already scheduled (scheduled={new_course.scheduled})")
        
        if new_course.must_have_window:
            print(f"Warning: replacing course '{course_code_to_replace}' with course '{new_course.course_code}' may override existing must-have window.")

        # Attempt to replace course
        replace_course_path, replace_term_idx = self._attempt_replace_course(course_path=self.course_path, new_course=new_course, course_to_replace=course_to_replace)
        replacement_violations = self._validate_plan(course_path=replace_course_path, course_bank=self.course_bank)

        # If violations, make must-have and schedule around
        if replacement_violations:
            print(f"* Replacement violations for course '{course_code_to_replace}' in term {replace_term_idx}: {replacement_violations}")

            if course_code_to_replace not in self.recommended_courses or self.course_bank[course_code_to_replace].is_prereq:
                raise Exception(f"Course '{course_code_to_replace}' is a pre-requisite for a recommended course, cannot be replaced.")
            
            # Reschedule if requested
            elif reschedule:
                print(f"* Course '{course_code_to_replace}' is a recommended course, replacing with '{new_course.course_code}' and rescheduling...")
                self.recommended_courses = self.recommended_courses - {course_code_to_replace} | {new_course.course_code}
                self.course_bank = self.course_bank | {new_course.course_code: new_course}
                self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)
                self.must_have_courses = self.must_have_courses - {course_code_to_replace} | {new_course.course_code}

                # Rebuild course path with must-have courses
                self.rebuild(window_start_term=self.curr_window_start, verbose=True)
            else:
                raise Exception(f"Cannot replace course '{course_code_to_replace}' with '{new_course.course_code}' due to scheduling violations.")

        # Simple replacement successful, update course info
        else:
            new_course.scheduled = True
            new_course.term_idx = replace_term_idx
            new_course.must_have_window = course_to_replace.must_have_window

            course_to_replace.scheduled = False
            course_to_replace.term_idx = None
            course_to_replace.must_have_window = None

            if course_code_to_replace in self.recommended_courses:
                self.recommended_courses = self.recommended_courses - {course_code_to_replace} | {new_course.course_code}

            self.course_bank = self.course_bank | {new_course.course_code: new_course}
            self.prereq_graph = rebuild_prereq_graph(course_bank=self.course_bank, courses=self.recommended_courses)

            if course_code_to_replace in self.must_have_courses:
                self.must_have_courses = self.must_have_courses - {course_code_to_replace} | {new_course.course_code}

            self.course_path = replace_course_path

        print(f"* Course '{course_code_to_replace}' replaced with '{new_course.course_code}' successfully.")
        return self

    # ─────────────────────────────────────────────────────────────────────────────
    # SWAP COURSES
    # ─────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _attempt_swap_courses(course_path: List[List[str]], course_1: Course, course_2: Course) -> Tuple[List[List[str]], int, int]:
        # First, remove course 1 and move course 2 to course 1's term
        remove_course_path = CoursePath._attempt_remove_course(course_path=course_path, course_to_remove=course_1)
        course_2_move_window = (course_1.term_idx, course_1.term_idx)
        move_course_path, course_2_new_term_idx = CoursePath._attempt_move_course(course_path=remove_course_path, course_to_move=course_2, move_window=course_2_move_window, max_classes_per_term=3)

        # Then, add course 1 to course 2's term
        course_1_add_window = (course_2.term_idx, course_2.term_idx)
        add_course_path, course_1_new_term_idx = CoursePath._attempt_add_course(course_path=move_course_path, course_code_to_add=course_1.course_code, must_have_window=course_1_add_window, max_classes_per_term=3)

        return add_course_path, course_1_new_term_idx, course_2_new_term_idx

    def swap_courses(self, course_code_1: str, course_code_2: str):
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
        
        # Validate indices in case of windows
        if course_1.must_have_window and (course_1.must_have_window[0] > course_2.term_idx or course_1.must_have_window[1] < course_2.term_idx):
            raise Exception(f"Cannot swap courses '{course_code_1}' and '{course_code_2}'; term {course_2.term_idx} is outside of course '{course_code_1}' must-have window.")

        if course_2.must_have_window and (course_2.must_have_window[0] > course_1.term_idx or course_2.must_have_window[1] < course_1.term_idx):
            raise Exception(f"Cannot swap courses '{course_code_1}' and '{course_code_2}'; term {course_1.term_idx} is outside of course '{course_code_2}' must-have window.")

        # Attempt to swap courses
        swap_course_path, course_1_new_term_idx, course_2_new_term_idx = CoursePath._attempt_swap_courses(course_path=self.course_path, course_1=course_1, course_2=course_2)
        swap_violations = self._validate_plan(course_path=swap_course_path, course_bank=self.course_bank)

        # If violations, cannot swap directly
        if swap_violations:
            print(f"* Swap violations for courses '{course_code_1}' and '{course_code_2}': {swap_violations}")
            raise Exception(f"Cannot swap courses '{course_code_1}' [term={course_1.term_idx} -> {course_1_new_term_idx}] and '{course_code_2}' [term={course_2.term_idx} -> {course_2_new_term_idx}] due to scheduling violations.")
        
        # Simple swap successful, update course info
        course_1.term_idx = course_1_new_term_idx
        course_2.term_idx = course_2_new_term_idx

        self.course_path = swap_course_path

        print(f"* Courses '{course_code_1}' and '{course_code_2}' swapped successfully.")
        return self