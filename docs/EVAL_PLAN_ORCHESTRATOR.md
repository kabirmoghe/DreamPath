# DreamPath Orchestrator: Evaluation Plan

The main orchestrator is harder to evaluate than the search agent because it operates over multi-turn conversations with stateful context (profile, course path, conversation history) and routes to 7 different nodes. This plan outlines a practical path to rigorous evaluation.

## Core Challenge

The orchestrator makes **routing decisions** given:
- A conversation history (summary + recent messages)
- A current turn trace (tool calls/results from earlier in this turn)
- The student's profile and course path context
- A user message

It outputs: `{ route, reason, handoff, confidence }`

Evaluating this requires constructing realistic state contexts, which is significantly more complex than the search agent's single-goal input.

## Evaluation Layer 1: Routing Decision Evaluation (Isolated)

### What
Test the orchestrator's routing decisions in isolation by constructing state snapshots and checking that it selects the correct route.

### Test Case Design

Each test case is a **scenario** with:
- A `StudentProfile` (major, interests, goals, career)
- A `CoursePath` (or absence of one)
- A conversation history (summary + recent messages)
- A current turn trace (possibly with prior tool results)
- A user message
- **Expected route** and **expected handoff characteristics**

### Scenario Categories

#### A. First-Message Routing (no prior turn context)

| # | Scenario | User Message | Expected Route | Why |
|---|----------|-------------|----------------|-----|
| 1 | New profile, no course path | "Student completed their profile for the first time" | `rebuild_course_path` | Init flow — must build from scratch |
| 2 | Has profile + course path | "What does a software engineer do day to day?" | `finalize` | Pure brainstorming, no tools needed |
| 3 | Has profile + course path | "Can you find me some courses on machine learning?" | `course_search` | Explicit search request |
| 4 | Has profile + course path | "Add COSC74 to my plan" | `plan_builder` | Direct course path modification |
| 5 | Has profile + course path | "I've changed my mind — I want to major in Economics" | `modify_profile` | Profile change request |
| 6 | Has profile + course path | "I want to completely pivot from SWE to pre-med" | `rebuild_course_path` | Major upheaval |
| 7 | Has profile + course path | "What careers are available in tech?" | `career_search` | Career exploration |
| 8 | Has profile + course path | "Tell me about the FDE role" | `career_search` | Specific career lookup |

#### B. Mid-Turn Routing (after tool results in turn trace)

| # | Scenario | Turn Trace Contains | User Message | Expected Route |
|---|----------|-------------------|-------------|----------------|
| 9 | course_search returned results | Search results for ML courses | "Yes, add COSC78 and COGS21" | `plan_builder` |
| 10 | course_search returned results | Search results for ML courses | "Hmm, none of those look right. Can you search for NLP specifically?" | `course_search` |
| 11 | plan_builder created worklist | worklist=["add COSC78"] | (orchestrator evaluating) | `course_path` |
| 12 | course_path succeeded | Successful add of COSC78 | (orchestrator evaluating) | `finalize` |
| 13 | course_path failed (prereq issue) | Failed to add COSC89 due to prereqs | (orchestrator evaluating) | `plan_builder` (retry with different approach) |
| 14 | career_search returned data | FDE role data with capabilities | "That's great, can you find courses for those capabilities?" | `course_search` (with translated handoff) |

#### C. Ambiguity & Edge Cases

| # | Scenario | User Message | Expected Route | Why |
|---|----------|-------------|----------------|-----|
| 15 | Has course path | "Make some changes to my plan" | `finalize` | Ambiguous — should clarify first |
| 16 | Has course path | "I'm not sure what I want to do after college" | `finalize` or `career_search` | Brainstorming or career exploration |
| 17 | Has course path | "Can you help me?" | `finalize` | Too vague to route elsewhere |
| 18 | Has course path, career discussed | "Let's do it" (after discussing a career pivot) | Context-dependent | Must interpret "it" from conversation |

### Implementation Approach

**State Construction:**
```python
@dataclass
class OrchestratorTestCase:
    name: str
    student_profile: StudentProfile
    course_path: CoursePath | None
    summary: str              # Conversation summary
    turn_messages: list[dict] # Current turn trace
    user_message: str
    expected_route: str
    expected_handoff_keywords: list[str]  # Soft check on handoff content
    acceptable_routes: list[str]  # Alternate acceptable routes
```

**Execution:**
1. Construct a `DreamPathAgentState` from the test case
2. Call `decide_next_route(state, config)` directly (bypass the full graph)
3. Compare `decision.route` against `expected_route` and `acceptable_routes`
4. Check handoff content for expected keywords
5. Evaluate confidence level

