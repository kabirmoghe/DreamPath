import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dreampath_processing.dreampath_agent.search_agent.search_types import CourseSearchParams


class CourseQueryGenerator:
    def __init__(self, client):
        self.client = client

    def configure(self, system_prompt: str | None=None, model: str | None="gpt-4o"):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if model is not None:
            self.model = model

    def generate(self, search_description: str) -> CourseSearchParams:
        """Generate CourseSearchParams from an atomic search description.

        Args:
            search_description: Atomic description of courses to find

        Returns:
            CourseSearchParams with optimized search parameters
        """
        messages = [{'role': 'system', 'content': self.system_prompt}, {'role': 'user', 'content': search_description}]
        query = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_model=CourseSearchParams,
        )

        return query

if __name__ == "__main__":
    import os

    from dotenv import load_dotenv
    from evaluation.utils import load_best_prompt
    from instructor import from_openai
    from openai import OpenAI

    load_dotenv()

    client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
    query_generator = CourseQueryGenerator(client)
    query_generator_prompt = load_best_prompt()
    query_generator.configure(system_prompt=query_generator_prompt)

    search_descriptions = [
        "Find cool courses that are relatively easy in CS",
        "Find a class on social network theory",
        "Determine if there are mid-level econ courses with minimal prerequisites",
        "Cross-disciplinary courses on AI and bio",
        "Easy philosophy courses",
    ]

    for description in search_descriptions:
        print(f"Search Description: {description}")
        print(query_generator.generate(description))
        print("-" * 100)
