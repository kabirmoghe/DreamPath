"""Service for loading/saving course path agent state."""

import json
from typing import Optional
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentState
from dreampath_processing.database.connection import DatabaseConnection
from dreampath_processing.database.serializers import (
    serialize_course_path_agent_state, 
    deserialize_course_path_agent_state
)

class CoursePathAgentService:
    """Service for loading/saving course path agent state."""
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection

    async def save_agent_state(self, user_id: int, agent_state: CoursePathAgentState) -> None:
        """Save or update agent state for a user. Only maintains one state row per user."""
        state_data = serialize_course_path_agent_state(agent_state)
        
        # Use UPSERT (INSERT ... ON CONFLICT UPDATE) to maintain only one state per user
        await self.db.execute_command(
            """
            INSERT INTO course_path_agent_state 
            (user_id, pending_op_type, pending_op_data, trial_op_execution, missing_fields, 
             facts, history, recent_messages, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) 
            DO UPDATE SET
                pending_op_type = EXCLUDED.pending_op_type,
                pending_op_data = EXCLUDED.pending_op_data,
                trial_op_execution = EXCLUDED.trial_op_execution,
                missing_fields = EXCLUDED.missing_fields,
                facts = EXCLUDED.facts,
                history = EXCLUDED.history,
                recent_messages = EXCLUDED.recent_messages,
                updated_at = CURRENT_TIMESTAMP
            """,
            user_id,
            state_data["pending_op_type"],
            json.dumps(state_data["pending_op_data"]) if state_data["pending_op_data"] else None,
            json.dumps(state_data["trial_op_execution"]) if state_data["trial_op_execution"] else None,
            json.dumps(state_data["missing_fields"]),
            json.dumps(state_data["facts"]),
            state_data["history"],
            json.dumps(state_data["recent_messages"])
        )
    
    async def load_agent_state(self, user_id: int) -> Optional[CoursePathAgentState]:
        """Get agent state for a user."""
        row = await self.db.execute_one(
            """
            SELECT pending_op_type, pending_op_data, trial_op_execution, missing_fields, 
                   facts, history, recent_messages
            FROM course_path_agent_state 
            WHERE user_id = $1
            """,
            user_id
        )
        
        if row is None:
            return None
        
        # Parse JSON fields back to Python objects
        data = {
            "pending_op_type": row["pending_op_type"],
            "pending_op_data": json.loads(row["pending_op_data"]) if row["pending_op_data"] else None,
            "trial_op_execution": json.loads(row["trial_op_execution"]) if row["trial_op_execution"] else None,
            "missing_fields": json.loads(row["missing_fields"]),
            "facts": json.loads(row["facts"]),
            "history": row["history"],
            "recent_messages": json.loads(row["recent_messages"])
        }
        
        return deserialize_course_path_agent_state(data)
    
    async def delete_agent_state(self, user_id: int) -> None:
        """Delete agent state for a user."""
        await self.db.execute_command(
            """
            DELETE FROM course_path_agent_state 
            WHERE user_id = $1
            """,
            user_id
        )
    
    async def agent_state_exists(self, user_id: int) -> bool:
        """Check if agent state exists for a user."""
        row = await self.db.execute_one(
            """
            SELECT 1 FROM course_path_agent_state WHERE user_id = $1
            """,
            user_id
        )
        return row is not None
