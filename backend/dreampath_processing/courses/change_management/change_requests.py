from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from dreampath_processing.courses.schedule_modules.course_path import CoursePath
from dreampath_processing.courses.schedule_modules.course import Course
from dreampath_processing.courses.scheduling_helpers import validate_plan, rebuild_course_path_with_must_haves
from dreampath_processing.courses.course_relationship_handling import rebuild_prereq_graph
import copy

class ChangeType(Enum):
    REMOVE = "remove"
    ADD = "add"
    MOVE = "move"
    REPLACE = "replace"
    SWAP = "swap"

    def __str__(self):
        return self.value

@dataclass
class ChangeRequest:
    change_type: ChangeType
    target_courses: Optional[List[str]]
    target_term_index: int
    new_courses: Optional[List[Course]]

# ─────────────────────────────────────────────────────────────────────────────
# REMOVE COURSE
# ─────────────────────────────────────────────────────────────────────────────

def attempt_remove_course(course_path_obj: CoursePath, course_to_remove: Course) -> List[List[str]]:
    """
    Attempt to remove course from course path

    Args:
        course_path_obj (CoursePath): Course path to remove course from
        course_to_remove (Course): Course to remove from course path

    Returns:
        List[List[str]]: Course path list with course removed
    """
    
    remove_course_path = copy.deepcopy(course_path_obj.course_path)
    remove_course_path[course_to_remove.term_idx].remove(course_to_remove.course_code) 

    return remove_course_path

def remove_course(course_path_obj: CoursePath, course_code_to_remove: str, reschedule: bool=False) -> CoursePath:
    """
    Remove courses from a course path

    Args:
        course_path_obj (CoursePath): Course path to remove courses from
        courses_to_remove (set): Set of course codes to remove from the course path

    Returns:
        CoursePath: Course path object with course removed
    """
    course_to_remove = course_path_obj.course_bank.get(course_code_to_remove, None)
    if course_to_remove is None:
        raise Exception(f"Course code '{course_code_to_remove}' does not exist in course bank.")
    
    if course_to_remove.term_idx is None:
        raise Exception(f"Course '{course_to_remove.course_code}' not scheduled / missing term index.")

    if course_to_remove.term_idx < 0 or course_to_remove.term_idx >= len(course_path_obj.course_path):
        raise Exception(f"Term index must be in range [0, {len(course_path_obj.course_path) - 1}]")

    if course_to_remove.term_idx < course_path_obj.curr_window_start:
        raise Exception(f"Term index {course_to_remove.term_idx} for removal must be within current window.")

    # Attempt to remove course and check for validity
    try:
        remove_course_path = attempt_remove_course(course_path_obj=course_path_obj, course_to_remove=course_to_remove)
        removal_violations = validate_plan(course_path=remove_course_path, course_bank=course_path_obj.course_bank)

    except Exception as e:
        raise Exception(f"Error attempting to remove course {course_code_to_remove}: {e}")

    # If removal violates prereq. graph, check if course is recommended and remove from recommended courses; if prereq., raise error
    if removal_violations:
        print(f"* Violations for REMOVE course '{course_code_to_remove}' in term {course_to_remove.term_idx}:\n{removal_violations}")
        
        if course_code_to_remove not in course_path_obj.recommended_courses or course_path_obj.course_bank[course_code_to_remove].is_prereq:
            raise Exception(f"\n* Course '{course_code_to_remove}' is a pre-requisite for a recommended course, cannot be removed. [prereq={course_to_remove.is_prereq}]")
        
        # Reschedule if requested
        elif reschedule:
            print(f"\n* Course '{course_code_to_remove}' is a recommended course, removing from recommended courses and rescheduling...")
            temp_remove_course_path_obj = copy.deepcopy(course_path_obj)
            temp_remove_course_path_obj.recommended_courses = course_path_obj.recommended_courses - {course_code_to_remove}
            temp_remove_course_path_obj.prereq_graph = rebuild_prereq_graph(course_bank=course_path_obj.course_bank, courses=temp_remove_course_path_obj.recommended_courses)
            temp_remove_course_path_obj.must_have_courses = course_path_obj.must_have_courses - {course_code_to_remove}

            # Rebuild course path with must-have courses
            removed_course_path_obj = rebuild_course_path_with_must_haves(initial_course_path=temp_remove_course_path_obj, 
                                                                      window_start_term=course_path_obj.curr_window_start, verbose=True)
        else:
            raise Exception(f"Cannot remove course '{course_code_to_remove}' due to scheduling violations.")

    # Simple removal successful, update course info
    else:
        course_to_remove.scheduled = False
        course_to_remove.term_idx = None
        
        removed_recommended_courses = course_path_obj.recommended_courses - {course_code_to_remove}
        removed_prereq_graph = rebuild_prereq_graph(course_bank=course_path_obj.course_bank, courses=removed_recommended_courses)
        removed_must_have_courses = course_path_obj.must_have_courses - {course_code_to_remove}

        removed_course_path_obj = CoursePath(course_path=remove_course_path,
                                         course_bank=course_path_obj.course_bank,
                                         prereq_graph=removed_prereq_graph,
                                         recommended_courses=removed_recommended_courses,
                                         must_have_courses=removed_must_have_courses)
        
    print(f"* Course '{course_code_to_remove}' removed successfully.")
    return removed_course_path_obj

