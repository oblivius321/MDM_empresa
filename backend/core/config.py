import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configurações de Ambiente (definir primeiro para usar em lógica condicional)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# PostgreSQL é o padrão para produção
# SQLite é apenas para desenvolvimento local rápido
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL não configurado. "
        "Configure em .env (desenvolvimento) ou variáveis de ambiente (produção)"
    )

# Para usar SQLite localmente, defina: DATABASE_URL=sqlite+aiosqlite:///./mdm_database.db
# ⚠️ SEGURANÇA: Gere uma chave única por instância com:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("CRÍTICO: SECRET_KEY obrigatória. Defina via variável de ambiente ou no .env.")

# Bootstrap Secret para Enroll Seguro
# Impede que qualquer app Android que saiba o device_id consiga fazer enroll
# Gere com: python -c "import secrets; print(secrets.token_urlsafe(24))"
BOOTSTRAP_SECRET = os.getenv("BOOTSTRAP_SECRET")
if not BOOTSTRAP_SECRET:
    raise ValueError("CRÍTICO: BOOTSTRAP_SECRET obrigatória. Defina via variável de ambiente ou no .env.")

