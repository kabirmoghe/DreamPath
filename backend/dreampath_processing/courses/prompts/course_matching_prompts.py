# ================================
# TOPIC-LEVEL COURSE MATCHING PROMPTS
# ================================

# Extracting small set of refined topics from single topic for querying
SUBTOPIC_EXTRACTION_PROMPT = """
Context:
    A student has expressed interest in exploring the following topic through college courses: "{topic}".

Task:
    Extract the 3 most relevant subtopics from the topic that are likely to appear in college course descriptions or syllabi.
    These might include subfields, tools, theories, or methodologies.

Return only a comma-separated list of the subtopics.
"""


# ================================
# PARAMETER-LEVEL COURSE MATCHING PROMPTS
# ================================

# Extracting topics from student interests
PARSE_TOPICS_FOR_STUDENT_INTERESTS_PROMPT = """
Context:
    A student majoring in {major} has expressed interest in the following topics during college:

    "{college_interests}"

Task:
    What are 5 specific technical or academic topics they should consider studying in college to support these interests? Take into account that certain interests may be independent of their major if implied by the student.
    Focus on topics that are likely to appear in college course descriptions or syllabi.
    These might include subfields, tools, theories, or methodologies.

Return only a comma-separated list of the topics.
"""

# Extracting topics from post-graduation goals
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

# Extracting topics from long-term career aspirations
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

# ================================
# COURSE DATA PROCESSING PROMPTS
# ================================

# Extracting departments for a given topic
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
    'Womens Gender & Sexuality Studies'

Task:
    Given the academic topic: "{topic}", return the **most relevant** department(s) from the list above that are likely to offer courses covering this topic.

    Return **no more than 3 departments**, and **only include multiple departments if they are clearly relevant**.
    It is perfectly acceptable—and often preferable—to return just 1 or 2 departments if the topic is specialized.

    Only include departments from the provided list.
    Return a comma-separated list of department names, with department names surrounded by single quotes.
"""

# Extracting prerequisites for a given course
PREREQ_GRAMMAR_PROMPT = """
Context:
    You are converting a natural-language course prerequisite statement into a standardized logical grammar.

    Here is the input prerequisite text for a course that belongs to the "{dept_code}" department:

"{prerequisite_text}"

Instructions:
    - Translate the text into a grammar format that uses AND, OR, and parentheses
    - Use course codes like COSC10 or MATH3 directly in the output; 
    - Use "IP" to indicate Instructor Permission
    - Use "AP" to indicate Advanced Placement credit
    - Use "LP" to indicate local placement or departmental placement tests
    - Only include course codes, IP, AP, or LP if they are **explicitly mentioned in the input text**. Do not infer or guess course codes based on context or common knowledge (e.g., do not assume “linear algebra” means MATH22).
    - Use parentheses to group OR/AND conditions as needed
    - Do not include recommended or optional courses
    - Normalize department abbreviations to the "{dept_code}" department (e.g., "CS31" becomes "COSC31")
    - Only use the following tokens: department course codes, IP, AP, and LP
    - If the text describes a student being allowed to enroll without a course due to instructor permission or placement, express that using IP or LP — do not use NOT
    - Avoid general phrases like "strong background," "approval of the instructor," or "equivalent experience" — instead, simplify those to IP or LP if appropriate

Examples:
    1. "COSC 22 and either COSC 24 or COSC 23.01" → COSC22 AND (COSC24 OR COSC23.01)
    2. "COSC 25.01 and Instructor Permission is required" → COSC25.01 AND IP
    3. "Math 3 and COSC 10; or Math 3, Instructor Permission, and either COSC 1 or ENGS 20"
       → (MATH3 AND COSC10) OR ((MATH3 AND IP) AND (COSC1 OR ENGS20))
    4. "Students without COSC30 may enroll with instructor permission." → COSC30 OR IP
    5. "Students may enroll with local placement or AP credit." → AP OR LP
    6. "COSC 1,COSC 10,MATH 8" → COSC1 AND COSC10 AND MATH8

Return only the grammar expression. If there are no required prerequisites, return a blank string (i.e., "").

"""
