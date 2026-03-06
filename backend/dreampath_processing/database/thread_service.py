"""
Thread database service for managing conversation threads.

This service handles CRUD operations for thread metadata stored in PostgreSQL.
The actual conversation data is managed by LangGraph's checkpointer.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dreampath_processing.database.connection import DatabaseConnection


@dataclass
class Thread:
    """Conversation thread metadata."""
    id: str
    user_id: str
    name: Optional[str]
    mode: str  # 'advise' or 'build'
    created_at: datetime
    last_message_at: datetime
    is_archived: bool = False


class ThreadDatabaseService:
    """Service for thread metadata operations."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    @staticmethod
    def _row_to_thread(row) -> Thread:
        return Thread(
            id=row['id'],
            user_id=row['user_id'],
            name=row['name'],
            mode=row.get('mode', 'advise'),
            created_at=row['created_at'],
            last_message_at=row['last_message_at'],
            is_archived=row['is_archived'],
        )

    async def create_thread(
        self,
        thread_id: str,
        user_id: str,
        name: Optional[str] = None
    ) -> Thread:
        """
        Create a new thread record.

        Args:
            thread_id: LangGraph thread ID
            user_id: User UUID string
            name: Optional custom thread name

        Returns:
            Created thread object
        """
        row = await self.db.execute_one(
            """
            INSERT INTO threads (id, user_id, name, created_at, last_message_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, user_id, name, mode, created_at, last_message_at, is_archived
            """,
            thread_id, user_id, name
        )
        if not row:
            raise RuntimeError("Failed to create thread")
        return self._row_to_thread(row)

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        """
        Get a thread by ID.

        Args:
            thread_id: Thread ID

        Returns:
            Thread object or None if not found
        """
        row = await self.db.execute_one(
            """
            SELECT id, user_id, name, mode, created_at, last_message_at, is_archived
            FROM threads
            WHERE id = $1
            """,
            thread_id
        )
        if not row:
            return None
        return self._row_to_thread(row)

    async def list_user_threads(
        self,
        user_id: str,
        include_archived: bool = False
    ) -> list[Thread]:
        """
        List all threads for a user, ordered by most recent first.

        Args:
            user_id: User UUID string
            include_archived: Whether to include archived threads

        Returns:
            List of threads ordered by last_message_at DESC
        """
        if include_archived:
            rows = await self.db.execute_query(
                """
                SELECT id, user_id, name, mode, created_at, last_message_at, is_archived
                FROM threads
                WHERE user_id = $1
                ORDER BY last_message_at DESC
                """,
                user_id
            )
        else:
            rows = await self.db.execute_query(
                """
                SELECT id, user_id, name, mode, created_at, last_message_at, is_archived
                FROM threads
                WHERE user_id = $1 AND is_archived = FALSE
                ORDER BY last_message_at DESC
                """,
                user_id
            )

        return [self._row_to_thread(row) for row in rows]

    async def update_last_message_at(
        self,
        thread_id: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Update the last_message_at timestamp for a thread.

        Args:
            thread_id: Thread ID
            timestamp: Timestamp to set (defaults to current time)
        """
        if timestamp is None:
            await self.db.execute_command(
                """
                UPDATE threads
                SET last_message_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                thread_id
            )
        else:
            await self.db.execute_command(
                """
                UPDATE threads
                SET last_message_at = $1
                WHERE id = $2
                """,
                timestamp, thread_id
            )

    async def update_mode(self, thread_id: str, mode: str) -> None:
        """
        Update the agent mode for a thread.

        Args:
            thread_id: Thread ID
            mode: 'advise' or 'build'
        """
        await self.db.execute_command(
            """
            UPDATE threads
            SET mode = $1
            WHERE id = $2
            """,
            mode, thread_id
        )

    async def update_thread_name(
        self,
        thread_id: str,
        name: Optional[str]
    ) -> None:
        """
        Update a thread's custom name.

        Args:
            thread_id: Thread ID
            name: New name (None to clear custom name)
        """
        await self.db.execute_command(
            """
            UPDATE threads
            SET name = $1
            WHERE id = $2
            """,
            name, thread_id
        )

    async def archive_thread(self, thread_id: str) -> None:
        """
        Archive a thread (soft delete).

        Args:
            thread_id: Thread ID
        """
        await self.db.execute_command(
            """
            UPDATE threads
            SET is_archived = TRUE
            WHERE id = $1
            """,
            thread_id
        )

    async def unarchive_thread(self, thread_id: str) -> None:
        """
        Unarchive a thread.

        Args:
            thread_id: Thread ID
        """
        await self.db.execute_command(
            """
            UPDATE threads
            SET is_archived = FALSE
            WHERE id = $1
            """,
            thread_id
        )

    async def delete_thread(self, thread_id: str) -> None:
        """
        Permanently delete a thread record.
        Note: This does NOT delete the actual conversation data from checkpoints.

        Args:
            thread_id: Thread ID
        """
        await self.db.execute_command(
            "DELETE FROM threads WHERE id = $1",
            thread_id
        )