**Key challenge:** Constructing realistic `CoursePath` objects and conversation histories. Options:
- **Snapshot approach**: Run the real agent, serialize states at key points, annotate expected routes
- **Synthetic approach**: Build minimal but valid state objects programmatically
- **Hybrid**: Use real agent outputs for complex states, synthetic for simple ones

### Metrics
- **Route accuracy**: % of test cases where agent selects expected route (or acceptable alternative)
- **Handoff quality**: % of handoffs containing expected keywords
- **Confidence calibration**: Are high-confidence decisions more likely to be correct?
- **Ambiguity handling**: Does the agent route to `finalize` (to clarify) when intent is unclear?

## Evaluation Layer 2: Trajectory Evaluation (Multi-Step)

### What
Evaluate complete multi-step trajectories: starting from a user message, does the orchestrator produce a reasonable sequence of routing decisions to accomplish the goal?

### Approach: Golden Trajectories

Define expected routing sequences for common user scenarios:

```python
class TrajectoryTestCase:
    name: str
    student_profile: StudentProfile
    course_path: CoursePath | None
    user_message: str
    expected_trajectory: list[str]  # e.g., ["course_search", "plan_builder", "course_path", "finalize"]
    acceptable_variations: list[list[str]]  # Alternative valid trajectories
```

**Example trajectories:**

1. **Simple course addition:**
   - User: "Add a machine learning course to my plan"
   - Expected: `course_search → plan_builder → course_path → finalize`
   - Acceptable: `course_search → finalize → plan_builder → course_path → finalize` (if agent presents findings first)

2. **Career-driven course search:**
   - User: "I want to be a data scientist — find relevant courses"
   - Expected: `career_search → course_search → finalize`
   - Acceptable: `course_search → finalize` (if agent knows enough about data science without career data)

3. **Profile change + rebuild:**
   - User: "I've decided to switch to Economics and rebuild my course plan"
   - Expected: `modify_profile → rebuild_course_path → finalize`

4. **Course path fix after prereq failure:**
   - User: "Add COSC89 to term 5"
   - Expected: `plan_builder → course_path → plan_builder → course_path → finalize` (if first attempt fails)

### Implementation: Mocked Sub-Nodes

The key insight: **mock the sub-nodes** to return deterministic outputs, so you can evaluate the orchestrator's routing decisions without actually executing searches/scheduling.

```python
# Pseudo-code for trajectory evaluation
async def evaluate_trajectory(test_case, mock_outputs):
    state = build_initial_state(test_case)
    trajectory = []

    for step in range(max_steps):
        decision = await decide_next_route(state, config)
        trajectory.append(decision.route)

        if decision.route == "finalize":
            break

        # Apply mock output for this node
        mock_output = mock_outputs.get(decision.route)
        state = apply_mock_output(state, decision.route, mock_output)

    return compare_trajectories(trajectory, test_case.expected_trajectory)
```

**Mock output library:**
- `course_search` → returns predefined search results (e.g., 3 ML courses)
- `plan_builder` → returns predefined worklist (e.g., ["add COSC78"])
- `course_path` → returns success or failure (configurable)
- `modify_profile` → returns modified profile
- `career_search` → returns predefined career data
- `rebuild_course_path` → returns rebuilt course path

### Metrics
- **Trajectory match rate**: % of test cases where actual trajectory matches expected (or acceptable variation)
- **Trajectory length**: avg steps to completion (shorter is generally better)
- **Recovery rate**: when a step fails (e.g., course_path prereq failure), does the agent recover?
- **Over-routing**: does the agent visit unnecessary nodes?
- **Under-routing**: does the agent skip necessary steps (e.g., searching before adding)?

## Evaluation Layer 3: Handoff Quality (Content Eval)

### What
Beyond correct routing, evaluate whether the **handoff content** gives the target node enough information to succeed.

### Approach
For each routing decision that includes a handoff, evaluate:

1. **Completeness**: Does the handoff include all information the target node needs?
   - `course_search` handoff: Does it describe what to search for clearly?
   - `plan_builder` handoff: Does it specify which courses and where?
   - `modify_profile` handoff: Does it specify which fields to change?
   - `rebuild_course_path` handoff: Does it explain the goal and what to keep/change?

2. **Accuracy**: Does the handoff correctly reflect the user's intent?
   - No invented course codes
   - No assumed preferences not stated by the user
   - Career capabilities translated to academic language (not verbatim)

3. **Conciseness**: Is the handoff focused, or does it contain irrelevant detail?

### Implementation: LLM Judge

