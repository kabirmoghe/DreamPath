"""
Frontend Message Helpers

Functions to create structured LangChain messages with metadata for rich frontend rendering.
These messages include additional_kwargs with structured data while keeping LLM context intact.
"""

from typing import Any

from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput
from dreampath_processing.dreampath_agent.dreampath_types import ModifiedStudentProfile
from dreampath_processing.modules.student_profile import StudentProfile
from langchain_core.messages import AIMessage


def extract_coursepath_operations_metadata(cp_agent_output: CoursePathAgentOutput) -> dict[str, Any]:
    """
    Extract structured metadata from a single CoursePathAgentOutput for interrupt display.

    Args:
        cp_agent_output: Single operation output from CoursePathAgent

    Returns:
        Dict with event_type and operations for frontend rendering
    """
    operations_metadata = []

    print(f"🔍 DEBUG: cp_agent_output.diff = {cp_agent_output.diff}")
    print(f"🔍 DEBUG: diff type = {type(cp_agent_output.diff)}")

    if cp_agent_output.diff and isinstance(cp_agent_output.diff, dict):
        # Handle both dict and list formats for changes
        for change_type, changes in cp_agent_output.diff.items():
            print(f"🔍 DEBUG: Processing change_type={change_type}, changes={changes}, type={type(changes)}")
            if change_type == 'added' and changes:
                if isinstance(changes, list):
                    # List of dicts format: [{'course_code': 'CS101', 'term_idx': 2}]
                    for change in changes:
                        if isinstance(change, dict) and 'course_code' in change and 'term_idx' in change:
                            operations_metadata.append({
                                'type': 'add',
                                'course_code': change['course_code'],
                                'term': change['term_idx'] + 1 if isinstance(change['term_idx'], int) else change['term_idx']
                            })
                elif isinstance(changes, dict):
                    # Dict format: {'CS101': 2}
                    for course_code, term_idx in changes.items():
                        operations_metadata.append({
                            'type': 'add',
                            'course_code': course_code,
                            'term': term_idx + 1 if isinstance(term_idx, int) else term_idx
                        })

            elif change_type == 'removed' and changes:
                if isinstance(changes, list):
                    # List of dicts format
                    for change in changes:
                        if isinstance(change, dict) and 'course_code' in change and 'term_idx' in change:
                            operations_metadata.append({
                                'type': 'remove',
                                'course_code': change['course_code'],
                                'term': change['term_idx'] + 1 if isinstance(change['term_idx'], int) else change['term_idx']
                            })
                elif isinstance(changes, dict):
                    # Dict format
                    for course_code, term_idx in changes.items():
                        operations_metadata.append({
                            'type': 'remove',
                            'course_code': course_code,
                            'term': term_idx + 1 if isinstance(term_idx, int) else term_idx
                        })

            elif change_type == 'moved' and changes:
                if isinstance(changes, list):
                    # List of dicts format: [{'course_code': 'CS101', 'old_term_idx': 2, 'new_term_idx': 3}]
                    for change in changes:
                        if isinstance(change, dict) and 'course_code' in change:
                            # Check for different field name variants
                            from_term = change.get('old_term_idx') or change.get('from_term_idx') or change.get('from_term')
                            to_term = change.get('new_term_idx') or change.get('to_term_idx') or change.get('to_term')
                            if from_term is not None and to_term is not None:
                                operations_metadata.append({
                                    'type': 'move',
                                    'course_code': change['course_code'],
                                    'from_term': from_term + 1 if isinstance(from_term, int) else from_term,
                                    'to_term': to_term + 1 if isinstance(to_term, int) else to_term
                                })
                            else:
                                print(f"⚠️ WARNING: Move operation missing term fields: {change}")
                elif isinstance(changes, dict):
                    # Dict format: {'CS101': (2, 3)}
                    for course_code, move_data in changes.items():
                        if isinstance(move_data, (list, tuple)) and len(move_data) == 2:
                            old_term, new_term = move_data
                            operations_metadata.append({
                                'type': 'move',
                                'course_code': course_code,
                                'from_term': old_term + 1 if isinstance(old_term, int) else old_term,
                                'to_term': new_term + 1 if isinstance(new_term, int) else new_term
                            })

    print(f"🔍 DEBUG: Extracted operations_metadata = {operations_metadata}")
    print(f"🔍 DEBUG: Number of operations = {len(operations_metadata)}")

    if operations_metadata:
        return {
            'event_type': 'coursepath_operations',
            'operations': operations_metadata
        }
    return {}


