import os
import sys
import asyncio
from psycopg_pool import AsyncConnectionPool

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/dreampath")

async def create_database_pool():
    """Create a database connection pool."""
    try:
        pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=5)
        return pool
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        print(f"   Make sure PostgreSQL is running and DATABASE_URL is correct")
        print(f"   Current DATABASE_URL: {DATABASE_URL}")
        return None

async def run_schema_sql(pool: AsyncConnectionPool):
    """Run the schema SQL to create tables."""
    print("📋 Creating database tables...")
    
    schema_path = os.path.join(os.path.dirname(__file__), "dreampath_processing", "database", "schema.sql")
    
    try:
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Split by semicolon and execute each statement
                statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
                
                for statement in statements:
                    if statement:
                        try:
                            await cur.execute(statement)
                        except Exception as e:
                            if "already exists" in str(e):
                                print(f"   Table already exists, skipping...")
                                # Rollback and continue with next statement
                                await conn.rollback()
                                continue
                            else:
                                raise e
                
                await conn.commit()
                print("✅ Database tables created successfully")
                return True
                
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

async def create_sample_data(pool: AsyncConnectionPool):
    """Create sample user and profile data for testing."""
    print("👤 Creating sample data...")
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Create a sample user
                await cur.execute(
                    """
                    INSERT INTO users (email, name) 
                    VALUES (%s, %s) 
                    ON CONFLICT (email) DO NOTHING
                    RETURNING id
                    """,
                    ("test@example.com", "Test User")
                )
                
                user_result = await cur.fetchone()
                if user_result:
                    user_id = user_result[0]  # Access by index instead of key
                    print(f"✅ Created user with ID: {user_id}")
                else:
                    # User already exists, get their ID
                    await cur.execute("SELECT id FROM users WHERE email = %s", ("test@example.com",))
                    user_result = await cur.fetchone()
                    user_id = user_result[0]  # Access by index instead of key
                    print(f"✅ Using existing user with ID: {user_id}")
                
                # Create a sample student profile
                await cur.execute(
                    """
                    INSERT INTO student_profiles (user_id, profile_name, name, major, college_interests, post_grad_goals, career_goals)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        user_id,
                        "Computer Science Track",
                        "Test Student",
                        "Computer Science",
                        "AI and machine learning, data science",
                        "Work as a software engineer at a tech company",
                        "Become a senior software engineer and eventually tech lead"
                    )
                )
                
                profile_result = await cur.fetchone()
                if profile_result:
                    profile_id = profile_result[0]  # Access by index instead of key
                    print(f"✅ Created student profile with ID: {profile_id}")
                else:
                    # Profile already exists, get their ID
                    await cur.execute("SELECT id FROM student_profiles WHERE user_id = %s", (user_id,))
                    profile_result = await cur.fetchone()
                    profile_id = profile_result[0]  # Access by index instead of key
                    print(f"✅ Using existing student profile with ID: {profile_id}")
                
                await conn.commit()
                
                print(f"\n🎯 Sample data created:")
                print(f"   User ID: {user_id}")
                print(f"   Student Profile ID: {profile_id}")
                print(f"   Email: test@example.com")
                print(f"   Major: Computer Science")
                
                return user_id, profile_id
                
    except Exception as e:
        print(f"❌ Failed to create sample data: {e}")
        return None, None

async def test_serialization(pool: AsyncConnectionPool, profile_id: int):
    """Test the serialization/deserialization with a simple course path."""
    print("🧪 Testing serialization...")
    
    try:
        from dreampath_processing.database.student_service import StudentDatabaseService, serialize_course_path, deserialize_course_path
        from dreampath_processing.modules.student_profile import StudentProfile
        from dreampath_processing.courses.schedule_modules.course_path import CoursePath
        from dreampath_processing.courses.course_relationship_handling import PrereqGraph
        from dreampath_processing.courses.schedule_modules.course import Course, CourseType
        
        # Create a simple test course path
        test_course_path = CoursePath(
            course_path=[["COSC1", "MATH1"], ["COSC2", "MATH2"]],
            recommended_courses={"COSC1", "COSC2", "MATH1", "MATH2"},
            course_bank={
                "COSC1": Course("COSC1", CourseType.MAJOR, course_title="Intro to CS"),
                "COSC2": Course("COSC2", CourseType.MAJOR, course_title="Data Structures"),
                "MATH1": Course("MATH1", CourseType.COMPLEMENTARY, course_title="Calculus I"),
                "MATH2": Course("MATH2", CourseType.COMPLEMENTARY, course_title="Calculus II"),
            },
            prereq_graph=PrereqGraph(
                children={"COSC1": {"COSC2"}},
                parents={"COSC2": {"COSC1"}},
                all_courses={"COSC1", "COSC2", "MATH1", "MATH2"}
            ),
            curr_window_start=0,
            must_have_courses={"COSC1"},
            lingering_courses=set()
        )
        
        # Test serialization
        serialized = serialize_course_path(test_course_path)
        print("✅ Serialization successful")
        
        # Test deserialization
        deserialized = deserialize_course_path(serialized)
        print("✅ Deserialization successful")
        
        # Verify the round-trip worked
        assert deserialized.course_path == test_course_path.course_path
        assert deserialized.recommended_courses == test_course_path.recommended_courses
        assert deserialized.curr_window_start == test_course_path.curr_window_start
        print("✅ Round-trip serialization test passed")
        
        # Test database save/load
        service = StudentDatabaseService(pool)
        
        # Create a test profile with course path
        test_profile = StudentProfile(
            name="Test Student",
            major="Computer Science",
            college_interests="AI and machine learning",
            post_grad_goals="Work as a software engineer",
            career_goals="Become a senior engineer",
            course_path=test_course_path
        )
        
        # Save to database
        await service.save_student_profile(profile_id, test_profile)
        print("✅ Database save successful")
        
        # Load from database
        loaded_profile = await service.load_student_profile(profile_id)
        print("✅ Database load successful")
        
        # Verify loaded profile
        assert loaded_profile.name == test_profile.name
        assert loaded_profile.major == test_profile.major
        assert loaded_profile.course_path is not None
        assert loaded_profile.course_path.course_path == test_course_path.course_path
        print("✅ Database round-trip test passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Serialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main setup function."""
    print("🚀 Setting up dreampath database...")
    print(f"   Database URL: {DATABASE_URL}")
    print()
    
    # Create database pool
    pool = await create_database_pool()
    if not pool:
        return False
    
    try:
        # Run schema
        if not await run_schema_sql(pool):
            return False
        
        # Create sample data
        user_id, profile_id = await create_sample_data(pool)
        if not user_id or not profile_id:
            return False
        
        # Test serialization
        if not await test_serialization(pool, profile_id):
            return False
        
        print("\n🎉 Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Set environment variables:")
        print(f"   export DATABASE_URL='{DATABASE_URL}'")
        print("2. Test the agent service:")
        print("   cd backend && python -m uvicorn service.service:app --reload")
        print("3. Test with API call:")
        print(f"   curl -X POST 'http://localhost:8000/stream' \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -H 'Authorization: Bearer your_auth_secret' \\")
        print("     -d '{\"message\": \"Find me AI courses\", \"agent_config\": {\"student_profile_id\": " + str(profile_id) + "}}'")
        
        return True
        
    finally:
        await pool.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
