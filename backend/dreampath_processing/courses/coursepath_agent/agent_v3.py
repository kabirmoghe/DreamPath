from dreampath_processing.courses.coursepath_agent.agent_v2 import CoursePathAgent
from dreampath_processing.courses.coursepath_agent.types import CoursePathAgentOutput, Op
from dreampath_processing.database.connection import DatabaseConnection, get_db_connection
from dreampath_processing.database.student_service import StudentDatabaseService
from dreampath_processing.database.course_path_agent_service import CoursePathAgentService
from dreampath_processing.courses.coursepath_agent.operation_tools import CoursePathTools
from typing import Optional

from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY

import asyncio

class CoursePathAgentDB(CoursePathAgent):
    def __init__(self, tools: Optional[CoursePathTools]=None, require_user_confirmation: bool=True, config: Optional[dict]={}, agent_service: Optional[CoursePathAgentService]=None, student_db_service: Optional[StudentDatabaseService]=None, user_id: Optional[int]=None):
        super().__init__(tools=tools, require_user_confirmation=require_user_confirmation, config=config)
        self.agent_service = agent_service
        self.student_db_service = student_db_service
        self.user_id = user_id

    async def load_agent_state(self):
        existing_state = await self.agent_service.load_agent_state(self.user_id)
        if existing_state:
            self.state = existing_state

    async def run(self, text: str) -> CoursePathAgentOutput:
        out = super().run(text)

        # Save state
        if self.agent_service and self.user_id is not None:
            await self.agent_service.save_agent_state(self.user_id, self.state)
            print(f"Saved agent state for user {self.user_id}")
        
        # Save course path
        if self.student_db_service and self.user_id is not None:
            self.tools.cp.visualize_by_term_idx()
            await self.student_db_service.save_course_path(self.tools.cp, self.user_id, pending_approval=out.status == "ask")
            print(f"Saved course path for user {self.user_id} (pending approval: {out.status == 'ask'})")
        
        return out

class CoursePathAPIService:
    def __init__(self, conn: DatabaseConnection):
        self.agent_service = CoursePathAgentService(conn)
        self.student_db_service = StudentDatabaseService(conn)

    async def run_stateless(self, user_id: int, message: str, major: Optional[str]="Computer Science", require_user_confirmation: bool=True) -> CoursePathAgentOutput:
        # Fresh stateless agent instance 
        course_path = await self.student_db_service.load_course_path(user_id)
        pending_course_path = await self.student_db_service.load_course_path(user_id, pending_approval=True)

        # Cannot proceed without active course path
        if course_path is None:
            raise ValueError(f"No active course path found for user {user_id}")

        # If pending, use active as fallback and pending as current
        if pending_course_path is not None:
            print(f"* Found pending course path for user {user_id}.")
            config = {"fallback_cp": course_path}
            course_path = pending_course_path
        
        else:
            config = {}

        tools = CoursePathTools(course_path=course_path, major=major)
        agent = CoursePathAgentDB(tools=tools, require_user_confirmation=require_user_confirmation, config=config, agent_service=self.agent_service, student_db_service=self.student_db_service, user_id=user_id)

        # Load agent state
        await agent.load_agent_state()

        # Run agent
        return await agent.run(message)

async def main():
    conn = get_db_connection()
    user_id = 1

    # Run agent
    print("CoursePathAgent ready. Type 'quit' to exit.\n")
    
    # --- Main Loop ---
    while True:
        service = CoursePathAPIService(conn)
        course_path = await service.student_db_service.load_course_path(user_id=user_id)
        if course_path is None:
            raise ValueError(f"No active course path found for user {user_id}")

        print(course_path.visualize_by_term_idx())
        print(f"----------\nCoursePath (@ term={course_path.curr_window_start})")
        # print("Recommended courses: ", current_path.recommended_courses)
        # print("Prereq Graph: ", current_path.prereq_graph)
        # print("Lingering courses: ", current_path.lingering_courses)
        print("----------\n")

        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break

        # Pass input to agent, get back a response
        response = await service.run_stateless(user_id=user_id, message=user_input)
        print(f"Agent: {response.ui_text}")

if __name__ == "__main__":
    asyncio.run(main())