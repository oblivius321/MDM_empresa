import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:Sherlock314@localhost:5432/mdm_project")

async def migrate():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE policies ADD COLUMN camera_disabled BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE policies ADD COLUMN install_unknown_sources BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE policies ADD COLUMN factory_reset_disabled BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE policies ADD COLUMN kiosk_mode VARCHAR"))
            print("Successfully added columns to policies table.")
        except Exception as e:
            print("Error adding columns (might already exist):", e)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
