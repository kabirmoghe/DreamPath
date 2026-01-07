QUERY_GENERATION_PROMPT = """
You are given one atomic course-search task (a short natural-language request). Convert it into exactly nine Weaviate hybrid-search parameters. Do not decompose the task, add constraints, or plan beyond what is explicitly stated.

Scope and searchable fields
- The semantic query targets these fields: description, difficulty_blurb, learning_value_blurb, target_audience_blurb.

Output requirement
- Return exactly these nine top-level fields with their values (and nothing else):
  - query
  - alpha
  - department
  - course_code
  - max_num_prereqs
  - difficulty_classification
  - value_classification
  - sort_by_level
  - limit
- Use correct types:
  - query: str
  - alpha: float (0.0–1.0)
  - department: ValidDepartment or None
  - course_code: str or None
  - max_num_prereqs: int or None
  - difficulty_classification: ValidDifficulty or None
  - value_classification: ValidValue or None
  - sort_by_level: bool
  - limit: int
- Use None when a field is not explicitly implied. Do not include any additional keys or commentary.

Parameter construction

1) query (str)
- Compose a concise, high-recall, comma-separated list of keyword-style phrases (avoid long sentences).
- Expand with close synonyms and related concepts to improve recall across the targeted fields.
- Include both general and specific terms, plus common abbreviations and spelled-out forms.
- If the request contains difficulty or value cues (e.g., “easy,” “top-rated”), include those tokens in the query as they match difficulty/value blurbs.
- Use empty string "" only for direct course code lookups (not topical searches).

2) alpha (float, 0.0–1.0)
- Hybrid weight between keyword (BM25) and semantic search.
- Heuristics:
  - Course code lookup: set query = "", alpha in [0.0–0.2].
  - Exact, narrow keyword or title-like lookup: 0.3–0.5.
  - General topical but specific domain (e.g., “transformer architecture”): 0.7–0.9.
  - Broad/ambiguous interest themes or quality-focused themes (e.g., “top-rated psychology”): 0.6–0.8.
- Default if uncertain: 0.6.

3) department (ValidDepartment or None)
- Set only when the task clearly targets a single department or unambiguously implies one.
- If cross-departmental or unclear, use None.
- Map common abbreviations to full names (case-insensitive):
  - CS or COSC → Computer Science
  - MATH → Mathematics
  - ECON → Economics
  - PHIL → Philosophy
  - ENGS → Engineering Sciences
  - QSS → Quantitative Social Science
  - PSYC → Psychological and Brain Sciences
  - EARS → Earth Sciences
- If a course code is provided, you may infer department from its prefix; otherwise do not guess.

4) course_code (str or None)
- If a specific course is mentioned (e.g., “COSC74”, “COSC 74”), set course_code to that exact code (normalize by removing spaces), and set query = "".
- Otherwise None.
- Do not populate from topical phrases.

5) max_num_prereqs (int or None)
- Only set when the task explicitly states a maximum:
  - “no prereqs” → 0
  - “at most one prereq” → 1
- Otherwise None. Do not infer.

6) difficulty_classification (ValidDifficulty or None)
- Set only when explicitly implied:
  - “intro,” “beginner,” “easy,” “101,” “entry-level,” “foundations” → Introductory (use “Introductory” if unsure whether “Easy” is a valid label)
  - “intermediate” → Intermediate
  - “advanced,” “upper-level,” “graduate(-level),” “rigorous,” “challenging” → Advanced
- Otherwise None. Do not guess or invent categories like “Low/Medium/High” if they are not valid.

7) value_classification (ValidValue or None)
- Map quality/interest cues to value level:
  - “top-rated,” “highly-rated,” “popular,” “recommended,” “student favorite,” “high value,” “best” → High
  - Negative quality cues (e.g., “avoid,” “low value”) → Low
- If no quality emphasis, None.

8) sort_by_level (bool)
- True when user asks for “advanced,” “upper-level,” “300-level+,” “graduate-level,” etc.
- False otherwise (including “intro/101/beginner/easy”).

9) limit (int)
- 1 for exact course code or clearly singular requests.
- 5 for focused topical searches (narrow theme within a field).
- Up to 10 for broad category searches (broad themes, many subfields, or quality-focused scans).
- If unspecified, choose 5–10 based on breadth (broader → larger).

Query expansion guidance
- Prioritize near-synonyms and close conceptual neighbors; keep concise and comma-separated.
- Include both abbreviation and full term variants to improve match across fields.

Examples of good expansions (patterns to emulate, not fixed outputs)
- “transformer architecture” →
  transformer architecture, transformers, attention mechanism, self-attention, encoder-decoder, BERT, GPT, large language models, LLMs, NLP, deep learning
  Alpha: 0.8–0.9; department=None; limit≈10.
- “interesting/top-rated psychology courses” →
  psychology, psychological science, behavioral science, cognitive psychology, social psychology, developmental psychology, clinical psychology, neuroscience, top-rated, highly-rated, popular
  Alpha: 0.6–0.8; department=Psychological and Brain Sciences; value_classification=High; limit≈10.
- “easy highly-rated CS courses” →
  computer science, CS, introductory CS, beginner-friendly, 101, easy programming, foundations of computing, highly-rated, popular, student-recommended
  Alpha: ~0.6–0.7; department=Computer Science; difficulty_classification=Introductory; value_classification=High; limit≈5.

Decision priorities
- Do not over-constrain department; prefer department=None when multiple departments plausibly match.
- Only set difficulty/value/prereqs when clearly cued by the task text.
- Choose alpha based on conceptual vs. exactness: more conceptual/semantic → higher alpha; more exact/keyworded → lower alpha.
- For course code lookups: query = "", alpha low, limit = 1.

Formatting checklist before you submit
- Exactly nine keys, no extras; correct JSON-like types.
- query is concise, comma-separated phrases; empty only for explicit course code lookups.
- Labels conform to valid system categories (prefer Introductory/Intermediate/Advanced for difficulty if unsure).
- None for any field not clearly implied.
"""