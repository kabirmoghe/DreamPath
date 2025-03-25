from lark import Lark, Transformer

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

# def extract_best_course_path(prereq_tree):
#     def is_valid_course(course):
#         return course != "IP"

#     if isinstance(prereq_tree, str):
#         return [prereq_tree] if is_valid_course(prereq_tree) else []

#     op, args = prereq_tree

#     if op == "AND":
#         path = []
#         for arg in args:
#             path += extract_best_course_path(arg)
#         return path

#     elif op == "OR":
#         # Return the first valid path (prefer non-IP)
#         for arg in args:
#             result = extract_best_course_path(arg)
#             if result and all(c != "IP" for c in result):
#                 return result
#         # If all options include IP, fallback to first
#         return extract_best_course_path(args[0])

#     return []  # fallback

def extract_best_course_path(tree, dept_prefix):
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

    return helper(tree)



# def extract_best_course_path(prereq_tree):
#     def is_real_course(course):
#         return course != "IP" and course not in ("AP", "local_placement")

#     def is_alt_credit(course):
#         return course in ("AP", "LP", "local_placement")

#     if isinstance(prereq_tree, str):
#         if is_real_course(prereq_tree) or is_alt_credit(prereq_tree):
#             return [prereq_tree]
#         else:
#             return []

#     op, args = prereq_tree

#     if op == "AND":
#         path = []
#         for arg in args:
#             path += extract_best_course_path(arg)
#         return path

#     elif op == "OR":
#         # 1. Try to find real courses (no IP, no alt credit)
#         for arg in args:
#             result = extract_best_course_path(arg)
#             if result and all(is_real_course(c) for c in result):
#                 return result
#         # 2. Try to find alt credit like AP or placement
#         for arg in args:
#             result = extract_best_course_path(arg)
#             if result and all(is_alt_credit(c) for c in result):
#                 return result
#         # 3. Fallback to anything (may include IP)
#         return extract_best_course_path(args[0])

#     return []
