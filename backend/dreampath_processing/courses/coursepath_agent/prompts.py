OP_EXTRACTOR_SYS = """You extract a single course modification operation.
Allowed types: ADD, REMOVE, MOVE, REPLACE, SWAP, REBUILD.
Use judgement to determine the type from user input. e.g.: 
- "get rid of ..." → "REMOVE"
- "shift..." or "move..." while mentioning a single course → "MOVE"

Output must fill the ExtractedOpType schema."""

PARAM_EXTRACTOR_SYS = """You extract parameters for a single course modification operation ({op_type}).

If a range of terms is specified, express it as an inclusive tuple window (start_term, end_term).
If a required field is missing/ambiguous, DO NOT populate the field. If not explictily specified, do not guess; leave it null.
You can extract safe inferences (e.g., 'cosc 89.17' → 'COSC89.17').

Example:
- user: "add COSC1" → no terms specified, leave null.'

Output must fill the provided operation schema for {op_type}."""