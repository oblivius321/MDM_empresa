import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:sua_senha_aqui@localhost:5432/mdm_project")
SECRET_KEY = os.getenv("SECRET_KEY", "elion-mdm-secret-key-enterprise-edition-2026")
