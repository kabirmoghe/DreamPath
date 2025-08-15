from copy import deepcopy
from typing import List, Dict, Optional, Tuple
from dreampath_processing.courses.schedule_modules.course_path import CoursePath
from dreampath_processing.courses.schedule_modules.course import Course, MAJOR, COMPLEMENTARY
from dreampath_processing.courses.course_relationship_handling import course_code_exists, is_major_course
from dreampath_processing.courses.course_path_agent.types import ExecuteOpResult, RemoveOp, AddOp, MoveOp, ReplaceOp, SwapOp, RebuildOp, Op, ExtractedOpType

# Utilities
class RequiresRescheduleError(Exception): ...
class ScheduleConflictError(Exception): ...
class ValidationError(Exception): ...

def snapshot_path(cp: CoursePath) -> CoursePath:
    return deepcopy(cp)

def compute_diff(before: CoursePath, after: CoursePath) -> Dict[str, List[Dict[str, str]]]:
    diff = {"removed": [], "added": [], "moved": []}
    
    # Get scheduled courses before and after
    before_courses = {c_code for c_code, c in before.course_bank.items() if c.scheduled}
    after_courses = {c_code for c_code, c in after.course_bank.items() if c.scheduled}

    # Removals
    removed_courses = before_courses - after_courses
    for course_code in removed_courses:
        diff["removed"].append({"course_code": before.course_bank[course_code].course_code, "term_idx": before.course_bank[course_code].term_idx})
    
    # Additions
    added_courses = after_courses - before_courses
    for course_code in added_courses:
        diff["added"].append({"course_code": after.course_bank[course_code].course_code, "term_idx": after.course_bank[course_code].term_idx})

    # Moves
    moved_courses = before_courses & after_courses
    for course_code in moved_courses:
        if before.course_bank[course_code].term_idx != after.course_bank[course_code].term_idx:
            diff["moved"].append({"course_code": before.course_bank[course_code].course_code, "old_term_idx": before.course_bank[course_code].term_idx, "new_term_idx": after.course_bank[course_code].term_idx})

    return diff

def summarize_diff(diff: Dict[str, List[Dict[str, str]]]) -> str:
    summary = ""
    for change_type, changes in diff.items():
        for change in changes:
            if change_type == "removed":
                summary += f"\n- {change['course_code']} (term {change['term_idx']})"
            elif change_type == "added":
                summary += f"\n+ {change['course_code']} (term {change['term_idx']})"
            elif change_type == "moved":
                summary += f"\nMoved {change['course_code']} (term {change['old_term_idx']} -> {change['new_term_idx']})"

    return summary

def construct_course(course_code: str, major_name: str, must_have_window: Optional[Tuple[int, int]] = None) -> Course:
    # Validate existence externally
    if not course_code_exists(course_code):
        raise Exception(f"Unknown course code '{course_code}'.")
    ctype = MAJOR if is_major_course(course_code, major_name) else COMPLEMENTARY
    return Course(
        course_code=course_code,
        course_type=ctype,
        scheduled=False,
        is_prereq=False,
        prereq_tree=None,
        must_have_window=must_have_window,
        term_idx=None,
        term_idx_in_term=None,
        course_name=None,
        course_description=None,
    )

