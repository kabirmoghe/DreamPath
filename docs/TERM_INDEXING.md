# Term Indexing in DreamPath

This document maps out how term indices flow through the DreamPath system, from user input to storage and display.

## Current State: 0-Based Internally, +1 for Display Only

| Layer | Indexing | Notes |
|-------|----------|-------|
| **Backend Core** | 0-based (0-11) | Arrays, Course.term_idx |
| **Database** | 0-based | Serialized as-is |
| **LLM/Agent** | Pass-through | Uses whatever values are given |
| **Frontend Display** | +1 adjustment | `Term {idx + 1}` in render |
| **Operation Metadata** | +1 adjustment | `frontend_message_helpers.py` converts for display |

**Key clarification:** The LLM nodes and coursepath agent are NOT inherently 1-based — they simply pass through whatever values are provided. The only 1-based transformation happens in `frontend_message_helpers.py` when creating operation metadata for display.

## Dual Source of Truth

The `CoursePath` dataclass maintains two representations of scheduled courses:

### 1. `course_path: List[List[str]]` (Nested List)
```python
# course_path.py:19
course_path: List[List[str]]

# Access pattern
course_path[0] = ["COSC1", "MATH1"]  # Term 1 courses
course_path[1] = ["COSC10", "ECON1"] # Term 2 courses
```

**Purpose:** Amortized O(1) access for term-by-term operations. When you need "all courses in term X", you just do `course_path[X]`.

### 2. `course_bank: Dict[str, Course]` (Course Objects)
```python
# course_path.py:21
course_bank: Dict[str, Course]

# course.py:28
@dataclass
class Course:
    term_idx: Optional[int] = None      # Which term (0-based)
    term_idx_in_term: Optional[int] = None  # Position within term
    scheduled: bool = False
```

**Purpose:** Rich course metadata, prerequisite trees, scheduling flags.

### Synchronization

Both are updated together in operations like `add_course()`:

```python
# course_path.py:478-486
course_to_add.term_idx = new_course_term_idx  # Update Course object
self.course_path = add_course_path             # Update nested list
self.course_bank = self.course_bank | {course_to_add.course_code: course_to_add}
```

### Consistency Check

The `_produce_mock_course_path()` method can reconstruct the list from `course_bank`:

```python
# course_path.py:75-81
def _produce_mock_course_path(self):
    mock_course_path = [[] for _ in range(len(self.course_path))]
    for course_code, course_obj in self.course_bank.items():
        if course_obj.term_idx is not None and course_obj.scheduled:
            mock_course_path[course_obj.term_idx].append(course_code)
    return mock_course_path
```

And `visualize_by_term_idx()` calculates drift between the two sources.

## Refactoring Consideration: Dict vs List

### Current (0-based List)
```python
course_path: List[List[str]]  # course_path[0] = Term 1

# Iteration
for term_idx, courses in enumerate(course_path):
    print(f"Term {term_idx + 1}: {courses}")  # +1 for display

# Access
term_5_courses = course_path[4]  # 0-based index
```

### Proposed (1-based Dict)
```python
course_path: Dict[int, List[str]]  # course_path[1] = Term 1

# Initialization
course_path = {i: [] for i in range(1, 13)}  # Keys 1-12

# Iteration
for term_idx in range(1, 13):
    print(f"Term {term_idx}: {course_path[term_idx]}")  # No +1 needed

# Access
term_5_courses = course_path[5]  # Natural indexing
```

### Trade-offs

| Aspect | 0-based List | 1-based Dict |
|--------|--------------|--------------|
| **Pythonic** | Yes | Less conventional |
| **Display logic** | Needs +1 everywhere | Natural |
| **`enumerate()`** | Works naturally | Doesn't apply |
| **Slicing** | `course_path[3:6]` | Manual loop |
| **Length** | `len(course_path)` | `len(course_path)` |
| **Iteration** | `for idx, courses in enumerate(cp)` | `for idx in range(1, 13)` |
| **Course.term_idx** | Must also change to 1-based | Must also change |
| **Validation bounds** | `0 <= idx < 12` | `1 <= idx <= 12` |

### Migration Scope (if using 1-based Dict)

**Core files requiring changes:**

