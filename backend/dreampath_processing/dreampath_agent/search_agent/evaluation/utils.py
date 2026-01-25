import json
from pathlib import Path

from dreampath_processing.dreampath_agent.search_agent.evaluation.manual_optimization.tuning_utils import (
    PromptEvaluationManager,
)


def load_best_prompt(prompt_dir: str | Path="dreampath_processing/dreampath_agent/search_agent/evaluation/manual_optimization/prompts", prompt_metadata_path: str | Path="dreampath_processing/dreampath_agent/search_agent/evaluation/manual_optimization/prompt_metadata.json", evaluation_performance_path: str | Path="dreampath_processing/dreampath_agent/search_agent/evaluation/manual_optimization/evaluation_performance.json"):
    """
    Load the prompt with version='best' in metadata using PromptEvaluationManager.
    
    Args:
        prompt_dir: Directory containing prompt_metadata.json and prompts/ subdirectory
        
    Returns:
        The prompt string (value of QUERY_GENERATION_PROMPT variable)
    """
    prompt_dir = Path(prompt_dir)
    prompt_metadata_path = Path(prompt_metadata_path)
    evaluation_performance_path = Path(evaluation_performance_path)
    prompts_subdir = Path(prompt_dir)
    
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