# ─────────────────────────────────────────────────────────────────────────────
# ADD COURSE
# ─────────────────────────────────────────────────────────────────────────────
def attempt_add_course(course_path_obj: CoursePath, course_to_add: Course, max_classes_per_term=3) -> Tuple[List[List[str]], int]:
    add_course_path = copy.deepcopy(course_path_obj.course_path)

    # Check if must_have term location / window specified
    if course_to_add.must_have_window:
        # Assumes valid window
        course_start_term, course_end_term = course_to_add.must_have_window

        for term_idx in range(course_start_term, course_end_term + 1):
            if len(add_course_path[term_idx]) < max_classes_per_term:
                add_course_path[term_idx].append(course_to_add.course_code)

                return add_course_path, term_idx
            
        raise Exception(f"Course '{course_to_add.course_code}' cannot be directly added in scheduling window {course_to_add.must_have_window}.")
    
    else:
        for term_idx in range(len(add_course_path)):
            if len(add_course_path[term_idx]) < max_classes_per_term:
                add_course_path[term_idx].append(course_to_add.course_code)
                return add_course_path, term_idx
            
        raise Exception(f"Course '{course_to_add.course_code}' cannot be directly added in any term.")

def add_course(course_path_obj: CoursePath, course_to_add: Course, max_classes_per_term: int=3, reschedule: bool=False) -> CoursePath:
    # Check if must_have term location / window specified 
    if course_to_add.must_have_window:
        max_terms = len(course_path_obj.course_path)

        # Validate scheduling window pointers
        course_start_term, course_end_term = course_to_add.must_have_window
    
        if (course_start_term > course_end_term) or (course_start_term < 0) or (course_end_term >= max_terms):
            raise Exception(f"Invalid scheduling window {course_to_add.must_have_window} for course {course_to_add.course_code}.")
        
    # Checking if course is already scheduled
    existing_course = course_path_obj.course_bank.get(course_to_add.course_code, None)
    if existing_course and existing_course.term_idx is not None:
        raise Exception(f"Course '{course_to_add.course_code}' is already scheduled (scheduled={existing_course.scheduled}).")
    
    # Proceed with addition
    add_course_path, new_course_term_idx = attempt_add_course(course_path_obj, course_to_add, max_classes_per_term)
    add_violations = validate_plan(course_path=add_course_path, course_bank=course_path_obj.course_bank)

    # If violations, make must-have and schedule around
    if add_violations:
        print(f"* Violations for ADD course '{course_to_add.course_code}':\n{add_violations}")

        # Reschedule if requested
        if reschedule:
            add_as_must_have = {course_to_add.course_code: course_to_add}
            add_course_path_obj = rebuild_course_path_with_must_haves(initial_course_path=course_path_obj,
                                            window_start_term=course_path_obj.curr_window_start,
                                            must_have_course_map=add_as_must_have)
        else:
            raise Exception(f"Cannot add course '{course_to_add.course_code}' due to scheduling violations.")
        
    # Simple addition successful, update course info
    else: 
        course_to_add.scheduled = True
        course_to_add.term_idx = new_course_term_idx

        added_recommended_courses = course_path_obj.recommended_courses | {course_to_add.course_code}
        added_course_bank = course_path_obj.course_bank | {course_to_add.course_code: course_to_add}
        added_prereq_graph = rebuild_prereq_graph(course_bank=added_course_bank, courses=added_recommended_courses)
        added_must_have_courses = course_path_obj.must_have_courses | {course_to_add.course_code}
        
        add_course_path_obj = CoursePath(
            course_path=add_course_path,
            recommended_courses=added_recommended_courses,
            must_have_courses=added_must_have_courses,
            course_bank=added_course_bank,
            prereq_graph=added_prereq_graph
        )

    print(f"* Course '{course_to_add.course_code}' added successfully.")
    return add_course_path_obj

