PARSE_TOPICS_FOR_STUDENT_INTERESTS_PROMPT = """
Context:
    A student majoring in {major} has expressed interest in the following topics during college:

    "{college_interests}"

Task:
    What are 5 specific technical or academic topics they should consider studying in college to support these interests?
    Prioritize topics typically covered within the {major} department, but include other topics from related disciplines *if they would meaningfully supplement* the student's preparation.
    Focus on topics that are likely to appear in college course descriptions or syllabi.
    These might include subfields, tools, theories, or methodologies.

Return only a comma-separated list of the topics.
"""

PARSE_TOPICS_FOR_POST_GRAD_GOAL_PROMPT = """
Context:
    A student majoring in {major} has expressed interest in pursuing the following goal after graduating:

    "{post_grad_goal}"

Task:
    What are 5 specific technical or academic topics they should consider studying in college to support this post-graduation goal?
    Prioritize topics typically covered within the {major} department, but include other topics from related disciplines *if they would meaningfully supplement* the student's preparation.
    Focus on topics that are likely to appear in college course descriptions or syllabi.
    These might include subfields, tools, theories, or methodologies.

Return only a comma-separated list of the topics.
"""

PARSE_TOPICS_FOR_LONG_TERM_GOAL_PROMPT = """
Context:
    A student majoring in {major} has expressed interest in the following long-term career aspirations:

    "{long_term_goal}"

Task:
    What are 5 specific technical or academic topics they should consider studying in college to support these aspirations?
    Prioritize topics typically covered within the {major} department, but include other topics from related disciplines *if they would meaningfully supplement* the student's preparation.
    Focus on topics that are likely to appear in college course descriptions or syllabi.
    These might include subfields, tools, theories, or methodologies.

Return only a comma-separated list of the topics.
"""

DEPARTMENT_MATCHING_PROMPT = """
Context:
    The following are departments available at Dartmouth College (separated by commas):

    'African and African American Studies', 'Anthropology',
    'Art History', 'Asian Societies, Cultures, and Languages',
    'Biological Sciences', 'Biological Chemistry',
    'Biophysical Chemistry', 'Chemistry', 'Ancient History',
    'Classical Archaeology', 'Classical Languages and Literatures',
    'Classical Studies', 'Cognitive Science', 'Comparative Literature',
    'Computer Science', 'Earth Sciences', 'Russian',
    'Russian Area Studies', 'Economics',
    'Biomedical Engineering Sciences', 'Engineering Physics',
    'Engineering Sciences', 'Engineering Sciences', 'English',
    'Film and Media Studies', 'French', 'French Studies', 'Italian',
    'Italian Studies', 'Romance Languages',
    'Biomedical Engineering Sciences', 'Geography', 'German Studies',
    'Government', 'History',
    'Latin American, Latino, and Caribbean Studies', 'Linguistics',
    'Mathematics', 'Music', 'Native American Studies', 'Philosophy',
    'Astronomy', 'Physics', 'Neuroscience', 'Psychology',
    'Quantitative Social Science', 'Religion', 'Sociology',
    'Hispanic Studies', 'Romance Studies', 'Studio Art', 'Theater',
    "Womens Gender & Sexuality Studies"

Task:
    Given the academic topic: "{topic}", return up to **3 departments** from the list above that are most likely to offer courses covering this topic.

    Only include departments from the provided list.
    Return a comma-separated list of department names.
"""