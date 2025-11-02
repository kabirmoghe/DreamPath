from dreampath_processing.modules.student_profile import StudentProfile
from dreampath_processing.courses.course_relationship_handling import construct_course
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.schedule_modules.course import MAJOR, COMPLEMENTARY

from dreampath_processing.database.connection import DatabaseConnection, get_db_connection
from dreampath_processing.database.student_service import StudentDatabaseService

import asyncio

async def seed_user_data(conn: DatabaseConnection, user_id: int):
    try:
        await conn.execute_command(
            """
            INSERT INTO users (email, name)
            VALUES ($1, $2)
            """,
            "kabir@example.com", "Kabir Moghe"
        )

        print(f"✅ Seeded user data for user {user_id}.")
    except Exception as e:
        print(f"❌ Error seeding user data for user {user_id}: {e}")
        raise e

async def seed_student_profile_data(conn: DatabaseConnection, user_id: int):
    try:
        student_profile = StudentProfile(
            name="Kabir Moghe",
            major="Computer Science",
            college_interests="I want to focus on international relations and current events (specifically courses on Israel / Palestine, diplomacy); I want to dabble in AI and data science for social sciences",
            post_grad_goals="work hands on as a data scientists and engineer at a tech company or startup, be knowledgeable about data security/privacy, etc.",
            career_goals="Become a CDO or hands on CEO developing a b2b saas platform for data aggregation across different BI tools.",
        )
        
        student_db_service = StudentDatabaseService(conn)
        await student_db_service.save_student_profile(student_profile, user_id)

        print(f"✅ Seeded student profile data for user {user_id}.")
    
    except Exception as e:
        print(f"❌ Error seeding student profile data for user {user_id}: {e}")
        raise e

async def seed_course_path_data(conn: DatabaseConnection, user_id: int):
    try:
        major_courses = {'COSC89.27', 'COSC55', 'COSC35', 'COSC62', 'COSC69.17', 'COSC69.18', 'COSC74', 'COSC70', 'COSC34', 'COSC61'}
        complementary_courses = {'QSS30.09', 'QSS20', 'QSS17', 'QSS45', 'QSS19', 'QSS30.19', 'QSS30.07', 'MATH56', 'COGS44', 'COGS26'}

        # Construct recommended courses set and course bank
        recommended_courses = major_courses | complementary_courses
        course_bank = {c: construct_course(course_code=c, hardcoded_type=MAJOR if c in major_courses else COMPLEMENTARY) for c in recommended_courses}

        # Build initial course path + course bank updated with prereqs + scheduling info
        test_course_path = build_course_path(recommended_courses, course_bank)
        test_course_path.curr_window_start = 6

        student_db_service = StudentDatabaseService(conn)
        await student_db_service.save_course_path(test_course_path, user_id)

        print(f"✅ Seeded course path data for user {user_id}.")
    
    except Exception as e:
        print(f"❌ Error seeding course path data for user {user_id}: {e}")
        raise e

async def seed_all_data(user_id: int):
    try:
        print(f"🌱 Seeding data for user {user_id}...")
        conn = get_db_connection()
        await seed_user_data(conn, user_id)
        await seed_student_profile_data(conn, user_id)
        await seed_course_path_data(conn, user_id)
    except Exception as e:
        print(f"❌ Error seeding all data for user {user_id}: {e}")
        raise e

if __name__ == "__main__":
    asyncio.run(seed_all_data(user_id=1))