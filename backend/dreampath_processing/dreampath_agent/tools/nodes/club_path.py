from clubs.types import ClubPathModifications
from dreampath_processing.dreampath_agent.context_building import (
    extract_structured_output_from_context,
)
from dreampath_processing.dreampath_agent.tools.nodes.prompts import CLUBPATH_MODIFICATIONS_SYSTEM
from dreampath_types import DreamPathAgentState


async def generate_club_path_modifications(state: DreamPathAgentState, config) -> tuple[ClubPathModifications, dict]:
    """Generate ClubPath modifications based on context."""
    return await extract_structured_output_from_context(
        state=state,
        config=config,
        system_prompt=CLUBPATH_MODIFICATIONS_SYSTEM,
        response_model=ClubPathModifications,
        small_context=True,
        model="gpt-4o",
        temperature=0
    )


async def club_path_node(state: DreamPathAgentState, config) -> DreamPathAgentState:
    """
    Club path node that handles ClubPath modifications.

    Generates ClubPath modifications based on context and requires user confirmation before saving changes.
    """
    print("| → ClubPathModifier")

    langchain_messages = []

    # Check if we already computed the club path modifications (to avoid re-computing on interrupt resume)
    if state.pending_pre_interrupt is not None:
        print("| * Using cached club path modifications (avoiding re-computation)")
        club_path_modifications = state.pending_pre_interrupt
    else:
        print("| * Computing club path modifications for the first time")
        club_path_modifications, _ = await generate_club_path_modifications(state, config)

    # Verify modified profile with user (skipped when require_user_confirmation=False, e.g. during rebuild)
    if state.require_user_confirmation:
        
        pass