1. **`schedule_modules/course_path.py`**
   - Change `List[List[str]]` to `Dict[int, List[str]]`
   - Update all `range(len(course_path))` → `range(1, 13)`
   - Update all `course_path[idx]` access
   - Update `_produce_mock_course_path()`
   - Lines: 19, 77, 91, 106, 144, 165, 419, 427, etc.

2. **`schedule_modules/course.py`**
   - `term_idx` semantics change (1-12 instead of 0-11)
   - Line: 28

3. **`scheduling_helpers.py`**
   - `schedule_courses_by_term()` returns dict instead of list
   - All `range(max_terms)` → `range(1, max_terms + 1)`
   - Lines: 28, 81, 126, 195, 218, 280, 289

4. **`build_major_course_path.py`**
   - Update schedule building
   - Line: 42

5. **`database/serializers.py`**
   - Update serialization/deserialization
   - Consider migration for existing data
   - Lines: 19, 37, 70, 73

6. **`frontend_message_helpers.py`**
   - Remove all `+ 1` conversions
   - Lines: 41, 49, 60, 68, 83-84, 96-97, 188, 195, 204-205

7. **`frontend/src/components/Courses.jsx`**
   - Remove all `+ 1` in display
   - Lines: 172, 233-239, 267, 350

## Current +1 Conversion Locations

These are the places where 0-based indices are converted to 1-based for user display:

### Backend (`frontend_message_helpers.py`)
```python
# Lines 41, 49, 60, 68 - additions/removals
'term': change['term_idx'] + 1

# Lines 83-84, 96-97 - moves
'from_term': from_term + 1,
'to_term': to_term + 1
```

### Frontend (`Courses.jsx`)
```jsx
// Line 172
<h5>Term {termIndex + 1}</h5>

// Line 267
<p>Term {courseDetails.term_idx + 1}</p>

// Lines 233-239 (must_have_window)
const startTerm = Math.min(...window) + 1;
const endTerm = Math.max(...window) + 1;

// Line 350
Scheduled: Term {course.term_idx + 1}
```

### Frontend (`CoursePathOperations.jsx`)
```jsx
// Lines 78, 80, 82 - displays as-is
// (already 1-based from frontend_message_helpers.py conversion)
return `${op.course_code} → Term ${op.term}`
```

## Recommendation

### Why 1-Based Throughout Makes Sense for Agentic Systems

The agent isn't just a display layer — it's a **conversational layer** that constantly bridges user language and internal state:

```
User: "Add COSC50 to term 5"
     ↓
Agent processes (internally)
     ↓
Agent: "Added COSC50 to term 5"
```

**With 0-based internal:**
- Agent receives "term 5" from user
- Must convert to index 4 for operations
- Must convert back to "term 5" for response
- Prompts need to explain this conversion
- Easy to forget conversion → bugs

**With 1-based internal:**
- Agent receives "term 5" from user
- Uses 5 directly
- Responds with 5
- No conversion logic needed
- No prompt overhead explaining indexing

### Decision: Refactor to 1-Based Dict

The overhead of having the agent correctly format term numbers (and explaining indexing in prompts) outweighs the Pythonic benefits of 0-based lists.

**Recommended approach:** `Dict[int, List[str]]` with keys 1-12

```python
# New structure
course_path: Dict[int, List[str]] = {i: [] for i in range(1, 13)}

# Natural access
term_5_courses = course_path[5]  # No mental math

# Natural iteration
for term in range(1, 13):
    courses = course_path[term]
```

### Migration Checklist

When ready to implement:

- [ ] `schedule_modules/course_path.py` - Change type, update all access patterns
- [ ] `schedule_modules/course.py` - `term_idx` now 1-12
- [ ] `scheduling_helpers.py` - Update all range() calls
- [ ] `build_major_course_path.py` - Update schedule building
- [ ] `database/serializers.py` - Update serialization
- [ ] `frontend_message_helpers.py` - Remove +1 conversions
- [ ] `frontend/src/components/Courses.jsx` - Remove +1 in display
- [ ] Existing database records - Migration script to +1 all term_idx values

### Helper Functions (If Keeping 0-Based)

If for some reason 0-based must be kept, use explicit converters:

```python
def to_display_term(internal_idx: int) -> int:
    """Convert 0-based internal index to 1-based display term."""
    return internal_idx + 1

def to_internal_idx(display_term: int) -> int:
    """Convert 1-based display term to 0-based internal index."""
    return display_term - 1
```

But this adds complexity that 1-based throughout would eliminate.
