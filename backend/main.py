from fastapi import FastAPI
from backend.api import routes
from backend.api.auth import router as auth_router
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

    # ── WATCHDOG DE PRESENÇA ────────────────────────────────────────────────────
    # Inicia o loop de detecção de zombie connections em background.
    # Varre a cada 30s e marca offline dispositivos sem heartbeat > 65s.
    from backend.api.websockets import manager
    manager.start_watchdog()
    print("🛡️ Watchdog de Presença iniciado.")

    # ── WATCHDOG DE COMANDOS (Dual-Timeout — Ajuste 3) ──────────────────────────
    # Duas janelas de timeout com diagnóstico distinto:
    #   sent_timeout  (30s) → device não confirmou recepção → failed_no_ack
    #   acked_timeout (90s) → device confirmou mas não executou → failed_no_result
    import asyncio
    async def command_timeout_watchdog():
        import logging
        from datetime import datetime, timezone, timedelta
        from backend.core.database import async_session_maker
        from backend.models.policy import CommandQueue
        from sqlalchemy import and_
        from sqlalchemy.future import select

        wd_logger = logging.getLogger("cmd_watchdog")
        SENT_TIMEOUT_SECONDS  = 30   # sem ACK após 30s
        ACKED_TIMEOUT_SECONDS = 90   # sem RESULT após 90s da acked_at

        while True:
            await asyncio.sleep(30)
            try:
                async with async_session_maker() as db:
                    now = datetime.now(timezone.utc)

                    # ── Janela 1: sent → failed_no_ack ────────────────────────
                    sent_cutoff = now - timedelta(seconds=SENT_TIMEOUT_SECONDS)
                    res1 = await db.execute(
                        select(CommandQueue).where(
                            and_(
                                CommandQueue.status == "sent",
                                CommandQueue.sent_at < sent_cutoff,
                            )
                        )
                    )
                    for cmd in res1.scalars().all():
                        cmd.status = "failed_no_ack"
                        cmd.error_code = "no_ack"
                        cmd.error_message = f"Device não confirmou recepção em {SENT_TIMEOUT_SECONDS}s"
                        cmd.completed_at = now
                        wd_logger.warning(
                            f"⏰ [CMD no_ack] cmd_id={cmd.id} action={cmd.command} "
                            f"device={cmd.device_id} → failed_no_ack"
                        )
                        await manager.broadcast_to_dashboards({
                            "type": "CMD_FAILED",
                            "device_id": cmd.device_id,
                            "command_id": cmd.id,
                            "action": cmd.command,
                            "status": "failed_no_ack",
                            "error": cmd.error_message,
                        })
                        # Ajuste 2: métricas de timeout
                        try:
                            from backend.api.command_dispatcher import emit_command_metrics
                            emit_command_metrics(cmd)
                        except Exception:
                            pass

                    # ── Janela 2: acked → failed_no_result ────────────────────
                    acked_cutoff = now - timedelta(seconds=ACKED_TIMEOUT_SECONDS)
                    res2 = await db.execute(
                        select(CommandQueue).where(
                            and_(
                                CommandQueue.status == "acked",
                                CommandQueue.acked_at < acked_cutoff,
                            )
                        )
                    )
                    for cmd in res2.scalars().all():
                        cmd.status = "failed_no_result"
                        cmd.error_code = "no_result"
                        cmd.error_message = f"Device não reportou resultado em {ACKED_TIMEOUT_SECONDS}s após ACK"
                        cmd.completed_at = now
                        wd_logger.warning(
                            f"⏰ [CMD no_result] cmd_id={cmd.id} action={cmd.command} "
                            f"device={cmd.device_id} → failed_no_result"
                        )
                        await manager.broadcast_to_dashboards({
                            "type": "CMD_FAILED",
                            "device_id": cmd.device_id,
                            "command_id": cmd.id,
                            "action": cmd.command,
                            "status": "failed_no_result",
                            "error": cmd.error_message,
                        })
                        # Ajuste 2: métricas de timeout
                        try:
                            from backend.api.command_dispatcher import emit_command_metrics
                            emit_command_metrics(cmd)
                        except Exception:
                            pass

                    await db.commit()
            except Exception as e:
                wd_logger.error(f"[CMD Watchdog] Erro: {e}")

    asyncio.create_task(command_timeout_watchdog())
    print("⏰ Watchdog de Comandos (Dual-Timeout) iniciado.")

    # ── WATCHDOG DE COMPLIANCE (Fase 3) ───────────────────────────────
    # Varre o banco a cada 5 min em busca de devices com policies
    # atribuídas que não tiveram compliance check recente.
    async def compliance_watchdog():
        import logging
        from datetime import datetime, timezone, timedelta
        from backend.core.database import async_session_maker
        from backend.models.policy import DevicePolicy, PolicyState
        from sqlalchemy.future import select
        from sqlalchemy import distinct

        cw_logger = logging.getLogger("compliance_watchdog")
        CHECK_INTERVAL = 300  # 5 minutos
        STALE_THRESHOLD = timedelta(hours=1)  # Re-check se > 1h desde última avaliação

        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            try:
                async with async_session_maker() as db:
                    # Busca devices com policies atribuídas
                    result = await db.execute(
                        select(distinct(DevicePolicy.device_id))
                    )
                    device_ids = [row[0] for row in result.all()]

                    now = datetime.now(timezone.utc)
                    for did in device_ids:
                        # Verifica se precisa re-checar
                        state_result = await db.execute(
                            select(PolicyState).where(PolicyState.device_id == did)
                        )
                        state = state_result.scalar_one_or_none()

                        needs_check = (
                            not state
                            or not state.last_enforced_at
                            or (now - state.last_enforced_at) > STALE_THRESHOLD
                        )

                        if needs_check and (
                            not state or state.last_compliance_status != "failed_loop"
                        ):
                            from backend.services.drift_detector import evaluate_compliance
                            asyncio.create_task(evaluate_compliance(did))
                            cw_logger.info(f"🔍 [ComplianceWatchdog] Re-check device={did}")

            except Exception as e:
                cw_logger.error(f"[ComplianceWatchdog] Erro: {e}")

    asyncio.create_task(compliance_watchdog())
    print("🛡️ Watchdog de Compliance (Fase 3) iniciado.")

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
# ✅ FASE 3: Importar rotas de Policy Enterprise
from backend.api import policy_routes

app.include_router(routes.router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(websocket_routes.router, prefix="/api")
# ✅ NOVO: Registrar rotas RBAC
app.include_router(rbac_routes.router, prefix="/api")
# ✅ FASE 3: Registrar rotas de Policy Enterprise
app.include_router(policy_routes.router)

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