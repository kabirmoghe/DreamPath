from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, List, Any
from dreampath_processing.courses.schedule_modules.course_path import CoursePath

# Operation Types
class OpBase(BaseModel):
    reschedule: bool = False

class RemoveOp(OpBase):
    course_code: str

    def __str__(self) -> str:
        return f"REMOVE '{self.course_code}'"

class AddOp(OpBase):
    course_code: Optional[str] = None
    add_to_term: Optional[int] = None
    must_have_window: Optional[List[int]] = Field(
        default=None, min_length=2, max_length=2
    )

    def __str__(self) -> str:
        return f"ADD '{self.course_code}'{f' to term {self.add_to_term}' if self.add_to_term and not self.must_have_window else ''}{f' between terms {self.must_have_window}' if self.must_have_window else ''}"

class MoveOp(OpBase):
    course_code: Optional[str] = None
    move_to_term: Optional[int] = None
    move_window: Optional[List[int]] = Field(
        default=None, min_length=2, max_length=2
    )

    def __str__(self) -> str:
        return f"MOVE '{self.course_code}' {'to term ' + str(self.move_to_term) if self.move_to_term and not self.move_window else ''}{f' between terms {self.move_window}' if self.move_window else ''}"

class ReplaceOp(OpBase):
    old_course_code: Optional[str] = None
    new_course_code: Optional[str] = None
    must_have_window: Optional[List[int]] = Field(
        default=None, min_length=2, max_length=2
    )

    def __str__(self) -> str:
        return f"REPLACE '{self.old_course_code}' with '{self.new_course_code}'{f' between terms {self.must_have_window}' if self.must_have_window else ''}"

class SwapOp(OpBase):
    course_code_1: Optional[str] = None
    course_code_2: Optional[str] = None

    def __str__(self) -> str:
        return f"SWAP '{self.course_code_1}' with '{self.course_code_2}'"

class RebuildOp(OpBase):
    must_have_course_map: Optional[Dict[str, List[int]]] = Field(default_factory=dict)

    def __str__(self) -> str:
        base = "REBUILD"
        if self.must_have_course_map:
            base += ":"
            for course_code, window in self.must_have_course_map.items():
                base += f"\n | '{course_code}' -> {window}"
        return base

# Operation Extraction
class ExtractedOpType(BaseModel):
    type: Literal["REMOVE", "ADD", "MOVE", "REPLACE", "SWAP", "REBUILD"]

Op = RemoveOp | AddOp | MoveOp | ReplaceOp | SwapOp | RebuildOp

# Operation Execution
class ExecuteOpResult(BaseModel):
    ok: bool
    diff: Dict = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[Dict] = None
    requires_reschedule: bool = False
    new_version: Optional[int] = None

# Agent Output
class CoursePathAgentOutput(BaseModel):
    status: Literal["ask", "confirm", "execute", "error", "cancel"]
    ui_text: str
    diff: Optional[Dict[str, Any]] = None
    error: Optional[Dict] = None

# Agent State
class CoursePathAgentState(BaseModel):
    # CP maintenance
    thread_id: str
    plan_id: str
    plan_version: int

    # Operation execution
    pending_op_type: Optional[ExtractedOpType] = None
    pending_op: Optional[Op] = None
    trial_op_execution: Optional[ExecuteOpResult] = None
    missing_fields: List[str] = Field(default_factory=list)
    facts: Dict[str, str | int | List[str]] = Field(default_factory=dict)

    # Conversation state
    summary: str = Field(default="")
    recent_messages: List[Dict] = Field(default_factory=list)

# Operation Info
OP_INFO = {
    "REMOVE": {'extraction_model': RemoveOp, 
               'required_fields': ['course_code'],
               'alternative_fields': []},
    "ADD": {'extraction_model': AddOp, 
            'required_fields': ['course_code'],
            'alternative_fields': []},
    "MOVE": {'extraction_model': MoveOp, 
             'required_fields': ['course_code'],
             'alternative_fields': ['move_to_term', 'move_window']},
    "REPLACE": {'extraction_model': ReplaceOp, 
                'required_fields': ['old_course_code', 'new_course_code'],
                'alternative_fields': []},
    "SWAP": {'extraction_model': SwapOp, 
             'required_fields': ['course_code_1', 'course_code_2'],
             'alternative_fields': []},
    "REBUILD": {'extraction_model': RebuildOp, 
                'required_fields': ['must_have_course_map'],
                'alternative_fields': []}
}