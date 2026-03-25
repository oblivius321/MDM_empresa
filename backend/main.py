from fastapi import FastAPI
from backend.api import routes, auth
from backend.core.database import engine, Base
import contextlib
import os
from dotenv import load_dotenv
from pathlib import Path

# Load all models for SQLAlchemy registry
import backend.models.user
import backend.models.device
import backend.models.policy
import backend.models.telemetry
# ✅ NOVO: Importar modelos RBAC
import backend.models.role
import backend.models.permission
import backend.models.audit_log

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # ✅ NOVO: Inicializar RBAC na startup
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.services.rbac_service import RBACService
    
    async with engine.begin() as conn:
        async_session = AsyncSession(engine)
        try:
            rbac_service = RBACService(async_session)
            await rbac_service.initialize_rbac()
            print("✅ RBAC system initialized")
        except Exception as e:
            print(f"⚠️  RBAC initialization: {e}")
        finally:
            await async_session.close()
    
    yield

app = FastAPI(title="MDM Projeto", lifespan=lifespan)

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.core.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Carregar variáveis de ambiente
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# ✅ SEGURANÇA (P1.2): Configurar CORS com origins explícitas (Tarefa 9)
# Lista de origins autorizadas (sem regex wildcard)
environment = os.getenv("ENVIRONMENT", "development").lower()

if environment == "production":
    # 🔴 PRODUÇÃO: Carregar origins de variável de ambiente OBRIGATORIAMENTE
    allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
    if not allowed_origins_str:
        raise ValueError(
            "❌ CRITICAL: ALLOWED_ORIGINS env var must be set in production. "
            "Example: ALLOWED_ORIGINS=https://painel.empresa.com,https://api.empresa.com"
        )
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
    allowed_hosts = [os.getenv("HOST_DOMAIN", "painel.empresa.com")]
else:
    # 🟡 DESENVOLVIMENTO: Origins locais apenas (sem permissão wildcard)
    allowed_origins = [
        "http://192.168.25.227",           # Nginx reverse proxy (porta 80)
        "http://192.168.25.227:8080",      # Nginx porta alternativa
        "http://192.168.25.227:5173",      # Vite dev server
        "http://192.168.25.227:3000",      # Frontend container
        "http://192.168.25.227:8000",      # Backend (para testes)
        "http://127.0.0.1",          # Nginx via IP (porta 80)
        "http://127.0.0.1:8080",     # Nginx via IP porta alternativa
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    allowed_hosts = ["*"] # Em desenvolvimento, permitimos qualquer host

# Adicionar CORS middleware COM ORIGINS EXPLÍCITAS (sem regex)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # ✅ Métodos explícitos
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "x-device-token"],  # ✅ Headers específicos, incluindo token
    max_age=3600,  # Cache CORS por 1 hora
)

# ✅ SEGURANÇA: Prevenir Host Header Attacks
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=allowed_hosts
)

from backend.api import websocket_routes
# ✅ NOVO: Importar rotas RBAC
from backend.api import rbac_routes

app.include_router(routes.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(websocket_routes.router, prefix="/api")
# ✅ NOVO: Registrar rotas RBAC
app.include_router(rbac_routes.router, prefix="/api")

@app.get("/")
def root():
    return {
        "message": "MDM API - use /api/enroll, /api/devices, /api/devices/{id}/apply_policy, /api/devices/{id}"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)