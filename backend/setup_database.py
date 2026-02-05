"""
Setup the DreamPath database schema for local development.

Reads POSTGRES_* credentials from .env (same vars used by compose.yml and the app).
Creates all tables needed by the application in the local Docker PostgreSQL instance.

Usage:
    python backend/setup_database.py
"""

import sys
import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any app imports (connection.py reads env vars at import time)
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Add backend/ to sys.path so dreampath_processing imports work
sys.path.insert(0, str(Path(__file__).parent))

from dreampath_processing.database.connection import get_db_connection


SCHEMA_PATH = Path(__file__).parent / "dreampath_processing" / "database" / "schema" / "local.sql"


async def main():
    print("Setting up DreamPath database...")

    if not SCHEMA_PATH.exists():
        print(f"Schema file not found: {SCHEMA_PATH}")
        return False

    db = get_db_connection()
    print(f"Connecting to {db.host}:{db.port}/{db.database} as {db.user}")

    try:
        await db.init_pool()
        print("Connected to database")
    except Exception as e:
        print(f"Failed to connect: {e}")
        print("Make sure PostgreSQL is running (docker compose up -d) and .env is configured")
        return False

    try:
        schema_sql = SCHEMA_PATH.read_text()

        # Execute each statement individually so we get clear error reporting
        statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
        print(f"Executing {len(statements)} SQL statements...")

        for i, statement in enumerate(statements, 1):
            try:
                await db.execute_command(statement)
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"  {i}. Skipped (already exists)")
                else:
                    print(f"  {i}. FAILED: {e}")
                    raise
            else:
                print(f"  {i}. OK")

        # Verify tables were created
        rows = await db.execute_query(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('student_profiles', 'course_paths', 'course_path_agent_state', 'threads')
            ORDER BY table_name
            """
        )
        tables = [r["table_name"] for r in rows]
        print(f"\nTables in database: {', '.join(tables)}")

        if len(tables) == 4:
            print("All 4 tables created successfully!")
        else:
            print(f"Warning: expected 4 tables, found {len(tables)}")

        print("\nNote: LangGraph tables (checkpoints, etc.) are auto-created when the backend starts.")
        return True

    except Exception as e:
        print(f"Schema setup failed: {e}")
        return False
    finally:
        await db.close_pool()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
