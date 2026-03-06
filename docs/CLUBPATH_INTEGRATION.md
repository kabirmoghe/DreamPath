# ClubPath Integration Plan

DreamPath's clubs pillar — giving students a ranked, personalized list of clubs/activities — and
eventually a `ClubPath` with agent-driven updates.

---

## Roadmap

| Step | Description | Status |
|------|-------------|--------|
| 1 | Ingest club data → Weaviate `Activity` collection | ✅ Done |
| 2 | Extend search agent to find clubs | 🔴 Next |
| 3 | Make search result types generalizable (courses + clubs) | 🔴 Next |
| 4 | Add `ClubPath` to DreamPath agent (ranked list, no scheduling) | ⬜ Future |
| 5 | `ClubPath` agent — creates and handles ClubPath updates | ⬜ Future |

---

## Step 1: Weaviate Ingestion

### 1a. File Reorganization

Before adding club ingestion, align the ingestion layer to a consistent structure. Currently:

- `connect_local_with_openai()` is **copy-pasted** in both `ingest_weaviate_courses_v4.py` and
  `ingest_weaviate_majors_v4.py`
- Both ingestion scripts sit in `courses/data_retrieval/` even though majors aren't course data
- The `v4` version suffix in filenames is now meaningless (v4 is the current standard)
- Clubs have no natural ingestion home under the current structure

**Fix:** Extract a shared `weaviate/` module at the `dreampath_processing` level, mirroring how
`database/` is a shared PostgreSQL layer — not buried under a domain-specific directory.

#### Before

```
backend/
├── setup_weaviate.py
└── dreampath_processing/
    ├── courses/
    │   └── data_retrieval/
    │       ├── ingest_weaviate_courses_v4.py   ← defines connect_local_with_openai()
    │       ├── ingest_weaviate_majors_v4.py    ← duplicates connect_local_with_openai()
    │       └── weaviate_course_service.py      ← runtime singleton (stays here)
    └── clubs/
        └── data/
            └── activities.csv                  ← no ingestion script
```

#### After

```
backend/
├── setup_weaviate.py                           ← updated imports, adds ingest_clubs()
└── dreampath_processing/
    ├── weaviate/                               ← NEW shared ingestion layer
    │   ├── __init__.py
    │   ├── connection.py                       ← connect_local_with_openai() (single source)
    │   ├── utils.py                            ← safe_float, safe_int, safe_str
    │   ├── ingest_courses.py                   ← moved + renamed from ingest_weaviate_courses_v4.py
    │   ├── ingest_majors.py                    ← moved + renamed from ingest_weaviate_majors_v4.py
    │   └── ingest_clubs.py                     ← NEW
    ├── courses/
    │   └── data_retrieval/
    │       └── weaviate_course_service.py      ← unchanged (runtime service, not ingestion)
    └── clubs/
        └── data/
            └── activities.csv
```

**What changes:**
- Old `ingest_weaviate_courses_v4.py` and `ingest_weaviate_majors_v4.py` are deleted
- Their `ensure_*_collection()` functions move into the new files (no logic changes)
- `connect_local_with_openai()` extracted to `weaviate/connection.py` (one copy)
- `safe_float`, `safe_int`, `safe_str` extracted to `weaviate/utils.py`
- `setup_weaviate.py` updated to import from `dreampath_processing.weaviate.*`

**What doesn't change:**
- `weaviate_course_service.py` stays in `courses/data_retrieval/` — it's a runtime service, not an
  ingestion script; it imports, queries, and manages the connection at agent runtime
- `college_info_retrieval.py` stays in `courses/data_retrieval/` — course/major specific
- `CourseSearchClient` and search agent internals — untouched

#### Naming conventions established

| Pattern | Example |
|---------|---------|
| `ingest_{entity}.py` | `ingest_courses.py`, `ingest_clubs.py` |
| `ensure_{entity}_collection(client, recreate=False)` | `ensure_course_collection()`, `ensure_club_collection()` |
| `stable_{entity}_id(...)` | `stable_course_id(dept, code)` |
| Shared utilities | `weaviate/connection.py`, `weaviate/utils.py` |

---

### 1b. Club Weaviate Collection Schema

Collection name: **`Activity`** (generic enough to cover clubs, labs, research groups — all activity
types in the CSV).

Data sources: `activities.csv` (primary) + `activity_evidence.csv` (pre-joined at ingestion time,
see §1b-ii below).

#### Vectorized fields (semantic search target)

| Field | Source | Rationale |
|-------|--------|-----------|
| `display_name` | `activities.csv` | Name matching |
| `mission_synth` | `activities.csv` | Synthesized mission — best single description |
| `what_you_do_synth` | `activities.csv` | What members actually do |
| `who_its_for_synth` | `activities.csv` | Audience description |
| `skills_exposed` | `activities.csv` | Skills a student would develop (pipe-separated string) |
| `career_alignment` | `activities.csv` | Career paths this maps to (pipe-separated string) |
| `subtags` | `activities.csv` | Topic tags (pipe-separated string) |

> These fields are what the student's search query should match against. Together they cover
> "what is this activity", "why would I join", and "what do I get out of it".

