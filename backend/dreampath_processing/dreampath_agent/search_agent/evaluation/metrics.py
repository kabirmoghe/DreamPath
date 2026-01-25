"""Evaluation metrics for DSPy query generation module.

Implements two-tier hybrid scoring:
- Programmatic metrics (70%): Fast, objective, deterministic
- LLM judge (30%): Nuanced semantic evaluation with feedback
"""

import os

if 'TOKENIZERS_PARALLELISM' not in os.environ:
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from typing import Any

from dreampath_processing.dreampath_agent.search_agent.search_types import CourseSearchParams
from evaluation.golden_examples import GoldenExample
from pydantic import BaseModel, Field

# ============================================================================
# LLM Judge Structured Output
# ============================================================================

class LLMJudgeEvaluation(BaseModel):
    """Structured output from LLM judge evaluation"""

    intent_captured: float = Field(description="How well the parameters capture user intent (0-1)")
    parameter_appropriateness: float = Field(description="How appropriate the parameter choices are (0-1)")
    semantic_quality: float = Field(description="Quality of semantic query for finding relevant courses (0-1)")
    overall_score: float = Field(description="Overall quality score (0-1)")

    # Critical for GEPA optimization
    feedback: str = Field(description="What's good/bad about this parameter extraction")
    improvement_suggestions: str = Field(description="Specific ways to improve the extraction")


# ============================================================================
# Programmatic Metrics
# ============================================================================

def exact_match_score(predicted: Any, expected: Any) -> float:
    """Binary exact match

    When expected is None, predicted should also be None.
    Setting a parameter when None is expected is incorrect (adds unnecessary filter).
    """
    return 1.0 if predicted == expected else 0.0


def alpha_score(predicted: float, expected: float) -> float:
    """Partial credit for alpha within 0.2 range"""
    if abs(predicted - expected) <= 0.2:
        return 1.0
    # Linear decay: max penalty at 0.4 difference
    return max(0.0, 1.0 - abs(predicted - expected) / 0.4)


def query_overlap_score(predicted: str, expected: str, use_semantic: bool = True) -> float:
    """Hybrid keyword + semantic similarity for query comparison

    Args:
        predicted: Predicted query string
        expected: Expected query string
        use_semantic: If True, blend keyword overlap with semantic similarity (default: True)

    Returns:
        Score 0-1 combining keyword and semantic similarity
    """
    if not expected or expected == "":
        # If expected query is empty (course code lookup), check if predicted is also minimal
        return 1.0 if (not predicted or predicted == "" or len(predicted.split()) <= 2) else 0.5

    if not predicted or predicted == "":
        return 0.0  # Expected non-empty but got empty

    # Keyword-based score (Jaccard with recall emphasis)
    expected_keywords = set(expected.lower().split())
    predicted_keywords = set(predicted.lower().split())

    if not expected_keywords:
        return 1.0

    intersection = len(expected_keywords & predicted_keywords)
    recall = intersection / len(expected_keywords)
    precision = intersection / len(predicted_keywords) if predicted_keywords else 0.0
    keyword_score = 0.7 * recall + 0.3 * precision

    if not use_semantic:
        return keyword_score

    # Semantic similarity using sentence embeddings
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        # Use cached model (loaded once per process)
        if not hasattr(query_overlap_score, '_model'):
            query_overlap_score._model = SentenceTransformer('all-MiniLM-L6-v2')

        model = query_overlap_score._model

        # Compute embeddings
        embeddings = model.encode([expected, predicted])
        expected_emb = embeddings[0]
        predicted_emb = embeddings[1]

        # Cosine similarity
        cosine_sim = float(np.dot(expected_emb, predicted_emb) /
                          (np.linalg.norm(expected_emb) * np.linalg.norm(predicted_emb)))

        # Blend keyword and semantic: 40% keyword, 60% semantic
        # Keyword catches exact term matches, semantic catches paraphrases
        blended_score = 0.4 * keyword_score + 0.6 * cosine_sim

        return blended_score

    except ImportError:
        # Fallback to keyword-only if sentence-transformers not available
        return keyword_score


def parameter_completeness_score(predicted: CourseSearchParams, expected: CourseSearchParams) -> float:
    """Check if appropriate optional fields are set"""
    score = 0.0
    total_checks = 0

    # Check department
    total_checks += 1
    if expected.department is not None:
        score += 1.0 if predicted.department is not None else 0.0
    else:
        score += 1.0  # Correctly left as None

    # Check difficulty
    total_checks += 1
    if expected.difficulty_classification is not None:
        score += 1.0 if predicted.difficulty_classification is not None else 0.0
    else:
        score += 1.0  # Correctly left as None

    # Check value
    total_checks += 1
    if expected.value_classification is not None:
        score += 1.0 if predicted.value_classification is not None else 0.0
    else:
        score += 1.0  # Correctly left as None

    # Check prerequisites
    total_checks += 1
    if expected.max_num_prereqs is not None:
        score += 1.0 if predicted.max_num_prereqs is not None else 0.0
    else:
        score += 1.0  # Correctly left as None

    # Check course_code
    total_checks += 1
    if expected.course_code is not None:
        score += 1.0 if predicted.course_code is not None else 0.0
    else:
        score += 1.0  # Correctly left as None

    # Check sort_by_level
    total_checks += 1
    if expected.sort_by_level:
        score += 1.0 if predicted.sort_by_level else 0.0
    else:
        score += 1.0  # Correctly left as False

    return score / total_checks if total_checks > 0 else 1.0


