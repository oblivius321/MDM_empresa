#!/usr/bin/env python
"""Initialize database with SQLAlchemy models"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from pathlib import Path

# Load environment
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurado em .env")

print(f"Conectando ao banco: {DATABASE_URL[:50]}...")

# Import models AFTER loading env
from backend.models.user import User
from backend.models.device import Device
from backend.models.policy import Policy
from backend.models.telemetry import DeviceTelemetry
from backend.core.database import Base

async def init_db():
    """Create all tables and run migrations"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Create all tables
        print("\nCriando tabelas...")
        await conn.run_sync(Base.metadata.create_all)
        print("✓ Tabelas criadas com sucesso")
        
        # Run migration for password reset fields
        print("\nAdicionando colunas de password reset...")
        from sqlalchemy import text
        
        try:
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_jti VARCHAR DEFAULT NULL;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_jti_expires TIMESTAMP DEFAULT NULL;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_answer_verified_at TIMESTAMP DEFAULT NULL;
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_password_reset_jti 
                ON users(password_reset_jti) 
                WHERE password_reset_jti IS NOT NULL;
            """))
            print("✓ Colunas de password reset adicionadas")
        except Exception as e:
            print(f"Aviso ao adicionar colunas: {e}")
    
    await engine.dispose()
    print("\n✓ Banco de dados inicializado com sucesso!")

if __name__ == "__main__":
    asyncio.run(init_db())
