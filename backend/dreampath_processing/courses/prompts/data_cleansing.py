# Extracting prerequisites for a given course
PREREQ_GRAMMAR_PROMPT = """You are an expert that converts a natural-language course prerequisite statement into a standardized logical grammar.

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
