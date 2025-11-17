import os
import asyncio
import asyncpg
from contextlib import asynccontextmanager
from typing import Optional

class DatabaseConnection:
    def __init__(self, user: str, password: str, database: str, host: str, port: int):
        self.user = user
        self.password = password
        self.database = database
        self.host = host
        self.port = port
        self.pool: Optional[asyncpg.Pool] = None

    async def init_pool(self, min_size: int = 1, max_size: int = 10):
        """Initialize the connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                user=self.user,
                password=self.password,
                database=self.database,
                host=self.host,
                port=self.port,
                min_size=min_size,
                max_size=max_size
            )

    async def close_pool(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool."""
        if self.pool is None:
            await self.init_pool()
        
        async with self.pool.acquire() as conn:
            yield conn

    async def execute_query(self, query: str, *args):
        """Execute a query and return results."""
        async with self.get_connection() as conn:
            return await conn.fetch(query, *args)

    async def execute_one(self, query: str, *args):
        """Execute a query and return one result."""
        async with self.get_connection() as conn:
            return await conn.fetchrow(query, *args)

    async def execute_command(self, command: str, *args):
        """Execute a command (INSERT, UPDATE, DELETE) and return status."""
        async with self.get_connection() as conn:
            return await conn.execute(command, *args)

# Global database instance
DB_HOST = os.getenv("POSTGRES_HOST", os.getenv("DB_HOST"))
DB_PORT = int(os.getenv("POSTGRES_PORT", os.getenv("DB_PORT")))
DB_USER = os.getenv("POSTGRES_USER", os.getenv("DB_USER"))
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", os.getenv("DB_PASSWORD"))
DB_DATABASE = os.getenv("POSTGRES_DB", os.getenv("DB_DATABASE"))

if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE]):
    raise ValueError("Missing required database environment variables")   

def get_db_connection() -> DatabaseConnection:
    """Get a configured database connection."""
    # Should use urllib.parse for better parsing
    return DatabaseConnection(DB_USER, DB_PASSWORD, DB_DATABASE, DB_HOST, DB_PORT)

async def test_connection():
    """Test the database connection."""
    print("Testing database connection...")
    db = get_db_connection()
    
    try:
        # Initialize the pool
        await db.init_pool()
        print("Database connection pool initialized")
        
        # Test basic query
        result = await db.execute_query("SELECT version()")
        print(f"PostgreSQL version: {result[0]['version']}")
        
        # Test if users table exists
        result = await db.execute_query(
            """
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            """
        )
        tables = [row['table_name'] for row in result]
        print(f"Found tables: {tables}")
        
        # Close the pool
        await db.close_pool()
        print("Database connection pool closed")
        
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_connection())

