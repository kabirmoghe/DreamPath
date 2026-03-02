"""Activity query generator — translates natural language to ActivitySearchParams.

Mirrors CourseQueryGenerator pattern with sync and async clients.
"""

from dreampath_processing.dreampath_agent.search_agent.types.activity_types import (
    ActivitySearchParams,
)

ACTIVITY_QUERY_GENERATION_PROMPT = """\
You are an expert course search query generator.

Your job is to determine the best query for a given atomic activity-search task using Weaviate hybrid search parameters.

## Available Parameters

- query
- alpha
- domain
- selectivity_est
- time_commitment_est
- limit

### Parameter Construction

1) query (str)
- Compose a concise, high-recall, comma-separated list of keyword-style phrases (avoid long sentences).
- If the request contains certain value or benefit cues ("career prep", "industry skills", etc.), include those tokens in the query
- Expand with intended meaning using relevant descriptors, topics, and keywords (≤ 10 words)
- If looking for a specific activity with a known name, use the activity name as the query.

2) alpha (float, 0.0-1.0)
- Balance between keyword (BM25) and semantic search.
- Heuristics:
  - Exact activity name lookups, alpha in [0.3-0.5].
  - Most queries, alpha in [0.6-0.8].
- Default if uncertain: 0.6.

3) limit (int)
- 1 for exact activity name lookups.
- 5 for most queries.
- If unspecified, choose 3-10 based on breadth (broader → larger).

**Important**: Do not infer any of the following parameters just from the name. Can be misleading and incorrect.
  - Can severely restrict search results by picking the wrong time commitment
  - Leave empty (None) if not explicitly mentioned in the task description.

4) domain (ValidDomain or None)
- Set only when the task explicitly calls for it.
  - E.g., "finance clubs" → domain="finance"
- If the topic could plausibly span multiple domains, leave domain unset and let the semantic query handle it.
- Valid domains: "consulting", "finance", "media", "policy", "research", "service", "sports", or "tech_product".

5) selectivity_est (ValidSelectivity or None)
- Set only when the task explicitly calls for it.
  - E.g., "open membership" → selectivity_est="open"
- Valid selectivities: "open", "application", "selective", or "tryout".

6) time_commitment_est (ValidTimeCommitment or None)
- Set only when the task explicitly calls for it.
  - E.g., "low commitment" → time_commitment_est="low"
- Valid time commitments: "low", "low_medium", "medium", "medium_high", "high", or "seasonal".

### Helpful Guidance

Query expansion guidance
- Prioritize near-synonyms and close conceptual neighbors; keep concise and comma-separated.
- Semantic search avoids the need for redundancies and near-synonyms; instead, focus on coverage of relevant topics and keywords.

Decision priorities
- Do not over-constrain activity_type, domain, selectivity_est, or time_commitment_est; prefer None when multiple options plausibly match.
- Choose alpha based on conceptual vs. exactness: more conceptual/semantic → higher alpha; more exact/keyworded → lower alpha.
- For exact activity name lookups, populate query with the activity name, set alpha low, and avoid additional filters.

## Examples

1) Task: Find clubs that offer hands-on experience in software engineering for tech product development
- Output:
  - query="software engineering technology programming", alpha=0.7
  - domain="tech_product"
  - selectivity_est=None
  - time_commitment_est=None
  - limit=5

2) Task: Find easy to join service organizations
- Output:
  - query="community service volunteering", alpha=0.7
  - domain=None
  - selectivity_est="open"
  - time_commitment_est=None
  - limit=5

3) Task: Find research opportunities related to AI or machine learning
- Output:
  - query="artificial intelligence machine learning", alpha=0.7
  - domain="research"
  - selectivity_est=None
  - time_commitment_est=None
  - limit=5

4) Task: Find low commitment finance clubs
- Output:
  - query="finance investing banking", alpha=0.7
  - domain="finance"
  - selectivity_est=None
  - time_commitment_est="low"
  - limit=5
"""


class ActivityQueryGenerator:
    """Query generator for activity searches with sync and async support."""

    def __init__(self, client, async_client=None):
        self.client = client
        self.async_client = async_client
        self.system_prompt = ACTIVITY_QUERY_GENERATION_PROMPT
        self.model = "gpt-4o-mini"

    def configure(self, system_prompt: str | None = None, model: str | None = None):
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if model is not None:
            self.model = model

    def generate(self, search_description: str) -> ActivitySearchParams:
        """Generate ActivitySearchParams from a search description (sync)."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": search_description},
        ]
        completion = self.client.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=ActivitySearchParams,
        )
        return completion.choices[0].message.parsed

    async def generate_async(self, search_description: str) -> ActivitySearchParams:
        """Generate ActivitySearchParams from a search description (async).

        Yields to the event loop during the API call for true parallel execution.
        """
        if self.async_client is None:
            raise ValueError(
                "async_client not configured. Pass async_client to __init__() to use generate_async()."
            )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": search_description},
        ]
        completion = await self.async_client.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=ActivitySearchParams,
        )
        return completion.choices[0].message.parsed


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    qg = ActivityQueryGenerator(client)

    descriptions = [
        "Find activties related to full-stack web dev, design, product management",
        "Easy to join community service clubs",
        "Research on topics related to machine learning or AI",
        "Competitive sports clubs",
        "Low commitment consulting or finance groups",
        "Find info on the 'DALI Lab'",
    ]

    for desc in descriptions:
        print(f"Description: {desc}")
        print(qg.generate(desc))
        print("-" * 80)
