import json
from pathlib import Path

from dreampath_processing.dreampath_agent.search_agent.evaluation.manual_optimization.tuning_utils import (
    PromptEvaluationManager,
)

# Get paths relative to this file's location
_THIS_DIR = Path(__file__).parent
_MANUAL_OPT_DIR = _THIS_DIR / "manual_optimization"
_DEFAULT_PROMPT_DIR = _MANUAL_OPT_DIR / "prompts"
_DEFAULT_METADATA_PATH = _MANUAL_OPT_DIR / "prompt_metadata.json"
_DEFAULT_PERFORMANCE_PATH = _MANUAL_OPT_DIR / "evaluation_performance.json"


def load_best_prompt(prompt_dir: str | Path | None = None, prompt_metadata_path: str | Path | None = None, evaluation_performance_path: str | Path | None = None):
    """
    Load the prompt with version='best' in metadata using PromptEvaluationManager.

    Args:
        prompt_dir: Directory containing prompts (defaults to module-relative path)
        prompt_metadata_path: Path to prompt_metadata.json (defaults to module-relative path)
        evaluation_performance_path: Path to evaluation_performance.json (defaults to module-relative path)

    Returns:
        The prompt string (value of QUERY_GENERATION_PROMPT variable)
    """
    prompt_dir = Path(prompt_dir) if prompt_dir else _DEFAULT_PROMPT_DIR
    prompt_metadata_path = Path(prompt_metadata_path) if prompt_metadata_path else _DEFAULT_METADATA_PATH
    evaluation_performance_path = Path(evaluation_performance_path) if evaluation_performance_path else _DEFAULT_PERFORMANCE_PATH
    prompts_subdir = prompt_dir
    
    # Load metadata to find the best prompt
    if not prompt_metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {prompt_metadata_path}")
    
    with open(prompt_metadata_path) as f:
        prompt_metadata = json.load(f)
    
    # Find prompt with version='best'
    best_prompt_id = None
    for prompt_id, metadata in prompt_metadata.items():
        if metadata.get('version') == 'best':
            best_prompt_id = prompt_id
            break
    
    if best_prompt_id is None:
        raise ValueError("No prompt with version='best' found in metadata")
    
    # Use PromptEvaluationManager to load the prompt
    manager = PromptEvaluationManager(
        prompt_dir=str(prompts_subdir),
        prompt_metadata_path=str(prompt_metadata_path),
        evaluation_performance_path=str(evaluation_performance_path)
    )
    
    return manager.load_prompt(best_prompt_id)