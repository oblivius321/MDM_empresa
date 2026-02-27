import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:sua_senha_aqui@localhost:5432/mdm_project")
SECRET_KEY = os.getenv("SECRET_KEY", "elion-mdm-secret-key-enterprise-edition-2026")
