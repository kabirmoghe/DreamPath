import re
import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from prompts import PREREQ_GRAMMAR_PROMPT
from prerequisite_parsing import parse_prereq_grammar, extract_best_course_path

# Manual extraction of prerequisites
filler_words = [
    'and', 'or', 'with', 'but', 'the', 'of', 'an', 'is',
    'students', 'who', 'have', 'has', 'not', 'taken', 'may',
    'take', 'permission', 'instructor', 'strong', 'background',
    'recommended', 'required', 'plus'
]

def preprocess_prereq_text(text):
    text = text.lower()

    # Remove periods only if followed by space or letter (not digits or part of 39.10)
    text = re.sub(r'\.(?=\s|[a-zA-Z])', ' ', text)

    # Remove other punctuation (except periods) — we preserve periods now
    text = re.sub(r"[^\w\s\.]", " ", text)

    # Remove full-word filler words first
    pattern = r'\b(?:' + '|'.join(map(re.escape, filler_words)) + r')\b'
    text = re.sub(pattern, ' ', text)

    # Remove embedded filler substrings
    for word in filler_words:
        text = text.replace(word, ' ')

    # Normalize whitespace
    return re.sub(r'\s+', ' ', text).strip()

def get_course_prereqs_manual(enhanced_course):
    # Extract relevant course fields
    course_code = enhanced_course['course_code']
    prereq_text = enhanced_course['prerequisites']
    dept_code = enhanced_course['dept']

    if not prereq_text or pd.isna(prereq_text):
        return []

    # Preprocess the prereq text
    prereq_text_cleaned = preprocess_prereq_text(prereq_text)
    print(f'prereq_text_cleaned: {prereq_text_cleaned}')

    course_extraction_expr = rf'\b{dept_code.lower()}[ \-]?\d{{1,3}}\b'
    matches = re.findall(course_extraction_expr, prereq_text_cleaned)

    # Normalize: remove space/hyphen, uppercase
    prereqs = list(set(re.sub(r'[\s\-]', '', match.upper()) for match in matches))
    prereqs = [prereq for prereq in prereqs if prereq != course_code]

    return prereqs

def preprocess_prereq_text(prereq_text):
    return re.sub(r'\.(?=[A-Za-z])', '; ', prereq_text)

# LLM-based extraction of prerequisites
def get_course_prereqs(enhanced_course):
    # Extract relevant course fields
    course_code = enhanced_course['course_code']
    prerequisites_text = preprocess_prereq_text(enhanced_course['prerequisites'])
    print(f'prerequisites_text: {prerequisites_text}')
    dept_code = enhanced_course['dept']

    if not prerequisites_text or pd.isna(prerequisites_text):
        return []
    
    # Produce grammar expression for prerequisites
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    prompt = PromptTemplate(
        input_variables=["prerequisite_text", "dept_code"],
        template=PREREQ_GRAMMAR_PROMPT
    )

    chain = prompt | llm
    prereq_grammar_response = chain.invoke({
        "prerequisite_text": prerequisites_text,
        "dept_code": dept_code
    })

    prereq_grammar = prereq_grammar_response.content if hasattr(prereq_grammar_response, 'content') else str(prereq_grammar_response)
    
    return prereq_grammar
    
    # # LLM-based extraction of prerequisites
    # llm = ChatOpenAI(temperature=0, model="gpt-4o")
    # prompt = PromptTemplate(
    #     input_variables=["prerequisite_text", "dept_code"],
    #     template=PREREQ_EXTRACT_PROMPT
    # )

    # # print(prompt.format(prerequisite_text=prerequisites_text, dept_code=dept_code))

    # chain = prompt | llm
    # response = chain.invoke({
    #     "prerequisite_text": prerequisites_text,
    #     "dept_code": dept_code
    # })

    # response_text = response.content if hasattr(response, 'content') else str(response)
    # prereqs = [prereq for prereq in response_text.split(',') if prereq != course_code]

    # return prereqs

if __name__ == "__main__":
    major_cleaned = 'computer_science'
    courses_with_descriptions_df = pd.read_csv(f'data/{major_cleaned}_courses_with_descriptions.csv')
    courses_with_descriptions = courses_with_descriptions_df.to_dict('records')

    print(len(courses_with_descriptions))

    for course in courses_with_descriptions[90:]:
        print(f'course code: {course["course_code"]}')
        print(f'raw prerequisites: {course["prerequisites"]}')

        if pd.isna(course['prerequisites']):
            continue

        output_grammar = get_course_prereqs(course)
        print(f'output prereq grammar: {output_grammar}')

        if output_grammar == '':
            print('[no prereqs]')
            continue

        try: 
            tree = parse_prereq_grammar(output_grammar)
            best_path = extract_best_course_path(tree, dept_prefix=course['dept'])
        except Exception as e:
            best_path = ['IP']
            print(f'Unrecognized prereq grammar: {output_grammar}')
        
        print(f'best path: {best_path}')

        print('--')

