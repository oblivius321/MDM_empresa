from fastapi import FastAPI
from backend.api import routes, auth
from backend.core.database import engine, Base
import contextlib
import os
from dotenv import load_dotenv
from pathlib import Path

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="MDM Projeto", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

# Carregar variáveis de ambiente
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Configurar CORS a partir de variáveis de ambiente
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
@app.get("/")
def root():
    return {
        "message": "MDM API - use /api/enroll, /api/devices, /api/devices/{id}/apply_policy, /api/devices/{id}"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)