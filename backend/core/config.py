import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./mdm_database.db")
SECRET_KEY = os.getenv("SECRET_KEY", "elion-mdm-secret-key-enterprise-edition-2026")
