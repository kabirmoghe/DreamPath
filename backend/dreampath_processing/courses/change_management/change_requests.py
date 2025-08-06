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
    # Validate term_idx
    term_idx = course_to_remove.term_idx

    if term_idx is None:
        raise Exception(f"Course '{course_to_remove.course_code}' not scheduled / missing term index.")

    elif term_idx < 0 or term_idx >= len(course_path_obj.course_path):
        raise Exception(f"Term index must be in range [0, {len(course_path_obj.course_path) - 1}]")
    
    if course_to_remove.course_code in course_path_obj.course_path[term_idx]:
        remove_course_path = copy.deepcopy(course_path_obj.course_path)
        remove_course_path[term_idx].remove(course_to_remove.course_code) 

        return remove_course_path
    else:
        raise Exception(f"Course '{course_to_remove.course_code}' not in specified term '{term_idx}' for course_path.")

def remove_course(course_path_obj: CoursePath, course_code_to_remove: str) -> CoursePath:
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

    if course_to_remove.term_idx < course_path_obj.curr_window_start:
        raise Exception(f"Term index {course_to_remove.term_idx} for removal must be within current window.")

    # Attempt to remove course and check for validity
    try:
        remove_course_path = attempt_remove_course(course_path_obj=course_path_obj, course_to_remove=course_to_remove)
        removal_violations = validate_plan(remove_course_path)

    except Exception as e:
        raise Exception(f"Error attempting to remove course {course_code_to_remove}: {e}")

    # If removal violates prereq. graph, check if course is recommended and remove from recommended courses; if prereq., raise error
    if removal_violations:
        print(f"* Violations for REMOVE course '{course_code_to_remove}' in term {course_to_remove.term_idx}:\n{removal_violations}")
        
        if course_code_to_remove not in course_path_obj.recommended_courses or course_path_obj.course_bank[course_code_to_remove].is_prereq:
            raise Exception(f"\n* Course '{course_code_to_remove}' is a pre-requisite for a recommended course, cannot be removed. [prereq={course_to_remove.is_prereq}]")
        else:
            print(f"\n* Course '{course_code_to_remove}' is a recommended course, removing from recommended courses and rescheduling...")
            temp_removed_course_path_obj = copy.deepcopy(course_path_obj)
            temp_removed_course_path_obj.recommended_courses = course_path_obj.recommended_courses - {course_code_to_remove}
            temp_removed_course_path_obj.prereq_graph = rebuild_prereq_graph(course_bank=course_path_obj.course_bank, courses=temp_removed_course_path_obj.recommended_courses)
            temp_removed_course_path_obj.must_have_courses = course_path_obj.must_have_courses - {course_code_to_remove}

            # Rebuild course path with must-have courses
            removed_course_path_obj = rebuild_course_path_with_must_haves(initial_course_path=temp_removed_course_path_obj, 
                                                                      window_start_term=course_path_obj.curr_window_start, verbose=True)

    # Simple removal successful
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

def add_course(course_path_obj: CoursePath, course_to_add: Course, max_classes_per_term: int=3) -> CoursePath:
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
    
    # Otherwise, attempt to add course
    try:
        add_course_path, new_course_term_idx = attempt_add_course(course_path_obj, course_to_add, max_classes_per_term)
        add_violations = validate_plan(add_course_path)

        if add_violations:
            print(f"* Violations for ADD course '{course_to_add.course_code}':\n{add_violations}")

            # Make must have and schedule around
            add_as_must_have = {course_to_add.course_code: course_to_add}
            add_course_path_obj = rebuild_course_path_with_must_haves(initial_course_path=course_path_obj,
                                                window_start_term=course_path_obj.curr_window_start,
                                                must_have_course_map=add_as_must_have)
        else:
            # Update course info / not currently handling course_graph updates
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

    except Exception as e:
        print(f"* Error attempting to add course '{course_to_add.course_code}' in window {course_to_add.must_have_window}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# MOVE COURSE
# ─────────────────────────────────────────────────────────────────────────────
def attempt_move_course(course_path_obj: CoursePath, course_to_move: Course, move_window: Tuple[int, int], max_classes_per_term: int=3):
     pass

def move_course(course_path_obj: CoursePath, course_to_move: Course, move_window: Tuple[int, int], max_classes_per_term: int=3) -> CoursePath:
    # Validate move window
    if move_window[0] > move_window[1] or move_window[0] < 0 or move_window[1] >= len(course_path_obj.course_path):
        raise Exception(f"Invalid move window {move_window} for course {course_to_move.course_code}.")

    if move_window[0] < course_path_obj.curr_window_start:
        raise Exception(f"Move window {move_window} must be within current window.")
    
    # Check if course is already scheduled
    if course_to_move.term_idx is None:
        raise Exception(f"Cannot move unscheduled course '{course_to_move.course_code}'.")

    # Check if course is in move window
    if move_window[0] <= course_to_move.term_idx <= move_window[1]:
        raise Exception(f"Course '{course_to_move.course_code}' is already in move window {move_window}.")


    

# ─────────────────────────────────────────────────────────────────────────────
# REPLACE COURSE
# ─────────────────────────────────────────────────────────────────────────────

def attempt_replace_course(course_path, new_course, old_course_code, term_idx):
    # Validate term_idx
    if term_idx < 0 or term_idx >= len(course_path):
        raise Exception(f"term_idx must be in range [0, {len(course_path) - 1}]")

    # Extract position of old course in term
    old_course_idx = course_path[term_idx].index(old_course_code) if old_course_code in course_path[term_idx] else None

    if old_course_idx:
        # Replace old course with new course
        course_path_swapped = copy.deepcopy(course_path)
        course_path_swapped[term_idx][old_course_idx] = new_course.course_code

        return course_path_swapped
    else:
        raise Exception(f"Course '{old_course_code}' not in specified term '{term_idx}' for course_path.") # Invalid course for replacement
    
def replace_course(course_path_obj: CoursePath, new_course: Course, old_course_code: str, term_idx: int) -> CoursePath:
    mod_course_path = copy.deepcopy(course_path_obj.course_path)
    attempt_replace_course(mod_course_path, new_course, old_course_code, term_idx)
    replacement_violations = validate_plan(mod_course_path)
    
    if replacement_violations:
        print(f"* Replacement violations for course '{old_course_code}' in term {term_idx}: {replacement_violations}")

        old_course_obj = course_path_obj.course_bank[old_course_code]
        if old_course_code not in course_path_obj.recommended_courses or old_course_obj.is_prereq:
            raise Exception(f"Course '{old_course_code}' is a pre-requisite for a recommended course, cannot be replaced.")
        else:   
            # print(f"* Course '{old_course}' is a recommended course, replacing with '{new_course}'.")
            # replaced_recommended_courses = course_path_obj.recommended_courses - {old_course} | {new_course}
            # replaced_course_path = build_course_path(replaced_recommended_courses, course_path_obj.course_bank)
            # return replaced_course_path
            pass

    else: # Simple replacement successful
        return
