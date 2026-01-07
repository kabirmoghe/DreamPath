from tuning_utils import PromptEvaluationManager
from pathlib import Path
import argparse

def main(args, metadata_kwargs):
    manager = PromptEvaluationManager(
        prompt_dir=Path(args.prompt_dir),
        prompt_metadata_path=Path(args.prompt_metadata_path),
        evaluation_performance_path=Path(args.evaluation_performance_path)
    )
    manager.save_prompt_metadata(args.prompt_id, **metadata_kwargs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt_dir", type=str, default=Path(__file__).parent / "prompts")
    parser.add_argument("--prompt_metadata_path", type=str, default=Path(__file__).parent / "prompt_metadata.json")
    parser.add_argument("--evaluation_performance_path", type=str, default=Path(__file__).parent / "evaluation_performance.json")
    parser.add_argument("--prompt_id", type=str, required=True)
    
    # Parse known arguments first
    args, unknown = parser.parse_known_args()
    
    # Extract metadata kwargs from unknown arguments
    # Format: --key value --key2 value2
    metadata_kwargs = {}
    i = 0
    while i < len(unknown):
        arg = unknown[i]
        if arg.startswith('--'):
            key = arg[2:]  # Remove '--' prefix
            if i + 1 < len(unknown) and not unknown[i + 1].startswith('--'):
                value = unknown[i + 1]
                metadata_kwargs[key] = value
                i += 2
            else:
                # Boolean flag (no value)
                metadata_kwargs[key] = True
                i += 1
        else:
            i += 1
    
    if not metadata_kwargs:
        parser.error("At least one metadata field must be provided (e.g., --description 'text' or --removed 'text')")
    
    main(args, metadata_kwargs)