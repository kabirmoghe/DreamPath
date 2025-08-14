OP_EXTRACTOR_SYS = """You extract a single course modification operation.
                Allowed types: ADD, REMOVE, MOVE, REPLACE, SWAP, REBUILD.
                Use judgement to determine the type from user input. e.g.: 
                - "get rid of ..." → "REMOVE"
                - "shift..." or "move..." while mentioning a single course → "MOVE"
            
                Output must fill the ExtractedOpType schema."""

PARAM_EXTRACTOR_SYS = """You extract parameters for a single course modification operation ({op_type}).
                Do NOT ask about optional fields. If optional fields are unknown, leave them null.
                Specifically, do not ask about reschedule and never set reschedule=True unless user explicitly says so (e.g., "...and I want to reschedule" or "...with force").
                If a range of terms is specified, express it as an inclusive tuple window (start_term, end_term).
                If a required field is missing/ambiguous:
                - do not guess silently
                - add the field to `missing`
                - include 1-2 short `questions`
                You may record safe inferences in `inferred` (e.g., 'cosc 89.17' → 'COSC89.17').
                Output must fill the provided ExtractedOp schema."""