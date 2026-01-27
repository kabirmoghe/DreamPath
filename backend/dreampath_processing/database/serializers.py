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
            # Required
            "course_code": course.course_code,
            "course_type": course.course_type.value,  # Convert enum to string
            # Scheduling state
            "is_prereq": course.is_prereq,
            "scheduled": course.scheduled,
            "prereq_tree": course.prereq_tree,
            "must_have_window": course.must_have_window,
            "term_idx": course.term_idx,
            "term_idx_in_term": course.term_idx_in_term,
            # DreamPath-specific
            "aligned_parameters": list(course.aligned_parameters) if course.aligned_parameters else None,
            # Basic course info
            "course_title": course.course_title,
            "course_description": course.course_description,
            "department": course.department,
            "prerequisites": course.prerequisites,
            "course_url": course.course_url,
            "num_prereqs": course.num_prereqs,
            "total_reviews": course.total_reviews,
            # Difficulty metrics
            "global_difficulty_percentile": course.global_difficulty_percentile,
            "global_difficulty_classification": course.global_difficulty_classification,
            "dept_difficulty_percentile": course.dept_difficulty_percentile,
            "dept_difficulty_classification": course.dept_difficulty_classification,
            "difficulty_blurb": course.difficulty_blurb,
            # Value metrics
            "global_value_percentile": course.global_value_percentile,
            "global_value_classification": course.global_value_classification,
            "dept_value_percentile": course.dept_value_percentile,
            "dept_value_classification": course.dept_value_classification,
            "learning_value_blurb": course.learning_value_blurb,
            # Target audience
            "target_audience_blurb": course.target_audience_blurb,
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
        # Handle aligned_parameters: convert list back to set
        aligned = course_data.get("aligned_parameters")
        aligned_set = set(aligned) if aligned else None

        course_bank[course_code] = Course(
            # Required
            course_code=course_data["course_code"],
            course_type=CourseType(course_data["course_type"]),
            # Scheduling state
            is_prereq=course_data.get("is_prereq", False),
            scheduled=course_data.get("scheduled", False),
            prereq_tree=course_data.get("prereq_tree"),
            must_have_window=course_data.get("must_have_window"),
            term_idx=course_data.get("term_idx"),
            term_idx_in_term=course_data.get("term_idx_in_term"),
            # DreamPath-specific
            aligned_parameters=aligned_set,
            # Basic course info
            course_title=course_data.get("course_title"),
            course_description=course_data.get("course_description"),
            department=course_data.get("department"),
            prerequisites=course_data.get("prerequisites"),
            course_url=course_data.get("course_url"),
            num_prereqs=course_data.get("num_prereqs"),
            total_reviews=course_data.get("total_reviews"),
            # Difficulty metrics
            global_difficulty_percentile=course_data.get("global_difficulty_percentile"),
            global_difficulty_classification=course_data.get("global_difficulty_classification"),
            dept_difficulty_percentile=course_data.get("dept_difficulty_percentile"),
            dept_difficulty_classification=course_data.get("dept_difficulty_classification"),
            difficulty_blurb=course_data.get("difficulty_blurb"),
            # Value metrics
            global_value_percentile=course_data.get("global_value_percentile"),
            global_value_classification=course_data.get("global_value_classification"),
            dept_value_percentile=course_data.get("dept_value_percentile"),
            dept_value_classification=course_data.get("dept_value_classification"),
            learning_value_blurb=course_data.get("learning_value_blurb"),
            # Target audience
            target_audience_blurb=course_data.get("target_audience_blurb"),
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