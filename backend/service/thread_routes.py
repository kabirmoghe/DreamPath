"""
API routes for thread management.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from dreampath_processing.database.connection import get_db_connection
from dreampath_processing.database.thread_service import ThreadDatabaseService, Thread as ThreadModel

router = APIRouter(prefix="/threads", tags=["threads"])


# Helper to get database connection
def _get_db():
    """Get database connection singleton."""
    return get_db_connection()


# Pydantic models for requests/responses
class ThreadResponse(BaseModel):
    """Thread metadata response."""
    id: str
    user_id: str
    label: str  # Generated from name or creation order
    name: Optional[str] = None
    mode: str = "advise"  # 'advise' or 'build'
    created_at: str
    last_message_at: str
    is_archived: bool = False


class CreateThreadRequest(BaseModel):
    """Request to create a new thread."""
    thread_id: str = Field(..., description="LangGraph thread ID")
    user_id: str = Field(..., description="User UUID")
    name: Optional[str] = Field(None, description="Optional custom thread name")


class UpdateThreadNameRequest(BaseModel):
    """Request to update thread name."""
    name: Optional[str] = Field(None, description="New thread name (null to clear)")


class ListThreadsResponse(BaseModel):
    """Response for listing threads."""
    threads: list[ThreadResponse]


def _generate_label(thread: ThreadModel, thread_number: int) -> str:
    """
    Generate display label for a thread.
    Uses custom name if set, otherwise "Discussion #N" based on creation order.

    Args:
        thread: Thread model
        thread_number: 1-based thread number (based on creation order)

    Returns:
        Display label
    """
    if thread.name:
        return thread.name
    return f"Discussion #{thread_number}"


def _thread_to_response(thread: ThreadModel, thread_number: int) -> ThreadResponse:
    """Convert Thread model to API response."""
    return ThreadResponse(
        id=thread.id,
        user_id=thread.user_id,
        label=_generate_label(thread, thread_number),
        name=thread.name,
        mode=thread.mode,
        created_at=thread.created_at.isoformat(),
        last_message_at=thread.last_message_at.isoformat(),
        is_archived=thread.is_archived
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ThreadResponse)
async def create_thread(request: CreateThreadRequest) -> ThreadResponse:
    """
    Create a new thread record.

    This should be called when a new conversation thread is created.
    """
    db = _get_db()
    thread_service = ThreadDatabaseService(db)

    try:
        thread = await thread_service.create_thread(
            thread_id=request.thread_id,
            user_id=request.user_id,
            name=request.name
        )

        # Get thread number for label generation
        all_user_threads = await thread_service.list_user_threads(
            user_id=request.user_id,
            include_archived=False
        )
        # Find position (1-indexed)
        thread_number = len(all_user_threads)
        for i, t in enumerate(reversed(all_user_threads), 1):
            if t.id == thread.id:
                thread_number = i
                break

        return _thread_to_response(thread, thread_number)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create thread: {str(e)}"
        )


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(thread_id: str) -> ThreadResponse:
    """Get a specific thread by ID."""
    db = _get_db()
    thread_service = ThreadDatabaseService(db)

    thread = await thread_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )

    # Get thread number for label
    all_user_threads = await thread_service.list_user_threads(
        user_id=thread.user_id,
        include_archived=False
    )
    thread_number = 1
    for i, t in enumerate(reversed(all_user_threads), 1):
        if t.id == thread.id:
            thread_number = i
            break

    return _thread_to_response(thread, thread_number)


@router.get("/user/{user_id}", response_model=ListThreadsResponse)
async def list_user_threads(
    user_id: str,
    include_archived: bool = False
) -> ListThreadsResponse:
    """
    List all threads for a user, ordered by most recent first.

    The label is generated based on creation order:
    - Most recent = Discussion #1
    - Second most recent = Discussion #2
    - etc.
    """
    db = _get_db()
    thread_service = ThreadDatabaseService(db)

    threads = await thread_service.list_user_threads(
        user_id=user_id,
        include_archived=include_archived
    )

    # Generate labels based on creation order (reversed)
    # Most recent gets #1, oldest gets #N
    thread_responses = []
    total_threads = len(threads)
    for i, thread in enumerate(threads):
        # Number from oldest to newest (reversed order)
        thread_number = total_threads - i
        thread_responses.append(_thread_to_response(thread, thread_number))

    return ListThreadsResponse(threads=thread_responses)


@router.put("/{thread_id}/name", status_code=status.HTTP_204_NO_CONTENT)
async def update_thread_name(
    thread_id: str,
    request: UpdateThreadNameRequest
) -> None:
    """Update a thread's custom name."""
    db = _get_db()
    thread_service = ThreadDatabaseService(db)

    # Verify thread exists
    thread = await thread_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )

    await thread_service.update_thread_name(thread_id, request.name)


@router.put("/{thread_id}/last-message", status_code=status.HTTP_204_NO_CONTENT)
async def update_last_message_timestamp(thread_id: str) -> None:
    """
    Update the last_message_at timestamp for a thread.

    This should be called whenever a new message is added to the thread.
    """
    db = _get_db()
    thread_service = ThreadDatabaseService(db)

    # Verify thread exists
    thread = await thread_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )

    await thread_service.update_last_message_at(thread_id)


@router.put("/{thread_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_thread(thread_id: str) -> None:
    """Archive a thread (soft delete)."""
    db = _get_db()
    thread_service = ThreadDatabaseService(db)

    # Verify thread exists
    thread = await thread_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )

    await thread_service.archive_thread(thread_id)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(thread_id: str) -> None:
    """
    Permanently delete a thread record.

    Note: This only deletes the thread metadata.
    The actual conversation data in checkpoints is not deleted.
    """
    db = _get_db()
    thread_service = ThreadDatabaseService(db)

    # Verify thread exists
    thread = await thread_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )

    await thread_service.delete_thread(thread_id)
