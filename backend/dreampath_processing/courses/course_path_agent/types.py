from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Tuple, List
from dreampath_processing.courses.schedule_modules.course_path import CoursePath
from dreampath_processing.courses.schedule_modules.course import Course

# Operation Types
class OpBase(BaseModel):
    reschedule: bool = False

class RemoveOp(OpBase):
    course_code: str

    def __str__(self) -> str:
        return f"REMOVE '{self.course_code}'"

class AddOp(OpBase):
    course_code: str
    to_term: Optional[int] = Field(default=None)
    must_have_window: Optional[List[int]] = Field(
        default=None, min_length=2, max_length=2
    )

    def __str__(self) -> str:
        return f"ADD '{self.course_code}'{f' between terms {self.must_have_window}' if self.must_have_window else ''}"

class MoveOp(OpBase):
    course_code: str
    to_term: int
    move_window: Optional[List[int]] = Field(
        default=None, min_length=2, max_length=2
    )

    def __str__(self) -> str:
        return f"MOVE '{self.course_code}' to term {self.to_term}{f' between terms {self.move_window}' if self.move_window else ''}"

class ReplaceOp(OpBase):
    old_course_code: str
    new_course_code: str
    must_have_window: Optional[List[int]] = Field(
        default=None, min_length=2, max_length=2
    )

    def __str__(self) -> str:
        return f"REPLACE '{self.old_course_code}' with '{self.new_course_code}'{f' between terms {self.must_have_window}' if self.must_have_window else ''}"

class SwapOp(OpBase):
    course_code_1: str
    course_code_2: str

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

class BaseExtractedOp(BaseModel):
    op: Optional[Op] = None
    missing: List[str] = Field(default_factory=list) 
    questions: List[str] = Field(default_factory=list)
    inferred: List[str] = Field(default_factory=list)

class RemoveExtractedOp(BaseExtractedOp):
    op: RemoveOp

class AddExtractedOp(BaseExtractedOp):
    op: AddOp

class MoveExtractedOp(BaseExtractedOp):
    op: MoveOp

class ReplaceExtractedOp(BaseExtractedOp):
    op: ReplaceOp

class SwapExtractedOp(BaseExtractedOp):
    op: SwapOp

class RebuildExtractedOp(BaseExtractedOp):
    op: RebuildOp

# Operation Execution
class ExecuteOpResult(BaseModel):
    ok: bool
    diff: Dict = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[Dict] = None
    requires_reschedule: bool = False
    new_version: Optional[int] = None

# Agent State
class CoursePathAgentState(BaseModel):
    thread_id: str
    plan_id: str
    plan_version: int
    pending_op_type: Optional[ExtractedOpType] = None
    pending_op: Optional[Op] = None
    facts: Dict[str, str | int | List[str]] = Field(default_factory=dict)
    summary: str = Field(default="")
    recent_messages: List[Dict] = Field(default_factory=list)