# ─────────────────────────────────────────────────────────────────────────────
# MOVE COURSE
# ─────────────────────────────────────────────────────────────────────────────
def attempt_move_course(course_path_obj: CoursePath, course_to_move: Course, move_window: Tuple[int, int], max_classes_per_term: int=3) -> Tuple[List[List[str]], int]:
    
    # First, remove course from original term
    remove_course_path = attempt_remove_course(course_path_obj=course_path_obj, course_to_remove=course_to_move)
    
    # Then, move course to new term
    move_course_path = copy.deepcopy(remove_course_path)

    for term_idx in range(move_window[0], move_window[1] + 1):
        if len(move_course_path[term_idx]) < max_classes_per_term:
            move_course_path[term_idx].append(course_to_move.course_code)
            return move_course_path, term_idx
        
    raise Exception(f"Course '{course_to_move.course_code}' cannot be moved due to max capacity in scheduling window {move_window}.")

def move_course(course_path_obj: CoursePath, course_code_to_move: str, move_window: Tuple[int, int], max_classes_per_term: int=3, reschedule: bool=False) -> CoursePath:
    # Validate move window and move validity
    if move_window[0] > move_window[1] or move_window[0] < 0 or move_window[1] >= len(course_path_obj.course_path):
        raise Exception(f"Invalid move window {move_window} for course {course_code_to_move}.")

    if move_window[0] < course_path_obj.curr_window_start:
        raise Exception(f"Move window {move_window} must be within current window.")
    
    course_to_move = course_path_obj.course_bank.get(course_code_to_move, None)
    if course_to_move is None:
        raise Exception(f"Course code '{course_code_to_move}' does not exist in course bank.")

    if course_to_move.term_idx is None:
        raise Exception(f"Cannot move unscheduled course '{course_code_to_move}'.")

    if move_window[0] <= course_to_move.term_idx <= move_window[1]:
        raise Exception(f"Course '{course_code_to_move}' is already in move window {move_window}.")

    # Proceed with move
    move_course_path, move_term_idx = attempt_move_course(course_path_obj=course_path_obj, course_to_move=course_to_move, move_window=move_window, max_classes_per_term=max_classes_per_term)
    move_violations = validate_plan(course_path=move_course_path, course_bank=course_path_obj.course_bank)

    # If violations, make must-have and schedule around
    if move_violations:
        print(f"* Violations for MOVE course '{course_code_to_move}' in window {move_window}:\n{move_violations}")

        # Reschedule if requested
        if reschedule:
            course_to_move.must_have_window = move_window
            move_course_path_obj = rebuild_course_path_with_must_haves(initial_course_path=course_path_obj,
                                                                    window_start_term=course_path_obj.curr_window_start)
        else:
            raise Exception(f"Cannot move course '{course_code_to_move}' due to scheduling violations.")

    # Simple move successful, update course info
    else:
        course_to_move.term_idx = move_term_idx
        course_to_move.must_have_window = move_window

        move_course_path_obj = CoursePath(
            course_path=move_course_path,
            course_bank=course_path_obj.course_bank,
            prereq_graph=course_path_obj.prereq_graph,
            recommended_courses=course_path_obj.recommended_courses,
            must_have_courses=course_path_obj.must_have_courses
        )

    print(f"* Course '{course_code_to_move}' moved successfully.")
    return move_course_path_obj

# ─────────────────────────────────────────────────────────────────────────────
# REPLACE COURSE
# ─────────────────────────────────────────────────────────────────────────────

def attempt_replace_course(course_path_obj: CoursePath, new_course: Course, course_to_replace: Course) -> Tuple[List[List[str]], int]:
    # First, remove old course
    remove_course_path = attempt_remove_course(course_path_obj=course_path_obj, course_to_remove=course_to_replace)

    # Then, add new course
    if course_to_replace.must_have_window:
        new_course.must_have_window = course_to_replace.must_have_window
    else:
        new_course.must_have_window = (course_to_replace.term_idx, course_to_replace.term_idx)

    # Reframe ADD error as REPLACE error
    try:
        add_course_path, new_course_term_idx = attempt_add_course(course_path_obj=course_path_obj, course_to_add=new_course, max_classes_per_term=3)

    except Exception as e:
        raise Exception(f"Error attempting to replace course '{course_to_replace.course_code}' with '{new_course.course_code}': {e}")

    return add_course_path, new_course_term_idx
    
