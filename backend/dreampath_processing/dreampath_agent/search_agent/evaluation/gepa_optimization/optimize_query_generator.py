"""Optimize CourseQueryGenerator with GEPA"""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

import dspy
from dreampath_processing.dreampath_agent.search_agent.query_generator_dspy import (
    CourseQueryGenerator,
)
from evaluation.golden_examples import to_dspy_examples
from evaluation.metrics import evaluate_query_generation
from langchain_openai import ChatOpenAI


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY to run optimization")
        return

    # Configure DSPy
    print("Configuring DSPy...")
    lm = dspy.LM("openai/gpt-4o-mini", max_tokens=500, api_key=os.getenv("OPENAI_API_KEY"))
    dspy.configure(lm=lm)

    # Load dataset
    print("Loading golden dataset...")
    dataset = to_dspy_examples()
    print(f"Loaded {len(dataset)} examples")

    # Split into train/val/test
    # Use 70% train, 15% val, 15% test
    n = len(dataset)
    train_size = int(0.7 * n)
    val_size = int(0.15 * n)

    train_set = dataset[:train_size]
    val_set = dataset[train_size:train_size + val_size]
    test_set = dataset[train_size + val_size:]

    print(f"Split: {len(train_set)} train, {len(val_set)} val, {len(test_set)} test")

    # Create LLM judge for evaluation
    llm_judge = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Store detailed traces for inspection
    evaluation_traces = []

    # Create metric function for GEPA (requires 5-parameter signature)
    def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        """GEPA-compatible metric function

        Args:
            gold: dspy.Example (the expected/gold example)
            pred: dspy.Prediction (the model's prediction)
            trace: GEPA's trace collection (not used by us, GEPA manages it)
            pred_name: Name of the prediction component (unused)
            pred_trace: Trace of prediction execution (unused)

        Returns:
            float: Score 0-1
        """
        eval_trace = {}
        score = evaluate_query_generation(gold, pred, llm=llm_judge, trace=eval_trace)

        # Store our own trace for later display
        evaluation_traces.append({
            'example': gold,
            'prediction': pred,
            'trace': eval_trace,
            'score': score
        })

        # Return score - GEPA handles its own trace collection
        return score

    # ========================================================================
    # PRE-OPTIMIZATION EVALUATION
    # ========================================================================
    print("\n" + "=" * 70)
    print("PHASE 1: PRE-OPTIMIZATION BASELINE")
    print("=" * 70)

    program = CourseQueryGenerator()

    evaluate = dspy.Evaluate(
        devset=test_set,
        metric=metric,
        num_threads=1,  # Start with 1 thread for debugging
        display_table=False,  # We'll print our own summary
        display_progress=True
    )

    print("\nEvaluating pre-optimization baseline...")
    pre_result = evaluate(program)

    # Extract score from EvaluationResult
    pre_score = pre_result if isinstance(pre_result, (int, float)) else pre_result.score

    # Print clean summary
    print("\n" + "=" * 70)
    print("PRE-OPTIMIZATION TEST SET RESULTS")
    print("=" * 70)
    print(f"Test Set Size: {len(test_set)} examples")
    print(f"Average Score: {pre_score:.1f}%")

    # Show per-example breakdown
    if hasattr(pre_result, 'results') and pre_result.results:
        print("\nPer-Example Scores:")
        for i, result_tuple in enumerate(pre_result.results):
            example = test_set[i]
            # Result tuple is (example, prediction, score)
            score = result_tuple[2] if len(result_tuple) > 2 else result_tuple[-1]
            task = example.search_description[:50] + "..." if len(example.search_description) > 50 else example.search_description
            print(f"  [{i+1}] {score*100:.1f}% - {task}")

    print("=" * 70)

    # ========================================================================
    # DETAILED PER-EXAMPLE BREAKDOWN
    # ========================================================================
    print("\n" + "=" * 70)
    print("DETAILED EVALUATION BREAKDOWN")
    print("=" * 70)

    for i, trace_data in enumerate(evaluation_traces):
        example = trace_data['example']
        prediction = trace_data['prediction']
        trace = trace_data['trace']
        score = trace_data['score']

        print(f"\n{'='*70}")
        print(f"EXAMPLE {i+1}: {example.search_description}")
        print(f"{'='*70}")
        print(f"Overall Score: {score*100:.1f}%")

        # Expected vs Predicted
        print("\n--- EXPECTED PARAMETERS ---")
        exp = example.expected_params
        print(f"  query: '{exp.query}'")
        print(f"  alpha: {exp.alpha}")
        print(f"  department: {exp.department}")
        print(f"  course_code: {exp.course_code}")
        print(f"  max_num_prereqs: {exp.max_num_prereqs}")
        print(f"  difficulty: {exp.difficulty_classification}")
        print(f"  value: {exp.value_classification}")
        print(f"  sort_by_level: {exp.sort_by_level}")
        print(f"  limit: {exp.limit}")

        print("\n--- PREDICTED PARAMETERS ---")
        print(f"  query: '{prediction.query}' | ({type(prediction.query)})")
        print(f"  alpha: {prediction.alpha} | ({type(prediction.alpha)})")
        print(f"  department: {prediction.department} | ({type(prediction.department)})")
        print(f"  course_code: {prediction.course_code} | ({type(prediction.course_code)})")
        print(f"  max_num_prereqs: {prediction.max_num_prereqs} | ({type(prediction.max_num_prereqs)})")
        print(f"  difficulty: {prediction.difficulty_classification} | ({type(prediction.difficulty_classification)})")
        print(f"  value: {prediction.value_classification} | ({type(prediction.value_classification)})")
        print(f"  sort_by_level: {prediction.sort_by_level} | ({type(prediction.sort_by_level)})")
        print(f"  limit: {prediction.limit} | ({type(prediction.limit)})")

        # Programmatic metrics breakdown
        if 'programmatic_metrics' in trace:
            print("\n--- PROGRAMMATIC METRICS (70% weight) ---")
            print(f"  Overall: {trace['programmatic_score']*100:.1f}%")
            metrics = trace['programmatic_metrics']
            for metric_name, metric_score in metrics.items():
                status = "✓" if metric_score == 1.0 else "✗" if metric_score == 0.0 else "~"
                print(f"  {status} {metric_name}: {metric_score*100:.0f}%")

        # LLM judge breakdown
        if 'llm_scores' in trace:
            print("\n--- LLM JUDGE (30% weight) ---")
            print(f"  Overall: {trace['llm_score']*100:.1f}%")
            llm_scores = trace['llm_scores']
            for dim, val in llm_scores.items():
                print(f"    {dim}: {val*100:.0f}%")

        if 'llm_feedback' in trace:
            print("\n--- LLM FEEDBACK ---")
            print(f"  {trace['llm_feedback']}")

        if 'improvement_suggestions' in trace:
            print("\n--- IMPROVEMENT SUGGESTIONS ---")
            print(f"  {trace['improvement_suggestions']}")

    print("\n" + "=" * 70)

    # ========================================================================
    # GEPA OPTIMIZATION
    # ========================================================================
    print("\n" + "=" * 70)
    print("PHASE 2: GEPA OPTIMIZATION")
    print("=" * 70)

    print("\nInitializing GEPA optimizer...")

    # Create GEPA optimizer
    gepa = dspy.GEPA(
        metric=metric,  # Uses our combined metric (70% programmatic + 30% LLM judge)
        auto="light",   # Light budget for initial run (can increase to 'medium' or 'heavy')
        num_threads=16,  # Parallel evaluation
        track_stats=True,
        reflection_lm=dspy.LM(
            model="openai/gpt-5",  # Stronger model for reflection
            temperature=1.0,
            max_tokens=16000,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    )

    print(f"Compiling with GEPA on {len(train_set)} train examples, {len(val_set)} val examples...")
    print("This may take several minutes as GEPA iteratively improves the prompt...\n")

    # Clear evaluation traces before optimization
    evaluation_traces.clear()

    # Compile (optimize) the program
    optimized_program = gepa.compile(
        student=program,
        trainset=train_set,
        valset=val_set
    )

    print("\n✓ GEPA optimization complete!")

    # Save the optimized program
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = Path(__file__).parent / "optimized_programs"
    save_dir.mkdir(exist_ok=True)

    # Save as JSON
    save_path = save_dir / f"optimized_query_generator_{timestamp}.json"
    optimized_program.save(str(save_path))
    print(f"\n📁 Saved optimized program to: {save_path}")

    # Print the optimized signature instructions (following DSPy docs pattern)
    print("\n" + "=" * 70)
    print("OPTIMIZED PREDICTORS")
    print("=" * 70)

    for name, pred in optimized_program.named_predictors():
        print(f"\n{'='*70}")
        print(f"Predictor: {name}")
        print(f"{'='*70}")
        print("Optimized Instructions:")
        print(pred.signature.instructions)
        print("*" * 70)

    print("=" * 70)

    # ========================================================================
    # POST-OPTIMIZATION EVALUATION
    # ========================================================================
    print("\n" + "=" * 70)
    print("PHASE 3: POST-OPTIMIZATION EVALUATION")
    print("=" * 70)

    # Clear traces again for post-optimization evaluation
    evaluation_traces.clear()

    # Evaluate optimized program on test set
    print("\nEvaluating post-optimization on test set...")
    post_result = evaluate(optimized_program)

    # Extract score
    post_score = post_result if isinstance(post_result, (int, float)) else post_result.score

    # Print summary
    print("\n" + "=" * 70)
    print("POST-OPTIMIZATION TEST SET RESULTS")
    print("=" * 70)
    print(f"Test Set Size: {len(test_set)} examples")
    print(f"Average Score: {post_score:.1f}%")

    # Show per-example breakdown
    if hasattr(post_result, 'results') and post_result.results:
        print("\nPer-Example Scores:")
        for i, result_tuple in enumerate(post_result.results):
            example = test_set[i]
            score = result_tuple[2] if len(result_tuple) > 2 else result_tuple[-1]
            task = example.search_description[:50] + "..." if len(example.search_description) > 50 else example.search_description
            print(f"  [{i+1}] {score*100:.1f}% - {task}")

    print("=" * 70)

    # ========================================================================
    # COMPARISON
    # ========================================================================
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"Pre-optimization:  {pre_score:.1f}%")
    print(f"Post-optimization: {post_score:.1f}%")
    print(f"Improvement:       {post_score - pre_score:+.1f}%")

    if post_score > pre_score:
        print(f"\n🎉 GEPA improved performance by {post_score - pre_score:.1f} percentage points!")
    elif post_score == pre_score:
        print("\n→ No change in performance")
    else:
        print(f"\n⚠️  Performance decreased by {pre_score - post_score:.1f} percentage points")


if __name__ == "__main__":
    main()
