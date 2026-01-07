"""Golden dataset for query generation evaluation.

Contains 5 initial examples covering diverse query patterns and parameter extraction challenges.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from dreampath_processing.dreampath_agent.search_agent.search_types import CourseSearchParams

class GoldenExample(BaseModel):
    """Structure for a golden query example"""

    # Input
    search_description: str = Field(description="Atomic search description for query generation")

    # Expected output
    expected_params: CourseSearchParams = Field(description="Ground truth search parameters")

    # Metadata
    archetype: str = Field(description="Query pattern category")
    key_features: List[str] = Field(description="Extraction skills this tests")

    # Evaluation guidance
    intent_description: str = Field(description="What the user actually wants")
    evaluation_notes: str = Field(description="Specific criteria for evaluating this example")


# ============================================================================
# Golden Examples
# ============================================================================

GOLDEN_EXAMPLES = [

    # Example 1: Difficulty + Topic (Humanities)
    # Tests: Basic difficulty extraction from atomic search in non-STEM domain
    GoldenExample(
        search_description="Find easy introductory history courses",

        expected_params=CourseSearchParams(
            query="introductory history survey overview beginners",
            department="History",
            difficulty_classification="Low",
            alpha=0.6,
            limit=10
        ),

        archetype="difficulty_topic",
        key_features=["difficulty_extraction", "topic_expansion", "department_inference"],

        intent_description="Atomic task seeking beginner-friendly history courses",

        evaluation_notes="""
        This is an ATOMIC task from task tracking - humanities domain.

        Critical checks:
        - difficulty_classification MUST be 'Low'
        - department should be 'History'
        - query should expand 'history' with introductory terms:
          'introductory', 'survey', 'overview', 'beginners', 'foundations'
        - alpha should be 0.5-0.7 (semantic finds courses described as accessible)
        - value_classification should be None (no quality signal)

        Humanities-specific considerations:
        - Introductory history courses often described as "survey" or "overview"
        - Target audience blurbs mention "no prior background required"
        - Department scoping important (history spans many regions/periods)

        Should NOT:
        - Add specific history topics (ancient, modern, etc.) unless in task
        - Set value_classification without explicit quality signal
        - Use pure keyword search

        Task tracking scoped to "history" - DSPy expands with accessibility terms.
        """
    ),

    # Example 2: Technical Topic (Atomic)
    # Tests: Semantic query expansion for technical content
    GoldenExample(
        search_description="Find courses on transformer architecture",

        expected_params=CourseSearchParams(
            query="transformer attention mechanisms neural architecture sequence models",
            department="Computer Science",
            alpha=0.75,  # Heavy semantic (technical concepts are contextual)
            limit=10
        ),

        archetype="focused_technical_topic",
        key_features=["topic_expansion", "technical_semantic_search", "department_inference"],

        intent_description="Atomic task seeking courses covering transformer models and attention mechanisms",

        evaluation_notes="""
        This is an ATOMIC task from task tracking - already scoped to transformers.

        Critical checks:
        - query should expand 'transformers' to include related technical terms:
          'attention mechanisms', 'neural architecture', 'sequence models', 'self-attention'
        - department should be 'Computer Science' (technical AI/ML topic)
        - alpha should be >= 0.7 (technical concepts require semantic understanding)
        - difficulty_classification should be None (not specified)
        - value_classification should be None (no quality signal in task)

        Should NOT:
        - Try to decompose into sub-topics (task tracking already did this!)
        - Infer career goals (not in atomic search scope)
        - Search for "applications" unless task mentions it
        - Set value_classification without explicit quality signal ("highly-rated", "valuable", etc.)

        Task tracking narrowed ML careers → transformers. DSPy expands transformer → technical terms.
        """
    ),

    # Example 3: Multi-Constraint (Atomic)
    # Tests: Multiple filters in atomic search
    GoldenExample(
        search_description="Find easy highly-rated CS courses",

        expected_params=CourseSearchParams(
            query="computer science introductory programming fundamentals",
            department="Computer Science",
            difficulty_classification="Low",
            value_classification="High",  # "highly-rated" = explicit quality signal
            alpha=0.6,
            limit=10
        ),

        archetype="multi_constraint",
        key_features=["difficulty_extraction", "department_mapping", "value_extraction", "compound_query"],

        intent_description="Atomic task seeking beginner-friendly, highly-rated CS courses",

        evaluation_notes="""
        This is an ATOMIC task with multiple constraints already specified.

        Critical checks:
        - department MUST be 'Computer Science' (not 'CS' - normalize abbreviation)
        - difficulty_classification MUST be 'Low' (easy → Low)
        - value_classification MUST be 'High' ('highly-rated' = explicit quality signal)
        - query should expand 'CS' to computer science terms

        Edge cases handled correctly:
        - "CS" abbreviation → "Computer Science" full name
        - "easy" → difficulty_classification="Low"
        - "highly-rated" → value_classification="High"

        Should NOT:
        - Leave department as 'CS' (must use full name from ValidDepartment Literal)
        - Skip value_classification ("highly-rated" is explicit quality signal)
        - Use pure keyword search (semantic helps find well-reviewed courses)

        Task tracking already scoped this - DSPy extracts multiple constraints.
        """
    ),

    # Example 4: Prerequisite-Aware (Atomic)
    # Tests: Prerequisite filtering, difficulty vs. level vs. prerequisites
    GoldenExample(
        search_description="Find advanced math courses with minimal prerequisites",

        expected_params=CourseSearchParams(
            query="advanced mathematics upper-level topics",
            department="Mathematics",
            difficulty_classification="High",  # "advanced" often correlates with High difficulty
            max_num_prereqs=2,  # "minimal" = 1-2 prereqs
            sort_by_level=True,  # "advanced" suggests higher course numbers
            alpha=0.6,
            limit=10
        ),

        archetype="prerequisite_aware",
        key_features=["prerequisite_filtering", "difficulty_inference", "level_sorting", "constraint_disambiguation"],

        intent_description="Atomic task seeking upper-level math courses with few prerequisite chains (e.g., special topics, self-contained courses)",

        evaluation_notes="""
        This is an ATOMIC task with a constraint on prerequisites.

        Critical checks:
        - department MUST be 'Mathematics'
        - difficulty_classification should be 'High' (advanced content often difficult)
        - max_num_prereqs should be 1-3 (minimal but not zero - advanced courses need background)
        - sort_by_level should be True ("advanced" suggests higher course numbers like MATH70+)
        - query should include 'advanced', 'upper-level', 'topics'

        Important distinctions:
        - "advanced" → BOTH difficulty_classification="High" AND sort_by_level=True
        - Course level (number) ≠ difficulty always! (MATH11 can be hard, MATH70 can be easier)
        - "minimal prerequisites" → max_num_prereqs filter (independent of difficulty)
        - These are THREE independent dimensions: level, difficulty, prerequisites

        Should NOT:
        - Confuse course level with difficulty (they correlate but aren't the same!)
        - Set max_num_prereqs=0 (advanced courses need some foundation)
        - Skip sort_by_level (advanced suggests upper-level course numbers)
        - Set difficulty='Low' (advanced content is usually challenging)

        Note: sort_by_level sorts by course code number (MATH11 < MATH22 < MATH70).
        """
    ),

    # Example 5: Skill-Building (Atomic)
    # Tests: Semantic skill search, alpha tuning
    GoldenExample(
        search_description="Find courses on practical data visualization",

        expected_params=CourseSearchParams(
            query="data visualization practical hands-on projects tools",
            alpha=0.75,  # High semantic (practical application is contextual)
            limit=10
        ),

        archetype="skill_building",
        key_features=["semantic_skills", "alpha_tuning", "topic_expansion"],

        intent_description="Atomic task seeking courses focused on applied data visualization with hands-on projects/tools",

        evaluation_notes="""
        This is an ATOMIC task focused on a specific skill.

        Critical checks:
        - query MUST include 'data visualization' plus practical terms:
          'hands-on', 'practical', 'projects', 'tools', 'applied'
        - alpha should be >= 0.7 (practical skill focus is semantic, found in blurbs)
        - department can be None, 'Computer Science', or 'Mathematics' (all acceptable)
        - difficulty_classification should be None (not specified in task)
        - value_classification should be None ("practical" is course TYPE, not quality signal)

        Blurb targeting strategy:
        - learning_value_blurb: "practical", "hands-on", "projects", "tools", "visualization"
        - target_audience_blurb: "data analysis", "applied"
        - description: "data visualization", "graphics", "plotting"

        Should NOT:
        - Use low alpha (<0.6) - "practical" is semantic, requires contextual understanding
        - Search only titles (practical courses may not say "hands-on" in title)
        - Set difficulty filter (not specified - could be intro or advanced data viz)
        - Restrict to one department (data viz taught across CS, Math, Stats, Economics, etc.)
        - Set value_classification ("practical" describes course style, not rating/quality)

        Task tracking narrowed to "data visualization" - DSPy adds "practical" expansion.
        """
    ),

    # Example 6: Difficulty + Topic (Science) - SECOND EXAMPLE
    # Tests: Difficulty extraction in natural sciences
    GoldenExample(
        search_description="Find challenging physics courses",

        expected_params=CourseSearchParams(
            query="physics advanced rigorous theoretical",
            department="Physics and Astronomy",
            difficulty_classification="High",
            alpha=0.65,
            limit=10
        ),

        archetype="difficulty_topic",
        key_features=["difficulty_extraction", "topic_expansion", "department_mapping"],

        intent_description="Atomic task seeking challenging physics courses",

        evaluation_notes="""
        This is an ATOMIC task - natural sciences with difficulty signal.

        Critical checks:
        - difficulty_classification MUST be 'High' ("challenging" → High)
        - department should be 'Physics and Astronomy' (note full department name)
        - query should include 'physics' plus difficulty-related terms:
          'advanced', 'rigorous', 'theoretical', 'challenging'
        - alpha should be 0.6-0.7 (semantic for difficulty descriptors)
        - value_classification should be None (no quality signal)

        Should NOT:
        - Map "Physics" → must use "Physics and Astronomy" (full ValidDepartment name)
        - Set value_classification (challenging ≠ highly-rated)
        """
    ),

    # Example 7: Focused Technical Topic (Humanities) - SECOND EXAMPLE
    # Tests: Technical/theoretical concepts in humanities
    GoldenExample(
        search_description="Find courses on postcolonial theory",

        expected_params=CourseSearchParams(
            query="postcolonial theory critical perspectives decolonization imperialism",
            alpha=0.8,  # Very semantic - theoretical frameworks described contextually
            limit=10
        ),

        archetype="focused_technical_topic",
        key_features=["topic_expansion", "theoretical_semantic_search", "cross_department"],

        intent_description="Atomic task seeking courses on postcolonial theoretical frameworks",

        evaluation_notes="""
        This is an ATOMIC task - humanities theoretical topic.

        Critical checks:
        - query should expand 'postcolonial theory' to include related terms:
          'critical perspectives', 'decolonization', 'imperialism', 'subaltern studies'
        - department should be None (taught across English, Comp Lit, History, Anthropology)
        - alpha should be >= 0.75 (theoretical concepts highly semantic)
        - difficulty_classification should be None (not specified)
        - value_classification should be None (no quality signal)

        Humanities theoretical topics:
        - Often cross-listed across multiple departments
        - Described in blurbs rather than titles
        - Target audience mentions "critical thinking", "theoretical frameworks"

        Should NOT:
        - Restrict to single department (interdisciplinary theory)
        - Set difficulty (theory courses can be intro or advanced)
        """
    ),

    # Example 8: Multi-Constraint (Arts) - SECOND EXAMPLE
    # Tests: Multiple filters in arts domain
    GoldenExample(
        search_description="Find easy highly-rated studio art courses",

        expected_params=CourseSearchParams(
            query="studio art hands-on creative projects beginner-friendly",
            department="Studio Art",
            difficulty_classification="Low",
            value_classification="High",
            alpha=0.7,
            limit=10
        ),

        archetype="multi_constraint",
        key_features=["difficulty_extraction", "value_extraction", "arts_domain"],

        intent_description="Atomic task seeking beginner-friendly, highly-rated studio art courses",

        evaluation_notes="""
        This is an ATOMIC task - arts domain with multiple constraints.

        Critical checks:
        - department MUST be 'Studio Art'
        - difficulty_classification MUST be 'Low' ("easy" → Low)
        - value_classification MUST be 'High' ("highly-rated" → High)
        - query should include studio art terms:
          'hands-on', 'creative', 'projects', 'beginner-friendly', 'accessible'
        - alpha should be 0.65-0.75 (arts courses described experientially)

        Arts-specific patterns:
        - Studio art emphasizes hands-on, creative process
        - Learning value blurbs mention "creative expression", "skill development"
        - Difficulty often about technical skill vs. conceptual challenge

        Should NOT:
        - Skip value_classification ("highly-rated" is explicit quality signal)
        - Use low alpha (experiential learning is semantic)
        """
    ),

    # Example 9: Prerequisite-Aware (Language) - SECOND EXAMPLE
    # Tests: Prerequisite filtering in language courses
    GoldenExample(
        search_description="Find intermediate French with minimal prerequisites",

        expected_params=CourseSearchParams(
            query="French intermediate conversation culture",
            department="French and Italian Languages and Literatures",
            difficulty_classification="Medium",
            max_num_prereqs=1,
            alpha=0.6,
            limit=10
        ),

        archetype="prerequisite_aware",
        key_features=["prerequisite_filtering", "difficulty_inference", "language_domain"],

        intent_description="Atomic task seeking intermediate French courses accessible without many prerequisites",

        evaluation_notes="""
        This is an ATOMIC task - language domain with prerequisite constraint.

        Critical checks:
        - department should be 'French and Italian Languages and Literatures'
        - difficulty_classification should be 'Medium' ("intermediate" → Medium)
        - max_num_prereqs should be 1-2 ("minimal" but intermediate needs some background)
        - query should include 'French', 'intermediate', 'conversation', 'culture'
        - alpha should be 0.5-0.7

        Language course patterns:
        - Intermediate = Medium difficulty (not Low, not High)
        - "Minimal prerequisites" for intermediate = 1-2 prereqs (not 0!)
        - Language courses often focus on conversation, culture, literature

        Should NOT:
        - Set max_num_prereqs=0 (intermediate courses need some foundation)
        - Set difficulty='Low' (intermediate ≠ beginner)
        """
    ),

    # Example 10: Skill-Specific (Writing) - SECOND EXAMPLE
    # Tests: Skill-building in writing domain
    GoldenExample(
        search_description="Find courses on academic writing",

        expected_params=CourseSearchParams(
            query="academic writing research argumentation critical analysis",
            department="Institute for Writing and Rhetoric",
            alpha=0.75,
            limit=10
        ),

        archetype="skill_building",
        key_features=["skill_semantic_search", "writing_domain", "department_inference"],

        intent_description="Atomic task seeking courses focused on academic writing skills",

        evaluation_notes="""
        This is an ATOMIC task - writing skill development.

        Critical checks:
        - query should expand 'academic writing' to include:
          'research', 'argumentation', 'critical analysis', 'thesis development'
        - department should be 'Institute for Writing and Rhetoric'
        - alpha should be >= 0.7 (writing pedagogy is semantic)
        - difficulty_classification should be None (not specified)
        - value_classification should be None (skill type ≠ quality)

        Writing course patterns:
        - Learning value blurbs emphasize skill development
        - Target audience: students needing writing practice
        - Could also be in English department (cross-listed)

        Should NOT:
        - Set value_classification (writing skill focus ≠ rating signal)
        - Use low alpha (pedagogical approaches described semantically)
        """
    ),

    # Example 11: Cross-Disciplinary (Math for Social Science)
    # Tests: Cross-disciplinary application context
    GoldenExample(
        search_description="Find math courses for economics applications",

        expected_params=CourseSearchParams(
            query="mathematics economics applications econometrics statistics modeling",
            department="Mathematics",
            alpha=0.7,
            limit=10
        ),

        archetype="cross_disciplinary",
        key_features=["cross_discipline_search", "application_context", "department_inference"],

        intent_description="Atomic task seeking math courses with economics applications",

        evaluation_notes="""
        This is an ATOMIC task - cross-disciplinary (Math for Econ).

        Critical checks:
        - query should bridge both fields:
          'mathematics', 'economics', 'applications', 'econometrics', 'statistics', 'modeling'
        - department should be 'Mathematics' (seeking MATH courses)
        - alpha should be >= 0.65 (cross-disciplinary relevance is semantic)
        - difficulty_classification should be None (not specified)
        - value_classification should be None (no quality signal)

        Cross-disciplinary patterns:
        - "for economics" → adds application context, doesn't change department
        - Target audience blurbs mention "economics students", "applications"
        - Could set department=None to include cross-listed courses

        Should NOT:
        - Set department='Economics' (task asks for MATH courses)
        - Set value_classification without explicit quality signal
        """
    ),

    # Example 12: Cross-Disciplinary (CS for Biology)
    # Tests: STEM cross-disciplinary, reverse direction
    GoldenExample(
        search_description="Find computer science for biology research",

        expected_params=CourseSearchParams(
            query="computational biology bioinformatics algorithms genomics data analysis",
            alpha=0.75,
            limit=10
        ),

        archetype="cross_disciplinary",
        key_features=["cross_discipline_search", "interdisciplinary_inference"],

        intent_description="Atomic task seeking computational/CS courses for biology applications",

        evaluation_notes="""
        This is an ATOMIC task - cross-disciplinary (CS for Biology).

        Critical checks:
        - query should bridge both fields:
          'computational biology', 'bioinformatics', 'algorithms', 'genomics', 'data analysis'
        - department should be None (could be CS, Biological Sciences, or cross-listed)
        - alpha should be >= 0.7 (interdisciplinary relevance is semantic)
        - difficulty_classification should be None
        - value_classification should be None

        Interdisciplinary STEM:
        - "CS for biology" could live in either department
        - Better to leave department=None and let semantic search find courses
        - Could be Cognitive Science, QSS, or other interdisciplinary programs

        Should NOT:
        - Force department='Computer Science' (misses biology dept offerings)
        - Restrict too narrowly (interdisciplinary courses span departments)
        """
    ),

    # Example 13: Exploratory Within Domain (Philosophy)
    # Tests: Value-driven exploration within bounded domain
    GoldenExample(
        search_description="Find interesting philosophy courses",

        expected_params=CourseSearchParams(
            query="philosophy engaging thought-provoking diverse perspectives",
            department="Philosophy",
            value_classification="High",
            alpha=0.75,
            limit=10
        ),

        archetype="exploratory_within_domain",
        key_features=["exploratory_search", "value_inference", "semantic_quality"],

        intent_description="Atomic task seeking engaging, thought-provoking philosophy courses",

        evaluation_notes="""
        This is an ATOMIC exploratory task - bounded to philosophy.

        Critical checks:
        - query should expand 'interesting' to semantic quality terms:
          'engaging', 'thought-provoking', 'diverse perspectives', 'compelling'
        - department MUST be 'Philosophy' (bounded exploration)
        - value_classification should be 'High' ('interesting' = engagement = high value)
        - alpha should be >= 0.7 ('interesting' is subjective, found in blurbs)
        - difficulty_classification should be None

        Exploratory search strategy:
        - "Interesting" = value signal (engagement implies quality)
        - Not looking for specific topics (that would be focused_technical_topic)
        - Value filter surfaces courses students found engaging
        - Query terms help find intellectually stimulating courses

        Should NOT:
        - Skip value_classification ("interesting" = quality/engagement signal)
        - Add specific philosophy topics (existentialism, ethics, etc.)
        - Leave department as None (exploration is bounded to Philosophy)
        """
    ),

    # Example 14: Exploratory Within Domain (Music)
    # Tests: Arts domain exploration
    GoldenExample(
        search_description="Find engaging music courses",

        expected_params=CourseSearchParams(
            query="music engaging performance appreciation creative",
            department="Music",
            value_classification="High",
            alpha=0.75,
            limit=10
        ),

        archetype="exploratory_within_domain",
        key_features=["exploratory_search", "arts_domain", "value_inference"],

        intent_description="Atomic task seeking engaging music courses across topics",

        evaluation_notes="""
        This is an ATOMIC exploratory task - arts domain.

        Critical checks:
        - query should include 'music' plus engagement terms:
          'engaging', 'performance', 'appreciation', 'creative', 'hands-on'
        - department should be 'Music'
        - value_classification should be 'High' ("engaging" = quality signal)
        - alpha should be >= 0.7 (engagement described in blurbs)
        - difficulty_classification should be None

        Music course exploration:
        - Spans performance, theory, history, composition
        - "Engaging" signals student interest/value
        - Learning value blurbs emphasize creative expression, appreciation

        Should NOT:
        - Specify music sub-genre without signal in task
        - Skip value_classification ("engaging" is quality signal)
        """
    ),

    # Example 15: Value-Focused Topic (Humanities Broad)
    # Tests: Quality emphasis across broad humanities
    GoldenExample(
        search_description="Find highly-rated humanities courses",

        expected_params=CourseSearchParams(
            query="humanities liberal arts culture society history literature philosophy",
            value_classification="High",
            alpha=0.65,
            limit=10
        ),

        archetype="value_focused_topic",
        key_features=["value_extraction", "broad_topic_expansion", "quality_ranking"],

        intent_description="Atomic task seeking top-rated humanities courses across departments",

        evaluation_notes="""
        This is an ATOMIC task - explicit quality emphasis, broad humanities.

        Critical checks:
        - query should expand 'humanities' to include typical fields:
          'liberal arts', 'culture', 'society', 'history', 'literature', 'philosophy', 'art'
        - value_classification MUST be 'High' ("highly-rated" = explicit quality signal)
        - department should be None (humanities spans many departments)
        - alpha should be 0.6-0.7 (broad topic but value assessment is semantic)
        - difficulty_classification should be None

        Value-focused search:
        - "Highly-rated" → PRIMARY constraint is value_classification
        - Query expansion casts wide net across humanities
        - Value filter surfaces best courses across departments
        - Don't restrict to single department

        Should NOT:
        - Skip value_classification (CORE requirement)
        - Restrict to one department (humanities is cross-departmental)
        - Set difficulty (highly-rated courses exist at all levels)
        """
    ),

    # Example 16: Value-Focused Topic (Social Science)
    # Tests: Quality emphasis in social sciences
    GoldenExample(
        search_description="Find top-rated psychology courses",

        expected_params=CourseSearchParams(
            query="psychology cognitive behavioral neuroscience social",
            department="Psychological and Brain Sciences",
            value_classification="High",
            alpha=0.7,
            limit=10
        ),

        archetype="value_focused_topic",
        key_features=["value_extraction", "quality_ranking", "department_mapping"],

        intent_description="Atomic task seeking highest-rated psychology courses",

        evaluation_notes="""
        This is an ATOMIC task - quality focus within psychology.

        Critical checks:
        - query should expand 'psychology' to major subfields:
          'cognitive', 'behavioral', 'neuroscience', 'social', 'developmental'
        - department should be 'Psychological and Brain Sciences' (note full name)
        - value_classification MUST be 'High' ("top-rated" = quality signal)
        - alpha should be >= 0.65
        - difficulty_classification should be None

        Department naming:
        - "Psychology" → 'Psychological and Brain Sciences' (full ValidDepartment name)
        - Note plural "Sciences"

        Should NOT:
        - Use "Psychology" (must match ValidDepartment exactly)
        - Skip value_classification ("top-rated" is explicit)
        """
    ),

    # Example 17: Practical/Applied (Economics)
    # Tests: Applied skill focus in social sciences
    GoldenExample(
        search_description="Find applied econometrics courses",

        expected_params=CourseSearchParams(
            query="applied econometrics empirical analysis real-world data policy",
            department="Economics",
            alpha=0.75,
            limit=10
        ),

        archetype="practical_applied",
        key_features=["applied_focus", "topic_expansion", "social_science"],

        intent_description="Atomic task seeking applied/empirical econometrics courses",

        evaluation_notes="""
        This is an ATOMIC task - applied/practical focus in economics.

        Critical checks:
        - query should include 'applied', 'econometrics', 'empirical', 'real-world', 'data', 'policy'
        - department should be 'Economics'
        - alpha should be >= 0.7 (applied focus described in blurbs)
        - difficulty_classification should be None
        - value_classification should be None ("applied" is TYPE, not quality)

        Applied vs. theoretical:
        - "Applied" → query expansion, NOT value filter
        - Emphasizes empirical analysis, real-world data
        - Learning value blurbs mention "hands-on", "policy applications"

        Should NOT:
        - Set value_classification ("applied" ≠ quality signal)
        - Add "easy" or difficulty without signal
        """
    ),

    # Example 18: Practical/Applied (Studio Art)
    # Tests: Hands-on focus in arts
    GoldenExample(
        search_description="Find hands-on sculpture courses",

        expected_params=CourseSearchParams(
            query="sculpture hands-on studio practice three-dimensional materials",
            department="Studio Art",
            alpha=0.75,
            limit=10
        ),

        archetype="practical_applied",
        key_features=["applied_focus", "arts_domain", "topic_expansion"],

        intent_description="Atomic task seeking hands-on sculpture studio courses",

        evaluation_notes="""
        This is an ATOMIC task - hands-on arts practice.

        Critical checks:
        - query should include:
          'sculpture', 'hands-on', 'studio', 'practice', 'three-dimensional', 'materials'
        - department should be 'Studio Art'
        - alpha should be >= 0.7 (studio practice described experientially)
        - difficulty_classification should be None
        - value_classification should be None ("hands-on" is TYPE, not quality)

        Studio arts patterns:
        - Emphasis on making, practice, materials, process
        - Learning value blurbs mention creative expression, skill development
        - "Hands-on" describes pedagogical approach, not quality

        Should NOT:
        - Set value_classification (hands-on ≠ quality signal)
        - Conflate practical approach with difficulty level
        """
    ),

    # Example 19: Theoretical Topic (Philosophy)
    # Tests: Theoretical focus in humanities
    GoldenExample(
        search_description="Find courses on epistemology foundations",

        expected_params=CourseSearchParams(
            query="epistemology foundations knowledge theory justification",
            department="Philosophy",
            alpha=0.8,
            limit=10
        ),

        archetype="theoretical_topic",
        key_features=["theoretical_focus", "topic_expansion", "humanities"],

        intent_description="Atomic task seeking courses on epistemological foundations/theory",

        evaluation_notes="""
        This is an ATOMIC task - theoretical philosophy topic.

        Critical checks:
        - query should expand 'epistemology' to related terms:
          'foundations', 'knowledge', 'theory', 'justification', 'belief', 'skepticism'
        - department should be 'Philosophy'
        - alpha should be >= 0.75 (theoretical concepts highly semantic)
        - difficulty_classification should be None
        - value_classification should be None (theory ≠ quality)

        Theoretical humanities:
        - Emphasizes conceptual frameworks, not applications
        - "Foundations" signals theoretical rather than applied
        - Don't set value filter (theory courses can be niche but excellent)

        Should NOT:
        - Set value_classification (theoretical focus ≠ quality signal)
        - Add "applied" or "practical" (contradicts theoretical)
        """
    ),

    # Example 20: Theoretical Topic (Economics/Math) - SECOND EXAMPLE
    # Tests: Theoretical focus in social science/math domain
    GoldenExample(
        search_description="Find courses on game theory foundations",

        expected_params=CourseSearchParams(
            query="game theory theoretical foundations strategic decision Nash equilibrium",
            department="Economics",
            alpha=0.75,
            limit=10
        ),

        archetype="theoretical_topic",
        key_features=["theoretical_focus", "technical_semantic_search", "social_science"],

        intent_description="Atomic task seeking courses on theoretical game theory foundations",

        evaluation_notes="""
        This is an ATOMIC task - theoretical economics/math topic.

        Critical checks:
        - query should expand 'game theory' to include theoretical terms:
          'theoretical', 'foundations', 'strategic decision', 'Nash equilibrium', 'mechanism design'
        - department should be 'Economics' (primary home, though Math/Government also teach it)
        - alpha should be >= 0.7 (theoretical concepts require semantic understanding)
        - difficulty_classification should be None (not specified)
        - value_classification should be None (theory ≠ quality)

        Theoretical vs. applied distinction:
        - "Foundations" → emphasize theory, proofs, formal analysis
        - NOT looking for applications (would add 'applied', 'practical')
        - Don't set value filter (theory courses may be niche but excellent)
        - Semantic search finds courses emphasizing theoretical rigor

        Cross-listed potential:
        - Game theory taught in Economics, Mathematics, Government, Computer Science
        - Could set department=None, but Economics is primary home
        - QSS might also offer game theory courses

        Should NOT:
        - Add "applied" or "practical" to query (contradicts theoretical focus)
        - Set value_classification (theoretical topic ≠ quality signal)
        - Use low alpha (<0.6) - theoretical content described semantically in blurbs
        """
    ),

    # Example 21: Specific Course Code Lookup
    # Tests: Course information retrieval by code
    GoldenExample(
        search_description="Tell me about COSC74",

        expected_params=CourseSearchParams(
            query="",  # Empty query for exact lookup
            course_code="COSC74",
            alpha=0.0,  # Pure BM25 for exact course code match
            limit=1,
        ),

        archetype="specific_course_lookup",
        key_features=["course_code_extraction", "exact_lookup", "alpha_tuning"],

        intent_description="Atomic task requesting information about a specific course by code",

        evaluation_notes="""
        This is an ATOMIC course information lookup - not a search.

        Critical checks:
        - course_code MUST be 'COSC74' (exact match)
        - query should be "" (empty) or very minimal
        - alpha MUST be 0.0 (pure BM25 for exact course code match)
        - limit should be 1 (looking for one specific course)
        - department should be None (course_code is sufficient)
        - All other filters should be None

        Exact lookup pattern:
        - course_code is the PRIMARY identifier
        - Empty/minimal query (not searching semantically)
        - alpha=0.0 for pure keyword matching on course_code field
        - limit=1 (expecting single result)

        Should NOT:
        - Add semantic query terms (defeats exact lookup purpose)
        - Use alpha > 0.0 - this is exact match, not semantic search
        - Set department filter (redundant with course_code)
        - Set difficulty/value filters (just retrieving info)

        This pattern is for "tell me about X" or "what is X" queries.
        """
    ),

    # Example 22: Zero Prerequisites Filter
    # Tests: Strict prerequisite filtering (zero prereqs)
    GoldenExample(
        search_description="Find intro biology with no prerequisites",

        expected_params=CourseSearchParams(
            query="introductory biology fundamentals basics life sciences",
            department="Biological Sciences",
            difficulty_classification="Low",
            max_num_prereqs=0,  # Zero prerequisites
            alpha=0.6,
            limit=10
        ),

        archetype="prerequisite_aware",
        key_features=["zero_prereqs", "difficulty_extraction", "department_inference"],

        intent_description="Atomic task seeking introductory biology courses with zero prerequisites",

        evaluation_notes="""
        This is an ATOMIC task with strict zero prerequisite constraint.

        Critical checks:
        - max_num_prereqs MUST be 0 ("no prerequisites" = 0, not 1-2)
        - department should be 'Biological Sciences'
        - difficulty_classification should be 'Low' ("intro" → Low)
        - query should include 'introductory', 'biology', 'fundamentals', 'basics'
        - alpha should be 0.5-0.7
        - value_classification should be None

        Zero prereqs vs minimal prereqs:
        - "No prerequisites" → max_num_prereqs=0 (strict)
        - "Minimal prerequisites" (for intermediate) → max_num_prereqs=1-2
        - Intro courses often have 0 prereqs (unlike intermediate)

        Should NOT:
        - Set max_num_prereqs=1 ("no" means zero, not minimal)
        - Skip difficulty filter ("intro" signals Low difficulty)
        - Use department='Biology' (must use full ValidDepartment name)
        """
    ),

    # Example 23: Course Existence Check
    # Tests: Checking if a potentially non-existent course exists
    GoldenExample(
        search_description="Determine if MATH123 exists",

        expected_params=CourseSearchParams(
            query="",  # Empty for exact lookup
            course_code="MATH123",
            alpha=0.0,  # Pure BM25 for exact course code match
            limit=1,
            sort_by_level=False
        ),

        archetype="specific_course_lookup",
        key_features=["course_code_extraction", "existence_check", "exact_lookup"],

        intent_description="Atomic task checking if a specific course code exists in the catalog",

        evaluation_notes="""
        This is an ATOMIC course existence check.

        Critical checks:
        - course_code MUST be 'MATH123' (exact as specified)
        - query should be "" (empty)
        - alpha MUST be 0.0 (pure BM25 for exact match)
        - limit should be 1
        - sort_by_level should be False
        - All filters (department, difficulty, value, prereqs) should be None

        Existence check pattern:
        - Similar to specific course lookup (Example 21)
        - User wants to know if course exists (may not exist)
        - Use course_code for exact match
        - Empty query, alpha=0.0, limit=1

        Should NOT:
        - Add semantic query (defeats exact lookup)
        - Use alpha > 0.0 (this is exact code match)
        - Set department='Mathematics' (course_code is sufficient)
        - Add any other filters

        If course doesn't exist, tool will return empty results - that's expected.
        """
    ),
]


# ============================================================================
# Helper Functions
# ============================================================================

def get_examples_by_archetype(archetype: str) -> List[GoldenExample]:
    """Get all examples of a specific archetype"""
    return [ex for ex in GOLDEN_EXAMPLES if ex.archetype == archetype]


def get_examples_by_feature(feature: str) -> List[GoldenExample]:
    """Get all examples that test a specific feature"""
    return [ex for ex in GOLDEN_EXAMPLES if feature in ex.key_features]


def print_dataset_summary():
    """Print summary statistics of the golden dataset"""
    print(f"Total examples: {len(GOLDEN_EXAMPLES)}\n")

    print("Archetypes covered:")
    archetypes = set(ex.archetype for ex in GOLDEN_EXAMPLES)
    for arch in sorted(archetypes):
        count = len(get_examples_by_archetype(arch))
        print(f"  - {arch}: {count}")

    print("\nKey features tested:")
    all_features = set()
    for ex in GOLDEN_EXAMPLES:
        all_features.update(ex.key_features)
    for feat in sorted(all_features):
        count = len(get_examples_by_feature(feat))
        print(f"  - {feat}: {count}")

    print("\nParameter coverage:")
    dept_set = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.department is not None)
    course_code_set = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.course_code is not None)
    diff_set = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.difficulty_classification is not None)
    value_set = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.value_classification is not None)
    prereq_set = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.max_num_prereqs is not None)
    sort_set = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.sort_by_level is True)

    # Alpha distribution
    alpha_low = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.alpha <= 0.5)
    alpha_mid = sum(1 for ex in GOLDEN_EXAMPLES if 0.5 < ex.expected_params.alpha <= 0.7)
    alpha_high = sum(1 for ex in GOLDEN_EXAMPLES if ex.expected_params.alpha > 0.7)

    print(f"  - Department specified: {dept_set}/{len(GOLDEN_EXAMPLES)}")
    print(f"  - Course code specified: {course_code_set}/{len(GOLDEN_EXAMPLES)}")
    print(f"  - Difficulty classification set: {diff_set}/{len(GOLDEN_EXAMPLES)}")
    print(f"  - Value classification set: {value_set}/{len(GOLDEN_EXAMPLES)}")
    print(f"  - Prereq constraint set: {prereq_set}/{len(GOLDEN_EXAMPLES)}")
    print(f"  - Sort by level enabled: {sort_set}/{len(GOLDEN_EXAMPLES)}")
    print(f"\nAlpha distribution:")
    print(f"  - Low (≤0.5): {alpha_low} examples (exact/keyword-focused)")
    print(f"  - Mid (0.5-0.7): {alpha_mid} examples (hybrid)")
    print(f"  - High (>0.7): {alpha_high} examples (semantic-focused)")


# ============================================================================
# DSPy Dataset Format
# ============================================================================

def to_dspy_examples():
    """Convert to DSPy Example format for GEPA optimization

    Stores the full GoldenExample so the metric can access all fields
    for comprehensive evaluation.
    """
    import dspy

    examples = []
    for golden in GOLDEN_EXAMPLES:
        example = dspy.Example(
            search_description=golden.search_description,
            expected_params=golden.expected_params,
            archetype=golden.archetype,
            key_features=golden.key_features,
            intent_description=golden.intent_description,
            evaluation_notes=golden.evaluation_notes
        ).with_inputs("search_description")
        examples.append(example)

    return examples


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GOLDEN DATASET SUMMARY")
    print("=" * 60)
    print_dataset_summary()

    print("\n" + "=" * 60)
    print("EXAMPLE DETAILS")
    print("=" * 60)

    for i, example in enumerate(GOLDEN_EXAMPLES, 1):
        print(f"\n[Example {i}: {example.archetype}]")
        print(f"Search Description: {example.search_description}")
        print(f"Intent: {example.intent_description}")
        print(f"\nExpected Parameters:")
        params = example.expected_params
        print(f"  - query: '{params.query}'")
        print(f"  - alpha: {params.alpha}")
        print(f"  - department: {params.department}")
        print(f"  - course_code: {params.course_code}")
        print(f"  - max_num_prereqs: {params.max_num_prereqs}")
        print(f"  - difficulty_classification: {params.difficulty_classification}")
        print(f"  - value_classification: {params.value_classification}")
        print(f"  - sort_by_level: {params.sort_by_level}")
        print(f"  - limit: {params.limit}")