def replace_course(course_path_obj: CoursePath, new_course: Course, course_code_to_replace: str, reschedule: bool=False) -> CoursePath:
   
    # Validate course to replace
    course_to_replace = course_path_obj.course_bank.get(course_code_to_replace, None)
    if course_to_replace is None:
        raise Exception(f"Course code '{course_code_to_replace}' does not exist in course bank.")
    
    if course_to_replace.term_idx is None:
        raise Exception(f"Course '{course_code_to_replace}' not scheduled / missing term index.")

    # Validate new course
    if new_course.course_code in course_path_obj.course_bank and new_course.term_idx is not None:
        raise Exception(f"Course '{new_course.course_code}' is already scheduled (scheduled={new_course.scheduled})")
    
    if new_course.must_have_window:
        print(f"Warning: replacing course '{course_code_to_replace}' with course '{new_course.course_code}' may override existing must-have window.")

    # Attempt to replace course
    replace_course_path, replace_term_idx = attempt_replace_course(course_path_obj=course_path_obj, new_course=new_course, course_to_replace=course_to_replace)
    replacement_violations = validate_plan(course_path=replace_course_path, course_bank=course_path_obj.course_bank)

    # If violations, make must-have and schedule around
    if replacement_violations:
        print(f"* Replacement violations for course '{course_code_to_replace}' in term {replace_term_idx}: {replacement_violations}")

        course_to_replace_obj = course_path_obj.course_bank[course_code_to_replace]
        if course_code_to_replace not in course_path_obj.recommended_courses or course_to_replace_obj.is_prereq:
            raise Exception(f"Course '{course_code_to_replace}' is a pre-requisite for a recommended course, cannot be replaced.")
        
        # Reschedule if requested
        elif reschedule:
            print(f"* Course '{course_code_to_replace}' is a recommended course, replacing with '{new_course.course_code}' and rescheduling...")
            temp_replace_course_path_obj = copy.deepcopy(course_path_obj)
            temp_replace_course_path_obj.recommended_courses = course_path_obj.recommended_courses - {course_code_to_replace} | {new_course.course_code}
            temp_replace_course_path_obj.course_bank = course_path_obj.course_bank | {new_course.course_code: new_course}
            temp_replace_course_path_obj.prereq_graph = rebuild_prereq_graph(course_bank=temp_replace_course_path_obj.course_bank, courses=temp_replace_course_path_obj.recommended_courses)
            temp_replace_course_path_obj.must_have_courses = course_path_obj.must_have_courses - {course_code_to_replace} | {new_course.course_code}

            # Rebuild course path with must-have courses
            replace_course_path_obj = rebuild_course_path_with_must_haves(initial_course_path=temp_replace_course_path_obj, 
                                                                      window_start_term=course_path_obj.curr_window_start, verbose=True)
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

        if course_code_to_replace in course_path_obj.recommended_courses:
            replaced_recommended_courses = course_path_obj.recommended_courses - {course_code_to_replace} | {new_course.course_code}
        else:
            replaced_recommended_courses = course_path_obj.recommended_courses

        replaced_course_bank = course_path_obj.course_bank | {new_course.course_code: new_course}

        # ASSUMPTION: prereq. tree for new course is already built in validate_plan
        replaced_prereq_graph = rebuild_prereq_graph(course_bank=replaced_course_bank, courses=replaced_recommended_courses)

        if course_code_to_replace in course_path_obj.must_have_courses:
            replaced_must_have_courses = course_path_obj.must_have_courses - {course_code_to_replace} | {new_course.course_code}
        else:
            replaced_must_have_courses = course_path_obj.must_have_courses

        replace_course_path_obj = CoursePath(
            course_path=replace_course_path,
            recommended_courses=replaced_recommended_courses,
            course_bank=replaced_course_bank,
            prereq_graph=replaced_prereq_graph,
            curr_window_start=course_path_obj.curr_window_start,
            must_have_courses=replaced_must_have_courses
        )

    print(f"* Course '{course_code_to_replace}' replaced with '{new_course.course_code}' successfully.")
    return replace_course_path_obj
