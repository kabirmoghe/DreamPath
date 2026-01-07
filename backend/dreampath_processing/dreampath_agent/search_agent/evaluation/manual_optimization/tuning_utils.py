from pathlib import Path
import importlib.util
import json
import warnings
import os
import sys
from typing import Optional

# Suppress litellm deprecation warning about asyncio.get_event_loop()
# This warning comes from litellm (used by langfuse) and is harmless
warnings.filterwarnings("ignore", message="There is no current event loop", category=DeprecationWarning)

from instructor import from_openai
from openai import OpenAI

sys.path.append(str(Path(__file__).parent.parent.parent))

from dreampath_processing.dreampath_agent.search_agent.tools.query_generator import CourseQueryGenerator
from dreampath_processing.dreampath_agent.search_agent.evaluation.metrics import evaluate_query_generation
from dreampath_processing.dreampath_agent.search_agent.evaluation.golden_examples import GoldenExample, GOLDEN_EXAMPLES

class PromptEvaluationManager:
    def __init__(self, prompt_dir: str, prompt_metadata_path: str='prompt_metadata.json', evaluation_performance_path: str='evaluation_performance.json', llm_judge=None):
        self.prompt_dir = Path(prompt_dir)
        self.prompt_metadata_path = Path(prompt_metadata_path)
        self.evaluation_performance_path = Path(evaluation_performance_path)
        self._llm_judge = llm_judge  # Store the provided judge or None

    @property
    def llm_judge(self):
        """Lazy-load the LLM judge (OpenAI client with instructor) on first access."""
        if self._llm_judge is None:
            # Only create when actually needed - no heavy LangChain imports!
            client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
            self._llm_judge = client
        return self._llm_judge

    def save_prompt_metadata(self, prompt_filename: str, **kwargs):
        """
        Saves metadata for given prompt into file.
        
        Args:
            prompt_filename: Name of the prompt file (relative to prompt_dir)
            **kwargs: Metadata fields to save (e.g., 'added', 'removed', etc.)
            
        Example:
            save_prompt_metadata(
                "prompt_0.py",
                added="New section about transformers",
                removed="Old examples section"
            )
        """
        prompt_path = self.prompt_dir / prompt_filename
        
        # Load existing metadata if file exists
        if self.prompt_metadata_path.exists():
            try:
                with open(self.prompt_metadata_path, 'r') as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, IOError):
                metadata = {}
        else:
            metadata = {}
        
        # Use prompt filename as key (relative to prompt_dir)
        prompt_key = prompt_filename
        
        # Initialize entry for this prompt if it doesn't exist
        if prompt_key not in metadata:
            metadata[prompt_key] = {}
        
        # Update metadata with kwargs
        metadata[prompt_key].update(kwargs)
        
        # Save back to file
        with open(self.prompt_metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def load_prompt(self, prompt_filename: str, prompt_name: str='QUERY_GENERATION_PROMPT') -> str:
        """
        Loads prompt from filename (relative to prompt_dir).
        
        Args:
            prompt_filename: Name of the prompt file (relative to prompt_dir)
            prompt_name: Name of the variable to load (default: 'QUERY_GENERATION_PROMPT')
            
        Returns:
            The value of the prompt variable (typically a string)
        """
        prompt_path = self.prompt_dir / prompt_filename

        # Import spec
        spec = importlib.util.spec_from_file_location(
            name=prompt_path.stem,
            location=str(prompt_path)
        )
        
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec from {prompt_path}")
        
        # Create and execute the module
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get the variable from the module
        if not hasattr(module, prompt_name):
            available = [name for name in dir(module) if not name.startswith('_')]
            raise AttributeError(
                f"Variable '{prompt_name}' not found in {prompt_path}. "
                f"Available variables: {available}"
            )
        
        return getattr(module, prompt_name)

    def evaluate_prompt_batch_on_example(self, query_generator: CourseQueryGenerator, example: GoldenExample, models_by_prompt: Optional[dict[str, list[str]]]=None, default_models: Optional[list[str]]=None):
        """
        Evaluates a batch of prompts for a given example (task-specific).
        Returns dict indexed by prompt_id (stem), with values being performance dicts indexed by model.
        
        Returns:
            Dict[str, Dict[str, dict]]: {prompt_id: {model: {prediction, expected_params, composite_score, model_trace}}}
        """
        print(f"Evaluating example | task = {example.search_description}")

        task_performance = {}
        task = example.search_description

        # If user wants to evaluate a specific set of prompts, use the models_by_prompt dict
        if models_by_prompt is not None:
            prompts = models_by_prompt.keys()
        else:
            prompts = [p for p in self.prompt_dir.iterdir() if p.is_file() and p.suffix == '.py']
        
        for prompt_file in prompts:
            # Iterate over models, only evaluate for prompts that are in the models_by_prompt dict
            if models_by_prompt is not None:
                models = models_by_prompt.get(prompt_file.stem)
                if models is None:
                    continue
            else:
                models = default_models

            # Load the prompt
            print(f"Evaluating prompt: {prompt_file.stem}")
            prompt = self.load_prompt(prompt_file.name)
            query_generator.configure(system_prompt=prompt)
            prompt_performance = {}
                
            for model in models:
                query_generator.configure(model=model)
                query = query_generator.generate(task=task) # Structured output of CourseSearchParams
                
                # Evaluate the query
                model_trace = {}
                composite_score = evaluate_query_generation(example, query, llm=self.llm_judge, trace=model_trace)
                prompt_performance[model] = {
                    'prediction': query.model_dump_json(),
                    'expected_params': example.expected_params.model_dump_json(),
                    'composite_score': composite_score,
                    'model_trace': model_trace
                }

            task_performance[prompt_file.stem] = prompt_performance

        return task_performance

    def save_evaluation_performance(self, task: str, task_performance: dict):
        """
        Saves evaluation performance to a JSON file. Indexed by task, with values being a list of performance dictionaries for each prompt.
        Updates existing file if it exists, appending ALL new performance entries (including duplicates) for existing tasks.
        
        Args:
            task: The search description (from example.search_description)
            task_performance: Dict with prompt_id (stem) as key, and value being performance dict indexed by model
        """        
        # Load existing data if file exists
        if self.evaluation_performance_path.exists():
            try:
                with open(self.evaluation_performance_path, 'r') as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing_data = {}
        else:
            existing_data = {}
        
        # Convert task_performance dict to list format for saving
        # Format: [{prompt_id: str, performance: dict}, ...]
        performance_list = [
            {
                'prompt_id': prompt_id,
                'performance': performance
            }
            for prompt_id, performance in task_performance.items()
        ]
        
        # If task exists, extend the list; otherwise create new list
        if task in existing_data:
            # Append all new entries to existing list (keep all entries, even duplicates)
            existing_data[task].extend(performance_list)
        else:
            # Create new list for this task
            existing_data[task] = performance_list
        
        # Save updated data
        with open(self.evaluation_performance_path, 'w') as f:
            json.dump(existing_data, f, indent=2)

    def load_evaluation_performance(self) -> dict:
        """
        Loads evaluation performance from JSON file.
        
        Returns:
            Dict indexed by task, with values being lists of performance entries
        """
        if not self.evaluation_performance_path.exists():
            return {}
        
        try:
            with open(self.evaluation_performance_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to load evaluation performance: {e}")

    def get_prompt_statistics(self, prompt_id: str = None) -> dict:
        """
        Get statistics for a specific prompt or all prompts.
        
        Args:
            prompt_id: Optional prompt ID to filter by. If None, returns stats for all prompts.
            
        Returns:
            Dict with statistics including:
            - overall: Overall statistics (count, mean, min, max, std)
            - by_task: Statistics per task
            - by_model: Statistics per model
            - by_prompt: Statistics per prompt
        """
        data = self.load_evaluation_performance()
        
        all_scores = []
        scores_by_task = {}
        scores_by_model = {}
        scores_by_prompt = {}
        
        for task, entries in data.items():
            for entry in entries:
                entry_prompt_id = entry.get('prompt_id')
                
                # Filter by prompt_id if specified
                if prompt_id is not None and entry_prompt_id != prompt_id:
                    continue
                
                performance = entry.get('performance', {})
                for model, model_perf in performance.items():
                    score = model_perf.get('composite_score', 0)
                    all_scores.append(score)
                    
                    # Aggregate by task
                    if task not in scores_by_task:
                        scores_by_task[task] = []
                    scores_by_task[task].append(score)
                    
                    # Aggregate by model
                    if model not in scores_by_model:
                        scores_by_model[model] = []
                    scores_by_model[model].append(score)
                    
                    # Aggregate by prompt
                    if entry_prompt_id not in scores_by_prompt:
                        scores_by_prompt[entry_prompt_id] = []
                    scores_by_prompt[entry_prompt_id].append(score)
        
        def calculate_stats(scores):
            if not scores:
                return {'count': 0, 'mean': 0, 'min': 0, 'max': 0, 'std': 0}
            import statistics
            return {
                'count': len(scores),
                'mean': statistics.mean(scores),
                'min': min(scores),
                'max': max(scores),
                'std': statistics.stdev(scores) if len(scores) > 1 else 0
            }
        
        return {
            'overall': calculate_stats(all_scores),
            'by_task': {task: calculate_stats(scores) for task, scores in scores_by_task.items()},
            'by_model': {model: calculate_stats(scores) for model, scores in scores_by_model.items()},
            'by_prompt': {prompt: calculate_stats(scores) for prompt, scores in scores_by_prompt.items()}
        }

    def get_best_prompts(self, top_k: int = 5, min_evaluations: int = 1) -> list[dict]:
        """
        Get the top performing prompts based on average composite score.
        
        Args:
            top_k: Number of top prompts to return
            min_evaluations: Minimum number of evaluations required
            
        Returns:
            List of dicts with prompt_id, average_score, evaluation_count, min_score, max_score, std_score
        """
        stats = self.get_prompt_statistics()
        prompt_stats = stats['by_prompt']
        
        # Filter by minimum evaluations and calculate averages
        prompt_rankings = []
        for prompt_id, stat in prompt_stats.items():
            if stat['count'] >= min_evaluations:
                prompt_rankings.append({
                    'prompt_id': prompt_id,
                    'average_score': stat['mean'],
                    'evaluation_count': stat['count'],
                    'min_score': stat['min'],
                    'max_score': stat['max'],
                    'std_score': stat['std']
                })
        
        # Sort by average score descending
        prompt_rankings.sort(key=lambda x: x['average_score'], reverse=True)
        
        return prompt_rankings[:top_k]

    def get_task_analysis(self, task: str = None) -> dict:
        """
        Get detailed analysis for a specific task or all tasks.
        
        Args:
            task: Optional search description to filter by. If None, returns analysis for all tasks.
            
        Returns:
            Dict with task analysis including prompt comparisons and model comparisons
        """
        data = self.load_evaluation_performance()
        
        if task is not None and task not in data:
            return {}
        
        tasks_to_analyze = [task] if task else data.keys()
        
        analysis = {}
        for task_name in tasks_to_analyze:
            entries = data[task_name]
            
            prompt_scores = {}
            model_scores = {}
            
            for entry in entries:
                prompt_id = entry.get('prompt_id')
                performance = entry.get('performance', {})
                
                for model, model_perf in performance.items():
                    score = model_perf.get('composite_score', 0)
                    
                    # Aggregate by prompt
                    if prompt_id not in prompt_scores:
                        prompt_scores[prompt_id] = []
                    prompt_scores[prompt_id].append(score)
                    
                    # Aggregate by model
                    if model not in model_scores:
                        model_scores[model] = []
                    model_scores[model].append(score)
            
            import statistics
            analysis[task_name] = {
                'total_evaluations': len(entries),
                'prompt_performance': {
                    prompt_id: {
                        'count': len(scores),
                        'mean': statistics.mean(scores),
                        'min': min(scores),
                        'max': max(scores),
                        'std': statistics.stdev(scores) if len(scores) > 1 else 0
                    }
                    for prompt_id, scores in prompt_scores.items()
                },
                'model_performance': {
                    model: {
                        'count': len(scores),
                        'mean': statistics.mean(scores),
                        'min': min(scores),
                        'max': max(scores),
                        'std': statistics.stdev(scores) if len(scores) > 1 else 0
                    }
                    for model, scores in model_scores.items()
                }
            }
        
        return analysis

    def get_detailed_metrics(self, prompt_id: str = None, task: str = None, model: str = None) -> list[dict]:
        """
        Get detailed metrics for filtered evaluations.
        
        Args:
            prompt_id: Optional prompt ID to filter by
            task: Optional search description to filter by
            model: Optional model name to filter by
            
        Returns:
            List of dicts with detailed metrics for each matching evaluation
        """
        data = self.load_evaluation_performance()
        
        results = []
        for task_name, entries in data.items():
            # Filter by task if specified
            if task is not None and task_name != task:
                continue
            
            for entry in entries:
                entry_prompt_id = entry.get('prompt_id')
                
                # Filter by prompt_id if specified
                if prompt_id is not None and entry_prompt_id != prompt_id:
                    continue
                
                performance = entry.get('performance', {})
                for model_name, model_perf in performance.items():
                    # Filter by model if specified
                    if model is not None and model_name != model:
                        continue
                    
                    model_trace = model_perf.get('model_trace', {})
                    results.append({
                        'task': task_name,
                        'prompt_id': entry_prompt_id,
                        'model': model_name,
                        'composite_score': model_perf.get('composite_score', 0),
                        'prediction': model_perf.get('prediction'),
                        'expected_params': model_perf.get('expected_params'),
                        'programmatic_score': model_trace.get('programmatic_score', 0),
                        'llm_score': model_trace.get('llm_score', 0),
                        'programmatic_metrics': model_trace.get('programmatic_metrics', {}),
                        'llm_scores': model_trace.get('llm_scores', {}),
                        'llm_feedback': model_trace.get('llm_feedback', ''),
                        'improvement_suggestions': model_trace.get('improvement_suggestions', '')
                    })
        
        return results

    def compare_prompts(self, prompt_ids: list[str], task: str = None) -> dict:
        """
        Compare multiple prompts side by side.
        
        Args:
            prompt_ids: List of prompt IDs to compare
            task: Optional task to filter by
            
        Returns:
            Dict with comparison statistics for each prompt
        """
        comparison = {}
        for prompt_id in prompt_ids:
            stats = self.get_prompt_statistics(prompt_id=prompt_id)
            comparison[prompt_id] = {
                'overall': stats['overall'],
                'by_task': stats['by_task'] if task is None else {task: stats['by_task'].get(task, {})},
                'by_model': stats['by_model']
            }
        
        return comparison
        