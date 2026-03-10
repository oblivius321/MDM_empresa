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

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="MDM Projeto", lifespan=lifespan)

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.core.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.middleware.cors import CORSMiddleware

# Carregar variáveis de ambiente
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Configurar CORS a partir de variáveis de ambiente
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8000").split(",")

# Em desenvolvimento, permite dinamicamente acessos para testes móveis
if os.getenv("ENVIRONMENT", "development") != "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"^https?://.*$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

from backend.api import websocket_routes

app.include_router(routes.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(websocket_routes.router, prefix="/api")

@app.get("/")
def root():
    return {
        "message": "MDM API - use /api/enroll, /api/devices, /api/devices/{id}/apply_policy, /api/devices/{id}"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)