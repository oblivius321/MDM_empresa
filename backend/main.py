from fastapi import FastAPI
from backend.api import routes, auth
from backend.core.database import engine, Base
import contextlib

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="MDM Projeto", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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