class CoursePathTools:
    def __init__(self, course_path: CoursePath, major_name: str):
        self.cp = course_path
        self.major_name = major_name
        self.window_start_term = course_path.curr_window_start

    def remove(self, p: RemoveOp) -> ExecuteOpResult:
        before = snapshot_path(self.cp)
        try:
            self.cp.remove_course(course_code_to_remove=p.course_code, reschedule=p.reschedule)
            after = snapshot_path(self.cp)
            return ExecuteOpResult(ok=True, diff=compute_diff(before, after), warnings=[], error=None, requires_reschedule=False, new_version=None)
        except Exception as e:
            # Revert to original path
            self.cp = before
            msg = str(e)
            if "requires rescheduling" in msg:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "REQUIRES_RESCHEDULE", "details": msg}, requires_reschedule=True, new_version=None)
            else:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "VALIDATION_ERROR", "details": msg}, requires_reschedule=False, new_version=None)

    def add(self, p: AddOp) -> ExecuteOpResult:
        before = snapshot_path(self.cp)
        try:
            add_window = None
            if p.must_have_window:
                add_window = p.must_have_window
            elif p.add_to_term is not None:
                add_window = (p.add_to_term, p.add_to_term)

            course_obj = construct_course(p.course_code, self.major_name, add_window)
            self.cp.add_course(course_to_add=course_obj, reschedule=p.reschedule)
            after = snapshot_path(self.cp)
            return ExecuteOpResult(ok=True, diff=compute_diff(before, after), warnings=[], error=None, requires_reschedule=False, new_version=None)
        
        except Exception as e:
            # Revert to original path
            self.cp = before
            msg = str(e)
            if "requires rescheduling" in msg:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "REQUIRES_RESCHEDULE", "details": msg}, requires_reschedule=True, new_version=None)
            else:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "VALIDATION_ERROR", "details": msg}, requires_reschedule=False, new_version=None)

    def move(self, p: MoveOp) -> ExecuteOpResult:
        before = snapshot_path(self.cp)
        if p.move_window is None:
            if p.move_to_term is None:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "VALIDATION_ERROR", "details": "Move requires either move_to_term or move_window."}, requires_reschedule=False, new_version=None)
            move_window = (p.move_to_term, p.move_to_term)
        else:
            move_window = p.move_window
        try:
            self.cp.move_course(course_code_to_move=p.course_code, move_window=move_window, reschedule=p.reschedule)
            after = snapshot_path(self.cp)
            return ExecuteOpResult(ok=True, diff=compute_diff(before, after), warnings=[], error=None, requires_reschedule=False, new_version=None)
        except Exception as e:
            # Revert to original path
            self.cp = before
            msg = str(e)
            if "requires rescheduling" in msg:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "REQUIRES_RESCHEDULE", "details": msg}, requires_reschedule=True, new_version=None)
            else:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "VALIDATION_ERROR", "details": msg}, requires_reschedule=False, new_version=None)

    def replace(self, p: ReplaceOp) -> ExecuteOpResult:
        before = snapshot_path(self.cp)
        try:
            new_course = construct_course(p.new_course_code, self.major_name, p.must_have_window)
            self.cp.replace_course(new_course=new_course, old_course_code=p.old_course_code, reschedule=p.reschedule)
            after = snapshot_path(self.cp)
            return ExecuteOpResult(ok=True, diff=compute_diff(before, after), warnings=[], error=None, requires_reschedule=False, new_version=None)
        except Exception as e:
            msg = str(e)
            if "requires rescheduling" in msg:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "REQUIRES_RESCHEDULE", "details": msg}, requires_reschedule=True, new_version=None)
            else:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "VALIDATION_ERROR", "details": msg}, requires_reschedule=False, new_version=None)

    def swap(self, p: SwapOp) -> ExecuteOpResult:
        before = snapshot_path(self.cp)
        try:
            self.cp.swap_courses(course_code_1=p.course_code_1, course_code_2=p.course_code_2)
            after = snapshot_path(self.cp)
            return ExecuteOpResult(ok=True, diff=compute_diff(before, after), warnings=[], error=None, requires_reschedule=False, new_version=None)
        except Exception as e:
            # Revert to original path
            self.cp = before
            msg = str(e)
            if "scheduling violations" in msg:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "SCHEDULE_CONFLICT", "details": msg}, requires_reschedule=False, new_version=None)
            else:
                return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "VALIDATION_ERROR", "details": msg}, requires_reschedule=False, new_version=None)

    def rebuild(self, p: RebuildOp) -> ExecuteOpResult:
        before = snapshot_path(self.cp)
        must_have_map = {}
        if p.must_have_course_map:
            for code, window in p.must_have_course_map.items():
                must_have_map[code] = construct_course(code, self.major_name, window)
        try:
            self.cp.rebuild(window_start_term=self.window_start_term, must_have_course_map=must_have_map)
            after = snapshot_path(self.cp)
            return ExecuteOpResult(ok=True, diff=compute_diff(before, after), warnings=[], error=None, requires_reschedule=False, new_version=None)
        except Exception as e:
            # Revert to original path
            self.cp = before
            return ExecuteOpResult(ok=False, diff={}, warnings=[], error={"code": "REBUILD_FAIL", "details": str(e)}, requires_reschedule=False, new_version=None)
        
    def execute(self, op_type: ExtractedOpType, op: Op) -> ExecuteOpResult:
        print(f"EXECUTING OPERATION: {op}")

        type = op_type.type

        if type == "REMOVE":
            return self.remove(op)
        elif type == "ADD":
            return self.add(op)
        elif type == "MOVE":
            return self.move(op)
        elif type == "REPLACE":
            return self.replace(op)
        elif type == "SWAP":
            return self.swap(op)
        elif type == "REBUILD":
            return self.rebuild(op)
        else:
            raise Exception(f"Unknown operation type: {type}")