def compute_programmatic_score(
    example: GoldenExample,
    prediction: CourseSearchParams
) -> dict[str, float]:
    """Compute all programmatic metrics and return breakdown + weighted score"""

    expected = example.expected_params

    # Individual metrics
    metrics = {
        'department_exact': exact_match_score(prediction.department, expected.department),
        'course_code_exact': exact_match_score(prediction.course_code, expected.course_code),
        'difficulty_exact': exact_match_score(prediction.difficulty_classification, expected.difficulty_classification),
        'value_exact': exact_match_score(prediction.value_classification, expected.value_classification),
        'prereqs_exact': exact_match_score(prediction.max_num_prereqs, expected.max_num_prereqs),
        'alpha_score': alpha_score(prediction.alpha, expected.alpha),
        'query_overlap': query_overlap_score(prediction.query, expected.query),
        'completeness': parameter_completeness_score(prediction, expected)
    }

    # Weighted combination
    weights = {
        'department_exact': 0.15,
        'course_code_exact': 0.10,
        'difficulty_exact': 0.15,
        'value_exact': 0.10,
        'prereqs_exact': 0.05,
        'alpha_score': 0.15,
        'query_overlap': 0.20,
        'completeness': 0.10
    }

    weighted_score = sum(metrics[key] * weights[key] for key in metrics)

    return {
        'metrics': metrics,
        'weighted_score': weighted_score
    }


# ============================================================================
# LLM Judge Evaluation
# ============================================================================

def llm_judge_score(
    example: GoldenExample,
    prediction: CourseSearchParams,
    llm: Any  # OpenAI client (from instructor)
) -> LLMJudgeEvaluation:
    """Use LLM to evaluate parameter extraction quality with structured feedback"""

    # Build evaluation prompt
    system_prompt = """You are an expert evaluator for course search parameter extraction.

Your job is to evaluate how well a DSPy module converted an atomic search task into CourseSearchParams.

IMPORTANT: For query evaluation, focus on SEMANTIC SIMILARITY, not exact keyword matching.
Paraphrases and synonyms are acceptable as long as they capture the same search intent.

Rate the extraction on three dimensions (0-1 scale):

1. **Intent Capture** (0-1):
   - 1.0: Perfectly captures what the user wants to find
   - 0.8: Captures main intent with good coverage
   - 0.6: Captures main intent, minor details missed
   - 0.4: Partially understands, significant gaps
   - 0.0: Misunderstands the user's goal

2. **Parameter Appropriateness** (0-1):
   - 1.0: All parameters set correctly and reasonably
   - 0.8: Most parameters excellent, 1 minor issue
   - 0.6: Most parameters good, 1-2 minor issues
   - 0.4: Several parameters wrong or missing
   - 0.0: Parameters don't match the task at all

3. **Semantic Query Quality** (0-1):
   - 1.0: Query captures exact concepts needed (semantically equivalent)
   - 0.8: Query captures main concepts with good paraphrasing
   - 0.6: Query is semantically similar, minor concepts missing/added
   - 0.4: Query partially related but misses key concepts
   - 0.0: Query unrelated to search intent

Provide specific, actionable feedback that helps improve the extraction."""

    user_prompt = f"""Evaluate this parameter extraction:

**Atomic Task:** "{example.search_description}"

**Task Intent:** {example.intent_description}

**Expected Parameters:**
{format_params(example.expected_params)}

**Predicted Parameters:**
{format_params(prediction)}

**Evaluation Notes from Golden Example:**
{example.evaluation_notes}

Please evaluate the predicted parameters against the expected parameters and provide:
1. Scores for intent_captured, parameter_appropriateness, semantic_quality (each 0-1)
2. Overall score (average of the three)
3. Specific feedback on what's good/bad
4. Concrete improvement suggestions"""

    # Call OpenAI with structured output (using instructor)
    result = llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_model=LLMJudgeEvaluation,
        temperature=0
    )

    return result


def format_params(params: CourseSearchParams) -> str:
    """Format CourseSearchParams for display"""
    lines = []
    lines.append(f"  - query: '{params.query}'")
    lines.append(f"  - alpha: {params.alpha}")
    lines.append(f"  - department: {params.department}")
    lines.append(f"  - course_code: {params.course_code}")
    lines.append(f"  - max_num_prereqs: {params.max_num_prereqs}")
    lines.append(f"  - difficulty_classification: {params.difficulty_classification}")
    lines.append(f"  - value_classification: {params.value_classification}")
    lines.append(f"  - sort_by_level: {params.sort_by_level}")
    lines.append(f"  - limit: {params.limit}")
    return "\n".join(lines)


