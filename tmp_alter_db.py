import asyncio
from sqlalchemy import text
from backend.core.database import async_session_maker, engine

async def run_alter():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE devices ADD COLUMN api_key_hash VARCHAR;"))
            print("Successfully added api_key_hash column")
        except Exception as e:
            print(f"Error or column already exists: {e}")

if __name__ == "__main__":
    asyncio.run(run_alter())