def extract_profile_update_metadata(
    modified_profile: ModifiedStudentProfile,
    original_profile: StudentProfile
) -> dict[str, Any]:
    """
    Extract structured metadata from profile modification for interrupt display.

    Args:
        modified_profile: The modified profile fields
        original_profile: The original StudentProfile for comparison

    Returns:
        Dict with event_type and changes for frontend rendering
    """
    changes = {}

    if modified_profile.major != original_profile.major:
        changes['major'] = {
            'old': original_profile.major,
            'new': modified_profile.major
        }

    if modified_profile.college_interests != original_profile.college_interests:
        changes['college_interests'] = {
            'old': original_profile.college_interests,
            'new': modified_profile.college_interests
        }

    if modified_profile.post_grad_goals != original_profile.post_grad_goals:
        changes['post_grad_goals'] = {
            'old': original_profile.post_grad_goals,
            'new': modified_profile.post_grad_goals
        }

    if modified_profile.career_goals != original_profile.career_goals:
        changes['career_goals'] = {
            'old': original_profile.career_goals,
            'new': modified_profile.career_goals
        }

    if changes:
        return {
            'event_type': 'profile_update',
            'changes': changes
        }
    return {}


def create_coursepath_operations_message(
    content: str,
    outcomes: dict[str, CoursePathAgentOutput]
) -> AIMessage:
    """
    Create a LangChain message with structured CoursePath operations metadata.

    Args:
        content: Formatted string for LLM context
        outcomes: Dictionary of operation outcomes from CoursePathAgent

    Returns:
        AIMessage with operations metadata in additional_kwargs
    """
    operations_metadata = []

    for op_str, outcome in outcomes.items():
        if outcome.diff and isinstance(outcome.diff, dict):
            # Extract operation type and details from the diff
            for change_type, changes in outcome.diff.items():
                # Handle both dict and list formats
                if not isinstance(changes, dict):
                    continue

                if change_type == 'added':
                    for course_code, term_idx in changes.items():
                        operations_metadata.append({
                            'type': 'add',
                            'course_code': course_code,
                            'term': term_idx + 1 if isinstance(term_idx, int) else term_idx
                        })
                elif change_type == 'removed':
                    for course_code, term_idx in changes.items():
                        operations_metadata.append({
                            'type': 'remove',
                            'course_code': course_code,
                            'term': term_idx + 1 if isinstance(term_idx, int) else term_idx
                        })
                elif change_type == 'moved':
                    for course_code, move_data in changes.items():
                        if isinstance(move_data, (list, tuple)) and len(move_data) == 2:
                            old_term, new_term = move_data
                            operations_metadata.append({
                                'type': 'move',
                                'course_code': course_code,
                                'from_term': old_term + 1 if isinstance(old_term, int) else old_term,
                                'to_term': new_term + 1 if isinstance(new_term, int) else new_term
                            })

    # Create message with structured metadata
    # Use empty content for frontend (structured rendering only)
    message = AIMessage(content="")
    if operations_metadata:
        message.additional_kwargs['event_type'] = 'coursepath_operations'
        message.additional_kwargs['operations'] = operations_metadata
        message.additional_kwargs['original_content'] = content  # Keep for debugging
    else:
        # If no operations extracted, fall back to text content
        message.content = content

    return message


def create_profile_update_message(
    content: str,
    modified_profile: ModifiedStudentProfile,
    original_profile: StudentProfile
) -> AIMessage:
    """
    Create a LangChain message with structured profile update metadata.

    Args:
        content: Formatted string for LLM context
        modified_profile: The modified profile fields
        original_profile: The original StudentProfile for comparison

    Returns:
        AIMessage with profile changes metadata in additional_kwargs
    """
    changes = {}

    # Compare and track changes
    if modified_profile.major != original_profile.major:
        changes['major'] = {
            'old': original_profile.major,
            'new': modified_profile.major
        }

    if modified_profile.college_interests != original_profile.college_interests:
        changes['college_interests'] = {
            'old': original_profile.college_interests,
            'new': modified_profile.college_interests
        }

    if modified_profile.post_grad_goals != original_profile.post_grad_goals:
        changes['post_grad_goals'] = {
            'old': original_profile.post_grad_goals,
            'new': modified_profile.post_grad_goals
        }

    if modified_profile.career_goals != original_profile.career_goals:
        changes['career_goals'] = {
            'old': original_profile.career_goals,
            'new': modified_profile.career_goals
        }

    # Create message with structured metadata
    # Use empty content for frontend (structured rendering only)
    message = AIMessage(content="")
    if changes:
        message.additional_kwargs['event_type'] = 'profile_update'
        message.additional_kwargs['changes'] = changes
        message.additional_kwargs['original_content'] = content  # Keep for debugging
    else:
        # If no changes detected, fall back to text content
        message.content = content

    return message
