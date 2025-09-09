from instructor import from_openai
from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from backend.dreampath_processing.dreampath_agent.types_legacy import OrchestratorDecision, DreamPathAgentState, CoursePathOperations
from dreampath_processing.dreampath_agent.prompts import ORCHESTRATOR_DECISION_SYS, BUILD_OPERATIONS_SYS, CRAFT_FINAL_REPLY_SYS

load_dotenv()

client = from_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

def build_messages(state: DreamPathAgentState, prompt: str):
    msgs = [{"role": "system", "content": prompt}]
    if state.summary:
        msgs.append({"role": "assistant", "content": f"Summary: ...{state.summary[-800:]}"})
    if state.recent_messages:
        msgs.extend(state.recent_messages[-10:])

    return msgs

def extract_structured_output_from_context(state: DreamPathAgentState, system_prompt: str, response_model: BaseModel, model="gpt-4o-mini", temperature=0, verbose=False):
    messages = build_messages(state, system_prompt)
    if verbose:
        print("=== MESSAGES SENT TO LLM ===")
        for i, msg in enumerate(messages):
            print(f"Message {i}: {msg['role']} - {msg['content']}")#[:200]}...")
        print("=== END MESSAGES ===")
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_model=response_model,
        temperature=temperature
    )
    return response

def decide_next_route(state: DreamPathAgentState, config) -> OrchestratorDecision:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, ORCHESTRATOR_DECISION_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), OrchestratorDecision)#, verbose=True)

def build_operations_from_context_and_results(state: DreamPathAgentState, max_cmds: int=3) -> CoursePathOperations:
    return extract_structured_output_from_context(state, BUILD_OPERATIONS_SYS, CoursePathOperations, model="gpt-4o-mini")

def render_final_reply(state: DreamPathAgentState, config) -> str:
    student_profile = config["configurable"]["student_profile"]
    student_name = student_profile.name
    return extract_structured_output_from_context(state, CRAFT_FINAL_REPLY_SYS.format(student_name=student_name, student_profile=student_profile.__str__()), str, temperature=0.1, verbose=True)

if __name__ == "__main__":
    state = DreamPathAgentState(
        recent_messages=[
            {"role": "user", "content": "can you add cosc50 to term 6?"},
        ]
    )
    print(build_operations_from_context_and_results(state))