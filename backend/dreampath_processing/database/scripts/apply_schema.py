"""
Apply database schema to create tables.
This script creates the necessary tables without inserting any data.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (in project root)
project_root = Path(__file__).parent.parent.parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)
print(f"📁 Loading .env from: {env_path}")
print(f"🔧 POSTGRES_DB: {os.getenv('POSTGRES_DB', 'NOT SET')}")

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from dreampath_processing.database.connection import get_db_connection

async def apply_schema():
    """Apply the database schema to create tables."""
    
    print("🔗 Connecting to database...")
    
    # Get database connection using the existing helper
    db_conn = get_db_connection()
    
    try:
        # Initialize connection pool
        await db_conn.init_pool()
        print("✅ Connected to database")
        
        # Read schema file
        schema_path = Path(__file__).parent.parent / "schema" / "initial.sql"
        print(f"📋 Reading schema from: {schema_path}")
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        print(f"📝 Executing {len(statements)} SQL statements...")
        
        for i, statement in enumerate(statements, 1):
            if statement:
                try:
                    print(f"   {i}. Executing statement...")
                    await db_conn.execute_command(statement)
                    print(f"   ✅ Statement {i} executed successfully")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"   ⚠️  Statement {i} skipped (already exists)")
                    else:
                        print(f"   ❌ Statement {i} failed: {e}")
                        raise e
        
        print("🎉 Schema applied successfully!")
        print("\n📊 Created tables:")
        print("   - users")
        print("   - student_profiles") 
        print("   - course_paths")
        
    except Exception as e:
        print(f"❌ Error applying schema: {e}")
        return False
    finally:
        # Close connection
        await db_conn.close_pool()
        print("🔌 Database connection closed")
    
    return True

if __name__ == "__main__":
    print("🚀 DreamPath Database Schema Setup")
    print("=" * 40)
    
    # Check if DATABASE_URL is set
    if not os.getenv("DATABASE_URL"):
        print("ℹ️  Using default DATABASE_URL: postgresql://postgres:password@localhost:5432/dreampath")
        print("   Set DATABASE_URL environment variable to use a different database")
        print()
    
    # Run the schema application
    success = asyncio.run(apply_schema())
    
    if success:
        print("\n✅ Schema setup completed successfully!")
        print("   You can now run your application or insert sample data.")
    else:
        print("\n❌ Schema setup failed!")
        sys.exit(1)
