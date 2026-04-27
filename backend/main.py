from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.api import routes
from backend.api.auth import router as auth_router
from backend.core.database import engine, Base
import contextlib
import os
import logging
import mimetypes
from dotenv import load_dotenv
from pathlib import Path

# Load all models for SQLAlchemy registry
import backend.models.user
import backend.models.device
import backend.models.policy
import backend.models.telemetry
# import backend.models.android_management
# ✅ NOVO: Importar modelos RBAC
import backend.models.role
import backend.models.permission
import backend.models.audit_log
from backend.utils.logging_config import setup_logging
from backend.middleware.observability import ObservabilityMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

async def ensure_default_admin(async_session):
    from sqlalchemy import select
    from backend.core.security import get_password_hash
    from backend.models.user import User

    logger = logging.getLogger("mdm.bootstrap")
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@empresa.com").strip().lower()
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "AdminSenhaForte123!")
    admin_aliases = {
        admin_email,
        "admin@empresa.com",
        "admin@elion.com.br",
    }

    result = await async_session.execute(
        select(User).where(User.email.in_(admin_aliases), User.is_admin.is_(True))
    )
    admin_user = result.scalars().first()

    if admin_user is None:
        admin_user = User(
            email=admin_email,
            hashed_password=get_password_hash(admin_password),
            is_admin=True,
            is_active=True,
        )
        async_session.add(admin_user)
        logger.warning("Default admin created at startup: %s", admin_email)
        return

    if admin_user.email != admin_email:
        logger.warning(
            "Legacy admin email retained for compatibility: current=%s configured=%s",
            admin_user.email,
            admin_email,
        )
    admin_user.is_admin = True
    admin_user.is_active = True
    admin_user.hashed_password = get_password_hash(admin_password)
    logger.info("Default admin credentials synchronized from environment for %s", admin_user.email)

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
            await ensure_default_admin(async_session)
            rbac_service = RBACService(async_session)
            await rbac_service.initialize_rbac()
            await async_session.commit()
            print("✅ RBAC system initialized")
        except Exception as e:
            await async_session.rollback()
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
    #   retry_count: tentativas enviadas
    #   attempts:    total de ciclos de vida (pending -> sent)
    async def command_timeout_watchdog():
        import logging
        from datetime import datetime, timedelta
        from sqlalchemy.future import select
        from sqlalchemy import and_
        
        from backend.core import async_session_maker, CommandStatus, utcnow
        from backend.repositories.device_repo import DeviceRepository
        from backend.models.policy import CommandQueue

        wd_logger = logging.getLogger("cmd_watchdog")
        wd_logger.info("⏰ Watchdog de Comandos (Enterprise) iniciado com Locking e Exponential Backoff.")

        while True:
            await asyncio.sleep(15) # Ciclo mais rápido para processamento de retry
            try:
                async with async_session_maker() as db:
                    repo = DeviceRepository(db)
                    now_naive = utcnow()

                    # ── 1. Processamento de Timeouts (DISPATCHED/sent) ─────────────────
                    # Lock seletivo via FOR UPDATE SKIP LOCKED garante exclusividade por worker
                    result = await db.execute(
                        select(CommandQueue)
                        .where(CommandQueue.status == CommandStatus.DISPATCHED)
                        .with_for_update(skip_locked=True)
                        .limit(50)
                    )
                    commands = result.scalars().all()

                    for cmd in commands:
                        # Cálculo de Backoff Exponencial (Cap de 5 min)
                        # retry_count incremental a cada re-envio
                        delay_seconds = min(2 ** (cmd.retry_count or 0), 300)
                        sent_at = cmd.sent_at or cmd.created_at
                        
                        # Se já passou o tempo de grace period (delay)
                        if now_naive >= (sent_at + timedelta(seconds=delay_seconds + 30)):
                            old_status = cmd.status
                            
                            # Estratégia de Retry (Fase 3)
                            if (cmd.attempts or 0) < cmd.max_retries:
                                wd_logger.info(f"🔄 [Retry] cmd_id={cmd.id} ({cmd.command}) atingiu timeout. Tentativa {cmd.attempts + 1}/{cmd.max_retries}")
                                
                                # Voltamos para PENDING para o dispatcher/ws pegar novamente
                                cmd.status = CommandStatus.PENDING
                                cmd.attempts = (cmd.attempts or 0) + 1
                                # Limpamos timestamps de envio para novo ciclo
                                cmd.sent_at = None
                                
                                await db.commit()
                                
                                await manager.broadcast_to_dashboards({
                                    "type": "CMD_RETRYING",
                                    "device_id": cmd.device_id,
                                    "command_id": str(cmd.id),
                                    "attempts": cmd.attempts
                                })
                            else:
                                # Falha definitiva
                                wd_logger.warning(f"⏰ [Timeout] cmd_id={cmd.id} esgotou retries. Falha definitiva.")
                                await repo.transition_status(cmd, CommandStatus.FAILED, metadata={"error": "timeout_reached"})
                                await db.commit()
            
            except Exception as e:
                wd_logger.error(f"[Watchdog] Erro crítico no ciclo: {e}")
                await asyncio.sleep(5)

    asyncio.create_task(command_timeout_watchdog())
    wd_logger = logging.getLogger("lifespan")
    wd_logger.info("⏰ Watchdog de Comandos (Enterprise) registrado.")

    # ── WATCHDOG DE COMPLIANCE (Fase 3) ───────────────────────────────
    # Varre o banco a cada 5 min em busca de devices com policies
    # atribuídas que não tiveram compliance check recente.
    async def compliance_watchdog():
        import logging
        from datetime import datetime, timezone, timedelta
        from backend.core.database import async_session_maker
        from backend.models.policy import DevicePolicy, DevicePolicyAssignment, PolicyState
        from sqlalchemy.future import select
        from sqlalchemy import union

        cw_logger = logging.getLogger("compliance_watchdog")
        CHECK_INTERVAL = 300  # 5 minutos
        STALE_THRESHOLD = timedelta(hours=1)  # Re-check se > 1h desde última avaliação

        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            try:
                async with async_session_maker() as db:
                    # Busca devices com policies atribuídas
                    result = await db.execute(
                        union(
                            select(DevicePolicy.device_id),
                            select(DevicePolicyAssignment.device_id),
                        )
                    )
                    device_ids = [row[0] for row in result.all()]

                    from backend.core import utcnow
                    now = utcnow()
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

    # ── AMAPI OPERATION POLLER ────────────────────────────────────────────────
    # Polls Google long-running operations for DISPATCHED AMAPI commands
    # and advances them to EXECUTED or FAILED.
    # from backend.services.amapi_operation_poller import amapi_operation_poller
    from backend.core import async_session_maker

    # Ensure operation_id column exists on command_queue (additive migration)
    async with async_session_maker() as migration_db:
        from sqlalchemy import text
        try:
            await migration_db.execute(
                text("ALTER TABLE command_queue ADD COLUMN IF NOT EXISTS operation_id VARCHAR")
            )
            await migration_db.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_command_queue_operation_id
                    ON command_queue (operation_id)
                    WHERE operation_id IS NOT NULL
                    """
                )
            )
            await migration_db.commit()
            print("✅ command_queue.operation_id column ensured.")
        except Exception as e:
            print(f"⚠️  operation_id migration: {e}")

    # asyncio.create_task(amapi_operation_poller())
    # print("⏰ AMAPI Operation Poller registrado.")

    yield

# Configuração de Logs Estruturados (JSON)
setup_logging()

app = FastAPI(title="MDM Projeto Enterprise", lifespan=lifespan)

# Métricas e Tracing
app.add_middleware(ObservabilityMiddleware)
Instrumentator().instrument(app).expose(app)

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
        "http://192.168.25.227:5173",      # Vite dev server
        "http://192.168.25.227:3000",      # Frontend container
        "http://192.168.25.227:8200",      # Backend exposto no host
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8200",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8200",
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
# from backend.api import android_management_routes

app.include_router(routes.router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(websocket_routes.router, prefix="/api")
# ✅ NOVO: Registrar rotas RBAC
app.include_router(rbac_routes.router, prefix="/api")
# ✅ FASE 3: Registrar rotas de Policy Enterprise
app.include_router(policy_routes.router)
# app.include_router(android_management_routes.router, prefix="/api")

# ✅ REPOSITÓRIO ESTÁTICO: Hospedagem de APKs e outros recursos
static_path = Path(__file__).resolve().parent / "static"
mimetypes.add_type("application/vnd.android.package-archive", ".apk")
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

@app.get("/")
def root():
    return {
        "message": "MDM API - use /api/android-management/enrollment-token, /api/android-management/devices, /api/devices"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
