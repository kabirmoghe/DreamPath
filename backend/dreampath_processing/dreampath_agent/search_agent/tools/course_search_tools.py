import os
import warnings

from dotenv import load_dotenv
from dreampath_processing.dreampath_agent.dreampath_types import CourseSearchOutput
from dreampath_processing.dreampath_agent.search_agent.course_search_client import (
    CourseSearchClient,
)
from dreampath_processing.dreampath_agent.search_agent.evaluation.utils import load_best_prompt
from dreampath_processing.dreampath_agent.search_agent.query_generator import CourseQueryGenerator
from dreampath_processing.dreampath_agent.search_agent.search_types import CourseSearchParams
from instructor import from_openai
from langchain_core.tools import tool
from openai import OpenAI

load_dotenv()

# Suppress Weaviate connection warnings - we use a singleton pattern where
# the connection intentionally stays open for the application lifetime
warnings.filterwarnings('ignore', message='.*Weaviate.*not closed properly.*')
warnings.filterwarnings('ignore', category=ResourceWarning, module='weaviate')

@tool
def module_search(search_description: str) -> CourseSearchOutput:
    """Search for courses using AI module-generated optimal parameters.

    ATOMIC REQUIREMENT: Each search must use ONE set of FILTER values (single department,
    single difficulty level, etc.). Filter parameters are NOT arrays.

    IMPORTANT: The semantic query content CAN and SHOULD include multiple related concepts.
    Atomicity applies to FILTERS, not semantic richness.

    If a task mentions multiple DEPARTMENTS or DIFFICULTY LEVELS, call this tool MULTIPLE times.
    If a task mentions multiple RELATED CONCEPTS in same domain, use ONE rich semantic query.

    Examples of ATOMIC search descriptions:
    - "Easy CS courses with high learning value for machine learning careers" ✓ (ONE department, ONE difficulty)
    - "Machine learning deep learning transformers and NLP" ✓ (Related concepts, ONE department)
    - "Data structures and algorithms fundamentals" ✓ (Related topics, ONE query)
    - "Challenging philosophy courses on ethics" ✓ (ONE department, ONE difficulty)

    Examples of NON-ATOMIC (requires multiple calls):
    - "Quantitative methods in Math, Stats, and QSS" ✗ (3 departments → 3 separate calls)
    - "Easy and challenging philosophy courses" ✗ (2 difficulty levels → 2 separate calls)

    The AI will automatically determine the best search parameters (department, filters, etc.)
    based on your description.

    Args:
        search_description: Atomic description (ONE set of filter values, rich semantic content OK)

    Returns:
        CourseSearchOutput with matching courses
    """

    # Initialize the query generator
    client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
    query_generator = CourseQueryGenerator(client)
    query_generator_prompt = load_best_prompt()
    query_generator.configure(system_prompt=query_generator_prompt)

    # Initialize the course search client
    course_search_client = CourseSearchClient()

    # Generate + execute the search
    query = query_generator.generate(search_description)
    print(f"Executing module search with query: {query}")
    results = course_search_client.structured_hybrid_search(query)
    return results

@tool
def manual_search(
    query: str,
    department: str | None = None,
    difficulty_classification: str | None = None,  # "Low" | "Medium" | "High"
    value_classification: str | None = None,  # "Low" | "Medium" | "High"
    max_num_prereqs: int | None = None,
    sort_by_level: bool = False,
    limit: int = 10,
    alpha: float = 0.5  # Hybrid search weight (0=keyword, 1=semantic)
) -> CourseSearchOutput:
    """Refine course search with explicit parameters.
    
    Use this when you need precise control over search filters,
    or when refining results from module_search.
    """
    course_search_client = CourseSearchClient()

    params = CourseSearchParams(
        query=query,
        alpha=alpha,
        department=department,
        max_num_prereqs=max_num_prereqs,
        difficulty_classification=difficulty_classification,
        value_classification=value_classification,
        sort_by_level=sort_by_level,
        limit=limit
    )

    print(f"Executing manual search with query: {params}")

    results = course_search_client.structured_hybrid_search(params)

    return results


if __name__ == "__main__":
    search_descriptions = [
        "Find cool courses that are relatively easy in CS",
        "Find a class on social network theory",
        "Determine if there are mid-level econ courses with minimal prerequisites",
        "Cross-disciplinary courses on AI and bio",
        "Easy philosophy courses",
    ]
    for i, search_description in enumerate(search_descriptions):
        print('=' * 100)
        print(f"# Search {i+1}: {search_description}")
        results = task_level_search(search_description)
        print("Search results:")
        for result in results.results:
            print(result.model_dump_json(indent=2))
            print("-" * 100)