```python
class HandoffEvaluation(BaseModel):
    completeness: float       # 0-1: does it contain all necessary info?
    accuracy: float           # 0-1: does it match user intent?
    conciseness: float        # 0-1: is it focused?
    career_translation: float # 0-1: are career terms translated? (only for career→search)
    feedback: str
```

Feed the LLM judge: user message + conversation context + routing decision + handoff → score.

### Metrics
- Per-route-type handoff quality scores
- Career capability translation accuracy (specific to career_search → course_search flow)
- Handoff length distribution (too short = missing info, too long = unfocused)

## Evaluation Layer 4: Course Path Operation Correctness

### What
Evaluate whether the orchestrator correctly handles complex course path scenarios with prerequisite chains, term conflicts, and scheduling constraints.

### Hardcoded Scenarios

Create course paths with known tricky relationships:

1. **Linear prereq chain**: A → B → C → D, student wants to add D but hasn't taken A
   - Expected: orchestrator recognizes the chain and suggests adding A first (or routes to plan_builder with full chain)

2. **Term capacity**: Term 5 is full (4 courses), student wants to add another course there
   - Expected: orchestrator should note the constraint and suggest term alternatives or removal

3. **Prereq conflict**: Student wants to swap course X for Y, but Y is a prereq for Z which is already scheduled
   - Expected: orchestrator should recognize Z depends on Y and handle accordingly

4. **Cross-term dependency**: Moving course from term 3 to term 6 breaks a prereq chain for term 4
   - Expected: orchestrator should detect the dependency violation

### Implementation
- Build synthetic CoursePaths with these exact structures
- Present modification requests to the orchestrator
- Evaluate whether the handoff to plan_builder captures the constraints correctly
- Check whether the agent recovers when course_path reports failures

### Metrics
- Prereq chain awareness rate
- Recovery strategy quality (how does the agent respond to course_path failures?)
- Term constraint recognition accuracy

## Evaluation Layer 5: End-to-End Integration Tests

### What
Full agent runs (real sub-nodes, real data) with predetermined user scripts.

### Approach
Each test is a **conversation script** — a sequence of user messages with expected outcomes at each step:

```python
class ConversationScript:
    name: str
    initial_profile: StudentProfile
    initial_course_path: CoursePath | None
    turns: list[ConversationTurn]

class ConversationTurn:
    user_message: str
    expected_state_changes: dict  # e.g., {"courses_added": ["COSC78"], "profile_changed": True}
    expected_nodes_visited: list[str]
    max_orchestrator_steps: int
```

**Example scripts:**

1. **Happy path: search + add**
   - Turn 1: "Find machine learning courses" → expect course_search results
   - Turn 2: "Add COSC78" → expect plan_builder + course_path + course added

2. **Career exploration → course adjustment**
   - Turn 1: "What does a backend engineer do?" → expect career data
   - Turn 2: "Find courses for those skills" → expect course_search with translated capabilities
   - Turn 3: "Add the top two" → expect plan_builder + course_path

3. **Profile pivot + rebuild**
   - Turn 1: "I want to switch from CS to Economics" → expect clarification or modify_profile
   - Turn 2: "Yes, rebuild everything" → expect rebuild_course_path

### Key Considerations
- These tests are expensive (real LLM calls, real Weaviate queries)
- Run infrequently (weekly or before major releases)
- Focus on 5-10 critical conversation paths
- Evaluate final state (profile correct? course path valid? courses actually scheduled?)

## Priority Order

1. **Layer 1: Routing Decision Eval** — highest ROI, isolated, deterministic expectations
2. **Layer 3: Handoff Quality** — pairs naturally with Layer 1 (same test cases)
3. **Layer 2: Trajectory Eval with Mocks** — medium effort, tests multi-step reasoning
4. **Layer 4: Course Path Operation Correctness** — targeted, addresses known complexity
5. **Layer 5: E2E Integration** — most realistic but most expensive, build last

## Implementation Roadmap

### Phase 1 (1-2 weeks): Routing Decision Eval
- Build 20-30 routing test cases across categories A, B, C
- Create state construction utilities (StudentProfile + CoursePath builders)
- Build runner that calls `decide_next_route()` directly
- Report route accuracy by category

### Phase 2 (1-2 weeks): Handoff + Trajectory
- Add LLM judge for handoff quality
- Build mock sub-node library
- Create 10-15 trajectory test cases
- Build trajectory comparison logic

### Phase 3 (2-3 weeks): Course Path Operations + E2E
- Build synthetic CoursePaths with known constraint structures
- Create 5-10 conversation scripts
- Build multi-turn test runner with state validation
- Run against real agent with real data
