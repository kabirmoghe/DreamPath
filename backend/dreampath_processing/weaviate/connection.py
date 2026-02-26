import os
import weaviate


def connect_local_with_openai():
    headers = {}
    if os.getenv("OPENAI_API_KEY"):
        headers = {"X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"]}
    return weaviate.connect_to_local(headers=headers)
