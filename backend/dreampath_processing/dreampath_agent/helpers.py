from instructor import from_openai
from openai import OpenAI
import os
from dotenv import load_dotenv
import json
from pydantic import BaseModel
from typing import Literal, List, Optional
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.dreampath_agent.types import OrchestratorDecision, DreamPathAgentState, CoursePathOperations, CourseSearchOutput
from dreampath_processing.dreampath_agent.prompts import ORCHESTRATOR_DECISION_SYS, BUILD_OPERATIONS_SYS, CRAFT_FINAL_REPLY_SYS
from dreampath_processing.courses.coursepath_agent.agent import CoursePathAgent, CoursePathTools

load_dotenv()

client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

def build_messages(state: DreamPathAgentState, prompt: str):
    msgs = [{"role": "system", "content": prompt}]
    if state.summary:
        msgs.append({"role": "assistant", "content": f"Summary: ...{state.summary[-800:]}"})
    if state.recent_messages:
        msgs.extend(state.recent_messages[-10:])

    # search_results = state.search_results
    # if search_results:
    #     search_message = {
    #         "role": "assistant",
    #         "content": json.dumps(search_results.model_dump()),
    #     }
    #     msgs.append(search_message)

    # course_path_agent_outcomes = state.current_cp_agent_outcomes
    # print(f"outcomes: {course_path_agent_outcomes}")
    # if course_path_agent_outcomes:
    #     for outcome in course_path_agent_outcomes:
    #         msgs.append({"role": "assistant", "content": json.dumps(outcome.model_dump())})

    return msgs

def extract_structured_output_from_context(state: DreamPathAgentState, system_prompt: str, response_model: BaseModel, model="gpt-4o-mini", temperature=0, verbose=False):
    messages = build_messages(state, system_prompt)
    if verbose:
        print("=== MESSAGES SENT TO LLM ===")
        for i, msg in enumerate(messages):
            print(f"Message {i}: {msg['role']} - {msg['content'][:200]}...")
        print("=== END MESSAGES ===")
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_model=response_model,
        temperature=temperature
    )
    return response

def decide_next_route(state: DreamPathAgentState) -> OrchestratorDecision:
    worklist = state.worklist
    return extract_structured_output_from_context(state, ORCHESTRATOR_DECISION_SYS.format(worklist=worklist), OrchestratorDecision, verbose=True)

def build_operations_from_context_and_results(state: DreamPathAgentState, max_cmds: int=3) -> CoursePathOperations:
    return extract_structured_output_from_context(state, BUILD_OPERATIONS_SYS, CoursePathOperations, model="gpt-4o-mini")

def render_final_reply(state: DreamPathAgentState) -> str:
    return extract_structured_output_from_context(state, CRAFT_FINAL_REPLY_SYS, str, temperature=0.1)

if __name__ == "__main__":
    state = DreamPathAgentState(
        recent_messages=[
            {"role": "user", "content": "can you add cosc50 to term 6?"},
        ]
    )
    print(build_operations_from_context_and_results(state))