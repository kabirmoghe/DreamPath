"""Service for loading/saving student profiles and course paths."""

import json
from typing import Optional
from dreampath_processing.modules.student_profile import StudentProfile
from dreampath_processing.courses.schedule_modules.course_path import CoursePath
from dreampath_processing.database.connection import DatabaseConnection
from dreampath_processing.database.serializers import serialize_course_path, deserialize_course_path

class StudentDatabaseService:
    """Service for loading/saving student profiles and course paths."""
    
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection

    async def save_student_profile(self, student_profile: StudentProfile, user_id: str) -> int:
        """Save student profile to PostgreSQL and set as active. Returns the profile ID."""
        # Insert new profile (is_active defaults to true)
        result = await self.db.execute_one(
            """
            INSERT INTO student_profiles (user_id, name, major, college_interests, post_grad_goals, career_goals, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, true)
            RETURNING id
            """,
            user_id, student_profile.name, student_profile.major, student_profile.college_interests,
            student_profile.post_grad_goals, student_profile.career_goals
        )

        profile_id = result['id']

        # Set this profile as the only active profile for the user
        # (deactivate any other profiles for this user)
        await self.db.execute_command(
            """
            UPDATE student_profiles
            SET is_active = false
            WHERE user_id = $1 AND id != $2 AND is_active = true
            """,
            user_id, profile_id
        )

        return profile_id
    
    async def load_student_profile(self, user_id: str, student_profile_id: Optional[int] = None) -> Optional[StudentProfile]:
        """Load student profile. Defaults to active profile for user, or specific profile if provided."""
        if student_profile_id is None:
            # Load active profile for user (query student_profiles directly by user_id)
            row = await self.db.execute_one(
                """
                SELECT name, major, college_interests,
                       post_grad_goals, career_goals
                FROM student_profiles
                WHERE user_id = $1 AND is_active = true
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id
            )
        else:
            # Load specific profile
            row = await self.db.execute_one(
                """
                SELECT name, major, college_interests,
                       post_grad_goals, career_goals
                FROM student_profiles
                WHERE id = $1
                """,
                student_profile_id
            )

        if row is None:
            return None

        return StudentProfile(
            name=row['name'],
            major=row['major'],
            college_interests=row['college_interests'],
            post_grad_goals=row['post_grad_goals'],
            career_goals=row['career_goals']
        )
    
    async def save_course_path(self, course_path: CoursePath, user_id: str, pending_approval: bool = False) -> int:
        """Save course path to PostgreSQL and link to active profile. Returns course path ID."""
        # Get the active profile ID for this user (query student_profiles directly)
        active_profile = await self.db.execute_one(
            """
            SELECT id FROM student_profiles
            WHERE user_id = $1 AND is_active = true
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id
        )

        if not active_profile or not active_profile['id']:
            raise ValueError(f"No active profile found for user {user_id}")

        profile_id = active_profile['id']
        
        # Insert new course path linked to the user and active profile
        course_path_json = json.dumps(serialize_course_path(course_path))
        
        result = await self.db.execute_one(
            """
            INSERT INTO course_paths (user_id, student_profile_id, course_path_data, is_active, pending_approval)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            user_id, profile_id, course_path_json, not pending_approval, pending_approval
        )

        # Deactivate all other course paths for the user if not pending approval
        if not pending_approval:
            course_path_id = result['id']
            await self.db.execute_command(
                """
                UPDATE course_paths 
                SET is_active = false,
                    pending_approval = false
                WHERE user_id = $1 AND id != $2
                """,
                user_id, course_path_id
            )
        
        return result['id']

    async def load_course_path(self, user_id: str, pending_approval: bool = False, course_path_id: Optional[int] = None) -> Optional[CoursePath]:
        """Load active course path for user. Returns course path if found."""
        
        if course_path_id is not None:
            row = await self.db.execute_one(
                """
                SELECT course_path_data
                FROM course_paths
                WHERE id = $1
                """,
                course_path_id
            )
        elif pending_approval:
            row = await self.db.execute_one(
                """
                SELECT course_path_data
                FROM course_paths
                WHERE user_id = $1 AND pending_approval = true
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id
            )
        else: # default to active course path
            row = await self.db.execute_one(
                """
                SELECT course_path_data
                FROM course_paths
                WHERE user_id = $1 AND is_active = true
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id
            )
        
        if not row or not row['course_path_data']:
            return None
        
        # Parse JSON string back to dict
        course_path_data = json.loads(row['course_path_data'])
        return deserialize_course_path(course_path_data)