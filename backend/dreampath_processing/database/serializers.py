from dreampath_processing.courses.schedule_modules.course_path import CoursePath
from dreampath_processing.courses.course_relationship_handling import PrereqGraph
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentState, ExtractedOpType, Op, OP_INFO, ExecuteOpResult
from dreampath_processing.courses.schedule_modules.course import Course, CourseType
# ------------------------------
#  Serialization 
# ------------------------------
def serialize_course_bank(course_bank: dict) -> dict:
    """Serialize course bank (Dict[str, Course]) to JSON-compatible dict."""
    serialized = {}
    for course_code, course in course_bank.items():
        serialized[course_code] = {
            "course_code": course.course_code,
            "course_type": course.course_type.value,  # Convert enum to string
            "is_prereq": course.is_prereq,
            "scheduled": course.scheduled,
            "prereq_tree": course.prereq_tree,  # dict - already JSON serializable
            "must_have_window": course.must_have_window,  # List[int] or None - already JSON serializable
            "term_idx": course.term_idx,  # int or None - already JSON serializable
            "term_idx_in_term": course.term_idx_in_term,  # int or None - already JSON serializable
            "course_title": course.course_title,  # str or None - already JSON serializable
            "course_description": course.course_description,  # str or None - already JSON serializable
        }
    return serialized

def serialize_prereq_graph(prereq_graph: PrereqGraph) -> dict:
    """Serialize PrereqGraph to JSON-compatible dict."""
    return {
        "children": {k: list(v) for k, v in prereq_graph.children.items()},  # Convert sets to lists
        "parents": {k: list(v) for k, v in prereq_graph.parents.items()},  # Convert sets to lists
        "all_courses": list(prereq_graph.all_courses),  # Convert set to list
    }

def serialize_course_path(course_path: CoursePath) -> dict:
    """Serialize CoursePath to JSON-compatible dict."""
    return {
        "course_path": course_path.course_path,  # List[List[str]] - already JSON serializable
        "recommended_courses": list(course_path.recommended_courses),  # Convert set to list
        "course_bank": serialize_course_bank(course_path.course_bank),  # Custom serialization
        "prereq_graph": serialize_prereq_graph(course_path.prereq_graph),  # Custom serialization
        "curr_window_start": course_path.curr_window_start,  # int - already JSON serializable
        "must_have_courses": list(course_path.must_have_courses),  # Convert set to list
        "lingering_courses": list(course_path.lingering_courses),  # Convert set to list
    }

def serialize_course_path_agent_state(state: CoursePathAgentState) -> dict:
    """Serialize CoursePathAgentState to JSON-compatible dict."""
    return {
        "pending_op_type": state.pending_op_type.type if state.pending_op_type else None,
        "pending_op_data": state.pending_op.model_dump() if state.pending_op else None,
        "trial_op_execution": state.trial_op_execution.model_dump() if state.trial_op_execution else None,
        "missing_fields": state.missing_fields,
        "facts": state.facts,
        "history": state.history,
        "recent_messages": state.recent_messages,
    }

# ------------------------------
#  Deserialization
# ------------------------------
def deserialize_course_bank(data: dict) -> dict:
    """Deserialize course bank from JSON dict."""
    
    course_bank = {}
    for course_code, course_data in data.items():
        course_bank[course_code] = Course(
            course_code=course_data["course_code"],
            course_type=CourseType(course_data["course_type"]),  # Convert string back to enum
            is_prereq=course_data["is_prereq"],
            scheduled=course_data["scheduled"],
            prereq_tree=course_data["prereq_tree"],
            must_have_window=course_data["must_have_window"],
            term_idx=course_data["term_idx"],
            term_idx_in_term=course_data["term_idx_in_term"],
            course_title=course_data["course_title"],
            course_description=course_data["course_description"],
        )
    return course_bank

def deserialize_prereq_graph(data: dict) -> PrereqGraph:
    """Deserialize PrereqGraph from JSON dict."""
    
    return PrereqGraph(
        children={k: set(v) for k, v in data["children"].items()},  # Convert lists back to sets
        parents={k: set(v) for k, v in data["parents"].items()},  # Convert lists back to sets
        all_courses=set(data["all_courses"]),  # Convert list back to set
    )

def deserialize_course_path(data: dict) -> CoursePath:
    """Deserialize CoursePath from JSON dict."""
    
    return CoursePath(
        course_path=data["course_path"],
        recommended_courses=set(data["recommended_courses"]),  # Convert list back to set
        course_bank=deserialize_course_bank(data["course_bank"]),  # Custom deserialization
        prereq_graph=deserialize_prereq_graph(data["prereq_graph"]),  # Custom deserialization
        curr_window_start=data["curr_window_start"],
        must_have_courses=set(data["must_have_courses"]),  # Convert list back to set
        lingering_courses=set(data["lingering_courses"]),  # Convert list back to set
    )

def deserialize_course_path_agent_state(data: dict) -> CoursePathAgentState:
    """Deserialize CoursePathAgentState from JSON dict."""
    pending_op_type = None
    if data.get("pending_op_type"):
        pending_op_type = ExtractedOpType(type=data["pending_op_type"])

    pending_op = None
    if data.get("pending_op_data") and pending_op_type:
        extraction_model: Op = OP_INFO[pending_op_type.type]['extraction_model']
        pending_op = extraction_model(**data["pending_op_data"])

    trial_op_execution = None
    if data.get("trial_op_execution"):
        trial_op_execution = ExecuteOpResult(**data["trial_op_execution"])

    return CoursePathAgentState(
        pending_op_type=pending_op_type,
        pending_op=pending_op,
        trial_op_execution=trial_op_execution,
        missing_fields=data.get("missing_fields", []),
        facts=data.get("facts", {}),
        history=data.get("history", ""),
        recent_messages=data.get("recent_messages", [])
    )