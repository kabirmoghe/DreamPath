from pathlib import Path

from tuning_utils import PromptEvaluationManager

manager = PromptEvaluationManager(
    prompt_dir=Path(__file__).parent.parent.parent / "prompts",
    prompt_metadata_path=Path(__file__).parent.parent.parent / "prompt_metadata.json",
    evaluation_performance_path=Path(__file__).parent.parent.parent / "evaluation_performance.json"
)

print(manager.compare_prompts(["prompt_0.py", "prompt_1.py"]))