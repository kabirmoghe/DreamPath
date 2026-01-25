"""DSPy query generation module for course search parameter extraction.

This module converts atomic search descriptions into optimized CourseSearchParams
for Weaviate hybrid search.

Note: Input field is named "task_description" for compatibility with DSPy training
dataset, but semantically represents an atomic search description.
"""

import sys
from pathlib import Path

import dspy

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from dreampath_processing.dreampath_agent.search_agent.search_types import (
    CourseSearchParams,
    ValidDepartment,
    ValidDifficulty,
    ValidValue,
)

# ============================================================================
# DSPy Signature
# ============================================================================

class CourseSearchSignature(dspy.Signature):
    """Extract optimal course search parameters from an atomic search description.

    CRITICAL CONTEXT:
    - Input: ATOMIC search description (already decomposed by task tracking upstream)
    - Your job: Convert atomic description → search parameters (NOT decompose/infer/plan)
    - Output: 9 search parameters for Weaviate hybrid search

    PARAMETER CONSTRAINTS:

    query (str): Semantic search string
      - Searches: description, difficulty_blurb, learning_value_blurb, target_audience_blurb
      - Use empty string "" for course code lookups (not semantic search)
      - Expand topics with related terms for better recall

    alpha (float): Hybrid search weight, range 0.0-1.0
      - 0.0 = pure keyword matching (BM25)
      - 1.0 = pure semantic/vector search
      - Balance based on query specificity vs. conceptual nature

    department (ValidDepartment or None): Department filter
      - Map abbreviations to full names (CS → Computer Science)
      - None for cross-departmental or when unclear

    course_code (str or None): Specific course code
      - Set when task mentions specific course (e.g., "COSC74")
      - None for general searches

    max_num_prereqs (int or None): Maximum prerequisite count
      - None if not mentioned in task

    difficulty_classification (ValidDifficulty or None): Difficulty level
      - None if not specified in task

    value_classification (ValidValue or None): Learning value/quality level
      - Set based on quality signals (highly-rated, interesting, etc.)
      - None if no quality emphasis in task

    sort_by_level (bool): Sort by course level number
      - True for "advanced"/"upper-level" queries
      - False otherwise (default)

    limit (int): Maximum number of results
      - Typically 1 for specific lookups, 5-10 for searches
    """

    task_description: str = dspy.InputField(
        desc="Atomic search description (already decomposed by task tracking)"
    )

    # Output fields (9 parameters)
    query: str = dspy.OutputField(
        desc="Semantic search query with expanded terms (empty string for course code lookups)"
    )
    alpha: float = dspy.OutputField(
        desc="Hybrid search weight 0-1 (0.3=exact, 0.5-0.6=hybrid, 0.7+=semantic)"
    )
    department: ValidDepartment | None = dspy.OutputField(
        desc="Department name or None for cross-departmental",
        default=None
    )
    course_code: str | None = dspy.OutputField(
        desc="Specific course code (e.g., 'COSC74') or None",
        default=None
    )
    max_num_prereqs: int | None = dspy.OutputField(
        desc="Maximum prerequisites or None",
        default=None
    )
    difficulty_classification: ValidDifficulty | None = dspy.OutputField(
        desc="Difficulty level or None",
        default=None
    )
    value_classification: ValidValue | None = dspy.OutputField(
        desc="Value level (set only with explicit quality signals) or None",
        default=None
    )
    sort_by_level: bool = dspy.OutputField(
        desc="Sort by course level number",
        default=False
    )
    limit: int = dspy.OutputField(
        desc="Max results",
        default=10
    )


# ============================================================================
# DSPy Module
# ============================================================================

class CourseQueryGenerator(dspy.Module):
    """DSPy module for generating course search parameters from atomic search descriptions.

    This module will be optimized to learn the best prompt for
    extracting search parameters from atomic search descriptions.
    """

    def __init__(self):
        super().__init__()
        self.generate_params = dspy.ChainOfThought(CourseSearchSignature)

    def forward(self, task_description: str):
        """Generate CourseSearchParams from atomic search description

        Note: Parameter is named task_description for compatibility with DSPy dataset,
        but semantically represents a search description.
        """
        result = self.generate_params(task_description=task_description)

        # Return structured output
        return dspy.Prediction(
            query=result.query,
            alpha=result.alpha,
            department=result.department,
            course_code=result.course_code,
            max_num_prereqs=result.max_num_prereqs,
            difficulty_classification=result.difficulty_classification,
            value_classification=result.value_classification,
            sort_by_level=result.sort_by_level,
            limit=result.limit
        )


# ============================================================================
# Conversion Utilities
# ============================================================================

def dspy_prediction_to_params(prediction: dspy.Prediction):
    """Convert DSPy prediction to CourseSearchParams Pydantic model

    Strips surrounding quotes from string fields that LLMs sometimes add.
    """
    def clean_string(s):
        """Remove surrounding quotes and handle None/empty string representations

        DSPy quirk: Optional[str] fields return string "None" instead of actual None.
        This function normalizes those cases.
        """
        if s is None:
            return None

        s = str(s).strip()

        # Convert string "None" to actual None (DSPy quirk for Optional[str])
        if s in ['None', 'none', 'null', 'NULL']:
            return None

        # Handle empty string with quotes: '""' or "''"
        if s in ['""', "''"]:
            return ""

        # Strip surrounding quotes
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
            # After stripping, check again for None
            if s in ['None', 'none', 'null', 'NULL']:
                return None

        # Convert empty string to None for optional fields
        return s if s else None

    return CourseSearchParams(
        query=clean_string(prediction.query) or "",
        alpha=float(prediction.alpha) if prediction.alpha is not None else 0.5,
        department=clean_string(prediction.department),
        course_code=clean_string(prediction.course_code),
        max_num_prereqs=int(prediction.max_num_prereqs) if prediction.max_num_prereqs is not None else None,
        difficulty_classification=clean_string(prediction.difficulty_classification),
        value_classification=clean_string(prediction.value_classification),
        sort_by_level=bool(prediction.sort_by_level) if prediction.sort_by_level is not None else False,
        limit=int(prediction.limit) if prediction.limit is not None else 10
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    import os

    # Configure DSPy with LLM (v3.0+ syntax)
    if os.getenv("OPENAI_API_KEY"):
        lm = dspy.LM("openai/gpt-4o-mini", max_tokens=500, api_key=os.getenv("OPENAI_API_KEY"))
        dspy.configure(lm=lm)

        # Create module
        generator = CourseQueryGenerator()

        # Test with a few examples
        test_tasks = [
            "Find easy introductory history courses",
            "Tell me about COSC74",
            "Find courses on transformer architecture",
            "Find highly-rated humanities courses",
        ]

        print("=" * 60)
        print("TESTING COURSE QUERY GENERATOR (Pre-Optimization)")
        print("=" * 60)

        for task in test_tasks:
            print(f"\nTask: {task}")
            prediction = generator(task_description=task)

            print(f"  query: '{prediction.query}'")
            print(f"  alpha: {prediction.alpha}")
            print(f"  department: {prediction.department}")
            print(f"  course_code: {prediction.course_code}")
            print(f"  difficulty: {prediction.difficulty_classification}")
            print(f"  value: {prediction.value_classification}")
            print(f"  sort_by_level: {prediction.sort_by_level}")
            print(f"  limit: {prediction.limit}")
    else:
        print("Set OPENAI_API_KEY to test the module")