# ============================================================================
# Combined Metric
# ============================================================================

def evaluate_query_generation(
    example,  # dspy.Example or GoldenExample
    prediction,  # dspy.Prediction or CourseSearchParams
    llm: Any | None = None,
    trace: dict[str, Any] | None = None
) -> float:
    """
    Combined metric for GEPA optimization and manual evaluation.

    Works with both DSPy types (for dspy.Evaluate/GEPA) and direct types (for testing).

    Args:
        example: dspy.Example (with expected_params) or GoldenExample
        prediction: dspy.Prediction (from CourseQueryGenerator) or CourseSearchParams
        llm: Optional LLM for judge evaluation
        trace: Optional dict to store detailed metrics

    Returns:
        Float score 0-1 (weighted combination of programmatic + LLM judge)
    """
    # Handle DSPy types vs direct types
    if hasattr(example, 'expected_params'):
        # DSPy Example - reconstruct GoldenExample for evaluation
        from dreampath_processing.dreampath_agent.search_agent.evaluation.golden_examples import (
            GoldenExample,
        )
        golden = GoldenExample(
            task_description=example.search_description,
            expected_params=example.expected_params,
            archetype=example.archetype,
            key_features=example.key_features,
            intent_description=example.intent_description,
            evaluation_notes=example.evaluation_notes
        )
    else:
        # Already a GoldenExample
        golden = example

    # Check if it's already a CourseSearchParams (not DSPy Prediction)
    from evaluation.types_lite import CourseSearchParams

    if isinstance(prediction, CourseSearchParams):
        # Already CourseSearchParams - no conversion needed
        prediction_params = prediction
    else:
        # DSPy Prediction - convert to CourseSearchParams (cleans quotes)
        from dreampath_processing.dreampath_agent.search_agent.query_generator_dspy import (
            dspy_prediction_to_params,
        )
        prediction_params = dspy_prediction_to_params(prediction)

    # Programmatic scoring (fast, objective)
    prog_result = compute_programmatic_score(golden, prediction_params)
    prog_score = prog_result['weighted_score']

    # LLM judge scoring (nuanced, feedback-rich)
    if llm is not None:
        llm_eval = llm_judge_score(golden, prediction_params, llm)
        llm_score = llm_eval.overall_score

        # Store feedback for GEPA
        if trace is not None:
            trace['llm_feedback'] = llm_eval.feedback
            trace['improvement_suggestions'] = llm_eval.improvement_suggestions
            trace['llm_scores'] = {
                'intent_captured': llm_eval.intent_captured,
                'parameter_appropriateness': llm_eval.parameter_appropriateness,
                'semantic_quality': llm_eval.semantic_quality
            }
    else:
        # If no LLM provided, use only programmatic score
        llm_score = prog_score

    # Store programmatic breakdown
    if trace is not None:
        trace['programmatic_metrics'] = prog_result['metrics']
        trace['programmatic_score'] = prog_score
        trace['llm_score'] = llm_score

    # Weighted combination: 70% programmatic, 30% LLM judge
    combined_score = 0.7 * prog_score + 0.3 * llm_score

    if trace is not None:
        trace['combined_score'] = combined_score

    return combined_score


# ============================================================================
# Batch Evaluation Utilities
# ============================================================================

def evaluate_all_examples(
    examples: list[GoldenExample],
    predictions: list[CourseSearchParams],
    llm: Any | None = None,
    verbose: bool = True
) -> dict[str, Any]:
    """
    Evaluate predictions against all golden examples.

    Returns:
        Dictionary with aggregate metrics and per-example traces
    """

    if len(examples) != len(predictions):
        raise ValueError(f"Mismatch: {len(examples)} examples but {len(predictions)} predictions")

    traces = []
    scores = []

    for i, (example, prediction) in enumerate(zip(examples, predictions)):
        trace = {'example_id': i, 'task_description': example.search_description}
        score = evaluate_query_generation(example, prediction, llm, trace)

        traces.append(trace)
        scores.append(score)

        if verbose:
            print(f"Example {i+1}/{len(examples)}: {score:.3f} - {example.search_description[:50]}...")

    # Aggregate statistics
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    # Count by score range
    excellent = sum(1 for s in scores if s >= 0.9)
    good = sum(1 for s in scores if 0.8 <= s < 0.9)
    acceptable = sum(1 for s in scores if 0.7 <= s < 0.8)
    poor = sum(1 for s in scores if s < 0.7)

    return {
        'average_score': avg_score,
        'min_score': min_score,
        'max_score': max_score,
        'score_distribution': {
            'excellent (≥0.9)': excellent,
            'good (0.8-0.9)': good,
            'acceptable (0.7-0.8)': acceptable,
            'poor (<0.7)': poor
        },
        'traces': traces
    }
