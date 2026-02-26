import argparse
import os
from pathlib import Path

from golden_examples import GOLDEN_EXAMPLES
from openai import OpenAI
from query_generator import CourseQueryGenerator
from tuning_utils import PromptEvaluationManager


def main(args):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    query_generator = CourseQueryGenerator(client)

    # Initialize PromptDataManager with prompts directory
    manager = PromptEvaluationManager(
        prompt_dir=Path(__file__).parent / "prompts",
        prompt_metadata_path=Path(__file__).parent / "prompt_metadata.json",
        evaluation_performance_path=Path(__file__).parent / "evaluation_performance.json"
    )
    
    # Testing
    for i in range(10):
        print(f"========= Evaluating batch {i+1} of 10 =========")
        for example in GOLDEN_EXAMPLES:
            task_performance = manager.evaluate_prompt_batch_on_example(query_generator, example, default_models=["gpt-4o-mini"])
            manager.save_evaluation_performance(example.search_description, task_performance)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt_metadata_path", type=str, default=Path(__file__).parent / "prompt_metadata.json")
    parser.add_argument("--evaluation_performance_path", type=str, default=Path(__file__).parent / "evaluation_performance.json")
    parser.add_argument("--prompt_dir", type=str, default=Path(__file__).parent / "prompts")
    parser.add_argument("--prompt_ids", nargs="+", type=str, default=None) # If None, will evaluate all prompts in prompt_dir
    parser.add_argument("--num_runs", type=int, default=10)
    args = parser.parse_args()
    main(args)