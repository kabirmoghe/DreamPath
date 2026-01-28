"""
Search tools for the search agent.

Two search modes:
1. module_search - AI-optimized (instructor generates params from description)
2. manual_search - Precise control (user provides exact params)

IMPORTANT: These functions are truly async and can be parallelized with asyncio.gather().
- Query generation uses AsyncOpenAI (yields to event loop during API call)
- Weaviate search uses run_in_executor (runs in thread pool to not block event loop)
"""

import asyncio
import os

from dreampath_processing.dreampath_agent.dreampath_types import CourseSearchOutput
from dreampath_processing.dreampath_agent.search_agent.search_types import CourseSearchParams
from dreampath_processing.dreampath_agent.search_agent.tools.course_search_client import (
    CourseSearchClient,
)
from dreampath_processing.dreampath_agent.search_agent.tools.query_generator import (
    CourseQueryGenerator,
)
from instructor import from_openai
from openai import AsyncOpenAI, OpenAI

# ============================================
# Initialize Query Generator (singleton pattern)
# ============================================

_query_generator = None


def _get_query_generator():
    """Lazy initialization of query generator with both sync and async clients"""
    global _query_generator

    if _query_generator is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not set - required for module_search")

        # Initialize both sync and async instructor clients
        sync_client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
        async_client = from_openai(AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")))
        _query_generator = CourseQueryGenerator(sync_client, async_client=async_client)

        # Load best prompt from evaluation
        try:
            from dreampath_processing.dreampath_agent.search_agent.evaluation.utils import (
                load_best_prompt,
            )
            prompt = load_best_prompt()
            _query_generator.configure(system_prompt=prompt, model="gpt-4o-mini")
        except Exception as e:
            print(f"Warning: Could not load best prompt: {e}")
            print("Using fallback prompt_2")
            from dreampath_processing.dreampath_agent.search_agent.evaluation.manual_optimization.prompts.prompt_2 import (
                QUERY_GENERATION_PROMPT,
            )
            _query_generator.configure(system_prompt=QUERY_GENERATION_PROMPT, model="gpt-4o-mini")

    return _query_generator


# ============================================
# Async Weaviate Helper
# ============================================

def _execute_weaviate_search_sync(params: CourseSearchParams) -> CourseSearchOutput:
    """
    Execute Weaviate search synchronously.
    This is called via run_in_executor to not block the event loop.
    """
    client = CourseSearchClient()
    try:
        return client.structured_hybrid_search(params)
    finally:
        client.close()


async def _execute_weaviate_search_async(params: CourseSearchParams) -> CourseSearchOutput:
    """
    Execute Weaviate search without blocking the event loop.
    Uses run_in_executor since Weaviate Python client is sync.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _execute_weaviate_search_sync, params)


# ============================================
# Search Tools
# ============================================

async def module_search(search_input: str) -> tuple[CourseSearchParams, CourseSearchOutput]:
    """
    AI-optimized search using instructor to generate parameters.

    This function is truly async - both query generation and Weaviate search
    yield to the event loop, enabling parallel execution with asyncio.gather().

    Args:
        search_input: Atomic search description (e.g., "Easy ML courses with high learning value")

    Returns:
        (generated_params, search_results) - Returns both the instructor-generated params and results
        so they can be stored in SearchExecution and rendered in context

    Flow:
        1. Instructor generates CourseSearchParams from search_input (async)
        2. Execute hybrid search with generated params (async via thread pool)
        3. Return both params and results
    """
    query_generator = _get_query_generator()

    # 1. Generate params using async instructor (yields to event loop)
    params = await query_generator.generate_async(search_input)

    # 2. Execute search (runs in thread pool to not block event loop)
    result = await _execute_weaviate_search_async(params)

    return (params, result)


async def manual_search(params: CourseSearchParams) -> tuple[CourseSearchParams, CourseSearchOutput]:
    """
    Manual search with precise parameter control.

    This function is truly async - Weaviate search yields to the event loop,
    enabling parallel execution with asyncio.gather().

    Args:
        params: CourseSearchParams with exact search parameters

    Returns:
        (params, search_results) - Returns tuple for consistency with module_search

    Flow:
        1. Execute hybrid search with provided params (async via thread pool)
        2. Return both params and results
    """
    print(f"      [Manual] Params: query='{params.query}', dept={params.department}, difficulty={params.difficulty_classification}")

    # Execute search (runs in thread pool to not block event loop)
    result = await _execute_weaviate_search_async(params)

    return (params, result)


# ============================================
# For testing
# ============================================

if __name__ == "__main__":
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    async def test():
        print("=" * 80)
        print("Testing module_search (instructor-based)")
        print("=" * 80)
        params1, result1 = await module_search("Easy machine learning courses with high learning value")
        print(f"Generated params: {params1.model_dump()}")
        print(f"Found {len(result1.results)} courses")
        for course in result1.results[:3]:
            print(f"  - {course.course_code}: {course.course_title}")

        print("\n" + "=" * 80)
        print("Testing manual_search")
        print("=" * 80)
        params = CourseSearchParams(
            query="philosophy ethics",
            department="Philosophy",
            difficulty_classification="High",
            limit=5,
            alpha=0.6
        )
        params2, result2 = await manual_search(params)
        print(f"Used params: {params2.model_dump()}")
        print(f"Found {len(result2.results)} courses")
        for course in result2.results[:3]:
            print(f"  - {course.course_code}: {course.course_title}")

    asyncio.run(test())