#### Non-vectorized, filterable fields

| Field | Type | Source | Use |
|-------|------|--------|-----|
| `activity_slug` | TEXT | `activities.csv` | Unique stable ID (equivalent to `course_code`) |
| `activity_type` | TEXT | `activities.csv` | `club`, `lab`, `research_group` — top-level type filter |
| `domain` | TEXT | `activities.csv` | `tech_product`, `finance`, `sports`, `media`, `research`, etc. |
| `selectivity_est` | TEXT | `activities.csv` | `open`, `application`, `tryout`, `selective` |
| `time_commitment_est` | TEXT | `activities.csv` | `low`, `low_medium`, `medium`, `medium_high`, `high`, `seasonal` |
| `owner_type` | TEXT | `activities.csv` | `student_run`, `faculty_led`, `hybrid` |
| `campus_affiliation` | TEXT | `activities.csv` | Dartmouth, etc. |
| `data_confidence` | TEXT | derived from evidence | `high`, `medium`, `low` — see §1b-ii |
| `last_verified_utc` | DATE | `activities.csv` | Data freshness |

#### Display-only fields (stored, not filtered or vectorized)

| Field | Source |
|-------|--------|
| `short_name` | `activities.csv` |
| `how_to_join_synth` | `activities.csv` |
| `roles_exposed` | `activities.csv` |
| `source_of_truth_url` | `activities.csv` |
| `official_urls` | `activities.csv` (pipe-separated) |
| `evidence_citations` | derived from `activity_evidence.csv` — see §1b-ii |

#### Fields intentionally omitted

| Field | Reason |
|-------|--------|
| `mission_raw`, `description_raw` | Superseded by `*_synth` fields |
| `value_dims_json`, `type_specific_json` | Sparsely populated, not needed for search |
| `sentiment_available`, `sentiment_confidence` | Already rolled up into `data_confidence` |
| `public_presence_urls`, `contact_url` | Lower priority; `official_urls` covers it |

---

### 1b-ii. Evidence Pre-joining Strategy

`activity_evidence.csv` contains citation/provenance rows (2–6 per activity) with fields:
`source_type` (`official_site`, `reddit`, `blog`, `social`, `linkedin`), `signal_kind`
(`mission`, `how_to_join`, `career`, `selectivity`, `workload`), `reliability` (`high`, `medium`,
`low`), and a URL + title.

**Design decision: pre-join at ingestion time, not a separate Weaviate collection.**

