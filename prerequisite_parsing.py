from lark import Lark, Transformer
import re
import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from course_matching_prompts import PREREQ_GRAMMAR_PROMPT

# Grammar and transformer for parsing prereqs
prereq_grammar = """
     ?start: expr

     ?expr: expr "OR" term   -> or_expr
          | term

     ?term: term "AND" factor   -> and_expr
          | factor

     ?factor: "(" expr ")"
          | ITEM

     // Define what can be considered a course or placement item
     ITEM: COURSE | ALIAS
     COURSE: /[A-Z]{2,}[0-9]+(\\.[0-9]+)?/
     ALIAS: "IP" | "AP" | "LP"
     | /[a-z_]+/

     %import common.WS
     %ignore WS
"""  

class CourseExprTransformer(Transformer):
    def ITEM(self, token):
        return str(token)

    def and_expr(self, args):
        return ('AND', args)

    def or_expr(self, args):
        return ('OR', args)

    def expr(self, args):
        return args[0]

    def term(self, args):
        return args[0]

    def factor(self, args):
        return args[0]

def parse_prereq_grammar(prereq_text_standardized):
    prereq_parser = Lark(prereq_grammar)
    prereq_tree = prereq_parser.parse(prereq_text_standardized)

    friendly_prereq_tree = CourseExprTransformer().transform(prereq_tree)

    return friendly_prereq_tree

def extract_best_prereq_path(prereq_tree, dept_prefix):
    def is_real_course(course):
        return course not in ("IP", "AP", "LP")

    def is_alt_credit(course):
        return course in ("AP", "LP")

    def is_ip(course):
        return course == "IP"

    def is_dept_course(course):
        return course.startswith(dept_prefix)

    def score(path):
        ip_penalty = sum(1 for c in path if is_ip(c))
        alt_penalty = sum(1 for c in path if is_alt_credit(c))
        non_dept_penalty = sum(1 for c in path if is_real_course(c) and not is_dept_course(c))
        length_penalty = len(path)
        return (ip_penalty, alt_penalty, non_dept_penalty, length_penalty)

    def helper(node):
        if isinstance(node, str):
            if is_real_course(node) or is_alt_credit(node) or is_ip(node):
                return [node]
            return []

        op, args = node

        if op == "AND":
            path = []
            for arg in args:
                path += helper(arg)
            return path

        elif op == "OR":
            candidate_paths = [helper(arg) for arg in args]
            candidate_paths = [p for p in candidate_paths if p]
            if not candidate_paths:
                return []
            return min(candidate_paths, key=score)

        return []

    return helper(prereq_tree)

# Preprocess the prerequisites text for LLM to pick up on separators
def preprocess_prereq_text(prereq_text):
    return re.sub(r'\.(?=[A-Za-z])', '; ', prereq_text)

# LLM-based extraction of prerequisites
def get_course_formatted_prereqs(enhanced_course):
    # Extract relevant course fields
    prerequisites_text_raw = enhanced_course['prerequisites']
    dept_code = enhanced_course['dept']

    if not prerequisites_text_raw or pd.isna(prerequisites_text_raw):
        return ''
    
    prerequisites_text = preprocess_prereq_text(prerequisites_text_raw)
    
    # Produce grammar expression for prerequisites
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    prompt = PromptTemplate(
        input_variables=["prerequisite_text", "dept_code"],
        template=PREREQ_GRAMMAR_PROMPT
    )

    chain = prompt | llm
    formatted_prereqs_response = chain.invoke({
        "prerequisite_text": prerequisites_text,
        "dept_code": dept_code
    })

    formatted_prereqs = formatted_prereqs_response.content if hasattr(formatted_prereqs_response, 'content') else str(formatted_prereqs_response)
    
    return formatted_prereqs

def get_course_prereqs(enhanced_course, overwrite=False):
    # To avoid re-running, check if best_prereq_path is already in the course
    if not overwrite and 'best_prereq_path' in enhanced_course:
        print(f'Using cached prereq path for {enhanced_course["course_code"]}')
        return enhanced_course['best_prereq_path']
        
    formatted_prereqs = get_course_formatted_prereqs(enhanced_course)
    current_course_code = enhanced_course['course_code']

    if formatted_prereqs == '':
        return []
    
    try: 
        prereq_tree = parse_prereq_grammar(formatted_prereqs)
        best_prereq_path = extract_best_prereq_path(prereq_tree, dept_prefix=enhanced_course['dept'])
        best_prereq_path = [course for course in best_prereq_path if course != current_course_code]

    except Exception as e:
        best_prereq_path = ['IP']
        print(f'Produced prereq. grammar: {formatted_prereqs} (Error: {e})')

    print(f'For {enhanced_course["course_code"]} --> best prereq path: {best_prereq_path}')
    return best_prereq_path