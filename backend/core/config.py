import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# PostgreSQL é o padrão para produção
# SQLite é apenas para desenvolvimento local rápido
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL não configurado. "
        "Configure em .env (desenvolvimento) ou variáveis de ambiente (produção)"
    )

# Para usar SQLite localmente, defina: DATABASE_URL=sqlite+aiosqlite:///./mdm_database.db
SECRET_KEY = os.getenv("SECRET_KEY", "elion-mdm-secret-key-enterprise-edition-2026")

# Configurações adicionais
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production" and (
    os.getenv("SECRET_KEY") is None or 
    SECRET_KEY == "elion-mdm-secret-key-enterprise-edition-2026" or 
    os.getenv("DB_PASSWORD") is None
):
    raise ValueError(
        "CRITICAL: Ambiente configurado como production, mas SECRET_KEY ou DB_PASSWORD estão ausentes ou usando padrões inseguros."
    )