A separate collection would require a second query on `activity_slug` after every search, and there
is no use case for querying evidence records independently (nobody searches "all reddit sources about
selectivity across all clubs"). The value is purely in surfacing provenance to the orchestrator and
finalizer so they can cite sources and evaluate data quality. The evidence rows are small (~6 per
activity) and static — denormalizing is the right call.

**Two fields added to each Activity object at ingestion time:**

**`evidence_citations` (TEXT, stored, not vectorized):**
A compact JSON string aggregating all evidence rows for that activity. Formatted for LLM
consumption so the finalizer can cite sources naturally:

```json
[
  {"source_type": "official_site", "title": "DALI Lab (official site)", "url": "https://dali.dartmouth.edu/", "signal_kind": "mission", "reliability": "high"},
  {"source_type": "reddit", "title": "What is the DALI Lab like at Dartmouth?", "url": "https://reddit.com/...", "signal_kind": "community", "reliability": "medium"}
]
```

The finalizer uses this to produce conclusions like: *"Based on the official DALI Lab site and a
Reddit discussion about student experience..."* rather than presenting recommendations without
grounding.

**`data_confidence` (TEXT, filterable):**
Derived from the evidence set — a single aggregate signal the orchestrator can use to filter or
flag low-confidence results:
- `high`: majority of sources are `reliability=high` official sites
- `medium`: mix of official + community sources
- `low`: primarily community/social sources with no official site evidence

Derivation logic at ingestion:
```python
def derive_data_confidence(evidence_rows: list[dict]) -> str:
    high_count = sum(1 for e in evidence_rows if e["reliability"] == "high")
    ratio = high_count / len(evidence_rows) if evidence_rows else 0
    if ratio >= 0.6:
        return "high"
    elif ratio >= 0.3:
        return "medium"
    else:
        return "low"
```

---

### 1c. Implementation — ✅ Complete

**Final structure:**
```
backend/dreampath_processing/weaviate/
├── __init__.py
├── connection.py       — connect_local_with_openai() (single source)
├── utils.py            — safe_float, safe_int, safe_str, parse_pipe_list
├── ingest_courses.py   — exports ensure_course_collection(), build_course_rows()
├── ingest_majors.py    — exports ensure_major_collection(), build_major_rows()
├── ingest_clubs.py     — exports ensure_activity_collection(), build_activity_rows(), load_evidence()
└── viewer.py           — Streamlit browser for any collection (dynamic, schema-aware)
```

Deleted: `courses/data_retrieval/ingest_weaviate_courses_v4.py`, `ingest_weaviate_majors_v4.py`.

`setup_weaviate.py` updated: imports from `dreampath_processing.weaviate.*`, calls
`ingest_activities()`, uses `build_course_rows()`/`build_major_rows()` (no more inline row loops).

All `ensure_*_collection()` functions use `vector_config=wc.Configure.Vectors.text2vec_openai()`
(not the deprecated `vectorizer_config=wc.Configure.Vectorizer.*`).

**Viewer:**
```bash
uv run streamlit run backend/dreampath_processing/weaviate/viewer.py
```
Collection picker, hybrid search, filterable property selector, schema expander, stats header.

---

## Steps 2–3: Generalize Search Agent + Add Activity Domain

### Step 2 (generalize search agent) — ✅ Complete

Branch: `search-agent-generalize` (off `search-agent`)

The search agent is now domain-agnostic via a **Strategy pattern**. All domain-specific logic
(search execution, prompts, rendering) lives in strategy implementations. The shared nodes
(orchestrator, tool_executor, summarize, context/building) are fully generic.

**Architecture:**
- `SearchStrategy` protocol in `strategy.py` — defines the interface each domain implements
- `get_strategy(domain)` resolves strategy from `state.domain` (simple dict lookup, lazy imports)
- `CourseSearchStrategy` in `strategies/course_strategy.py` — bundles query generator, prompts, rendering
- Base types in `types/base.py`: `SearchParams`, `SearchResult`, `SearchOutput`
- Course types in `types/course_types.py`: `CourseSearchParams`, `CourseSearchResult`, `CourseSearchOutput`
- Orchestrator emits `search_description: str` (natural language) — strategy internally calls
  a query generator to translate to domain-specific params, then executes the Weaviate search
- `OrchestratorResult` is domain-agnostic (single schema for all domains)
- Prompt sections injected via `strategy.get_orchestrator_prompt_sections()`

**Key design decision — query generator stays in the execution path:**
Regression testing showed that having the orchestrator emit params directly degraded quality
(no filters used, alpha stuck at 0.5, 65% more tokens for worse results). The query generator
adds real value by translating natural language descriptions into well-tuned search params.
Each domain strategy will house its own query generator.

**Post-generalization cleanup (also done):**
- Merged `render_result_compact` + `render_result_full` → single `render_result(compact=False)`
- Removed all `strategy=None` fallback paths (strategy is always required)
- Strategy resolved once per node, passed to helpers (not re-resolved per function)
- Fixed dead `task_search` param in `_build_tool_result_data` → passes `search_description` string
- Removed 500-char description truncation (was causing orchestrator to miss relevant content)
- Fixed QG prompt: "advanced" maps to `sort_by_level=True`, NOT `difficulty_classification=High`

### Step 3 (add activity domain) — 🔴 Next

**What needs to be built:**

1. **`types/activity_types.py`** — `ActivitySearchParams`, `ActivitySearchResult`, `ActivitySearchOutput`
   - Filters: `domain`, `activity_type`, `selectivity_est`, `time_commitment_est`
   - Result fields: `activity_slug` (→ id), `display_name` (→ title), `mission_synth` (→ description),
     skills_exposed, career_alignment, etc.
   - Enum literals derived from actual `activities.csv` distinct values

2. **`WeaviateActivityService`** — singleton mirroring `WeaviateCourseService`
   - `self.activity_collection = client.collections.get("Activity")`
   - `_build_filters(activity_type, domain, selectivity_est, time_commitment_est)`

3. **`ActivitySearchClient`** — mirrors `CourseSearchClient`
   - `hybrid_search(query, alpha, ...)` → `list[dict]`
   - `structured_hybrid_search(params: ActivitySearchParams)` → `ActivitySearchOutput`

4. **`ActivitySearchStrategy`** in `strategies/activity_strategy.py`
   - `execute_search()` — uses ActivitySearchClient + query generator
   - `get_orchestrator_prompt_sections()` — activity-specific prompts (different filters,
     different "good result" criteria, different examples)
   - `render_result()` / `render_result_for_summary()` — show domain, selectivity, time commitment,
     skills, mission instead of department, difficulty, prerequisites
   - `build_tool_result_entry()` — activity-specific dict
   - Own query generator with activity-specific prompt

5. **Wire into `get_strategy()`** — add `"activity": ActivitySearchStrategy` to the dict

6. **Wire into DreamPath orchestrator** — new route for activity search
   (analogous to `course_search_node` but passes `domain="activity"`)

---

## Steps 4–5: ClubPath Agent

> Future work — only relevant after Steps 1–3 are complete.

**Step 4 (ClubPath in DreamPath agent):**
- `ClubPath` = ranked list of activities (no scheduling, no prerequisites)
- New node: `club_search_node` — invokes search agent with `search_mode="activities"`
- New node: `club_path_node` — manages ClubPath state (add/remove/rerank)
- Orchestrator routing updated to include `club_search` and `club_path` routes
- Frontend: `ClubPath` display component (simpler than CoursePath — no term grid)

**Step 5 (ClubPath agent):**
- Analogous to `CoursePathAPIService` but stripped of scheduling logic
- Operations: `add_activity`, `remove_activity`, `rerank` (swap position)
- Confirmation flow: same button-driven Accept/Reject pattern as CoursePathOps
