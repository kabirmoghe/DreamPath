# Club information extraction prompts from documents
EXTRACT_CLUB_INFO_PROMPT = """
Given the club name "{club_name}" and the following document text, extract structured information:

{document_text}

Return a JSON object with these fields:
{{
    "name": "Full official club name",
    "contact_email": "Contact email if found",
    "description": "Detailed (approximately 3-sentence), third-person summary of the club's nature, mission, commitment,and example activities/projects."
}}

If information is not found, use empty string or empty array as appropriate. Do not invent any fields that are not present or fill in fields with information that is not present.

IMPORTANT: Return only the JSON object without any markdown formatting or code blocks.
"""

# Club name extraction prompt
PRODUCE_CLUB_NAME_PROMPT = """
Context:
    The following is the description of a club/organization/extracurricular activity:

    "{club_description}"

Task:
    Extract the name of the club/organization/extracurricular activity.

Return only the name of the club/organization/extracurricular activity.
"""

# Club tagging prompt
PRODUCE_CLUB_TAGS_PROMPT = """
Context:
    The following is the description of a club/organization/extracurricular activity:

    "{club_description}"

Task:
    Extract up to 8 discrete tags describing core domains, skills, and formats.


Return only a comma-separated list of the tags.
"""


# 1) From Student Interests → Club Themes
PARSE_CLUB_THEMES_FROM_INTERESTS_PROMPT = """
Context:
    A student majoring in {major} has the following interests on campus:

    "{college_interests}"

Task:
    What are 5 specific **club-related themes or activities** they should look for to explore these interests?
    These might include types of events (e.g., "hackathons," "networking mixers"), core skill areas (e.g., "data visualization," "public speaking"), or experiential formats (e.g., "research projects," "community outreach").

Return only a comma-separated list of the themes.
"""

# 2) From Post-Grad Goals → Club Prep Areas
PARSE_CLUB_THEMES_FOR_POST_GRAD_GOALS_PROMPT = """
Context:
    A student majoring in {major} plans to pursue this goal after graduation:

    "{post_grad_goal}"

Task:
    What are 5 **club-based experiences or focus areas** they should seek out now to prepare?
    Prioritize activities that build the skills, networks, or practical experience aligned with that goal (e.g., "case competitions" for consulting; "journal publication" for research).
    These might include specialized workshops, leadership roles, or collaborative project formats.

Return only a comma-separated list of the themes.
"""

# 3) From Long-Term Aspirations → Club Skillsets
PARSE_CLUB_THEMES_FOR_LONG_TERM_GOALS_PROMPT = """
Context:
    A student majoring in {major} has these long-term career aspirations:

    "{long_term_goal}"

Task:
    What are 5 **club skillsets or experiential formats** they should cultivate to support those aspirations?
    Focus on extracurricular contexts that map to strategic capabilities—like "entrepreneurship incubators," "mentorship programs," "international service trips," or "technical hackathons."

Return only a comma-separated list of the themes.
"""