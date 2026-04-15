from fastapi import APIRouter, HTTPException, Depends, Query, Request, Response, status
from typing import List, Dict, Optional
from backend.api.websockets import manager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.services.mdm_service import MDMService
from backend.repositories.device_repo import DeviceRepository
from backend.core.database import get_db
from backend.schemas.device import (
    DeviceCreate, DeviceResponse, DeviceUpdate, DeviceFullResponse, EnrollmentResponse,
    AttestationRequest, NonceResponse, DeviceSummaryResponse
)
from backend.services.attestation_service import AttestationService
from backend.services.redis_service import RedisService
from backend.schemas.policy import (
    ProvisioningProfileCreate, ProvisioningProfileResponse, ProvisioningProfileUpdate,
    DevicePolicyResponse, PolicySyncHandshake, DeviceCommandResponse, CommandStatusUpdate,
    DeviceCommandCreate, BootstrapResponse, DeviceStatusReport
)
from backend.schemas.user import DeviceEnrollRequest, UserMeResponse, UserPreferences, UserPreferencesUpdate
from backend.schemas.telemetry import TelemetryResponse
from backend.api.auth import get_current_user
from backend.api.device_auth import get_current_device
from backend.core.limiter import limiter
from backend.models.device import Device
from backend.models.user import User
import base64
import datetime
import hashlib
import os
from pathlib import Path
import uuid
import logging

router = APIRouter()

APK_FILENAME = "elion-mdm.apk"
APK_PATH = Path(__file__).resolve().parent.parent / "static" / APK_FILENAME

def get_repo(db: AsyncSession = Depends(get_db)) -> DeviceRepository:
    return DeviceRepository(db)

def get_redis() -> RedisService:
    return RedisService()

def get_service(
    repo: DeviceRepository = Depends(get_repo), 
    redis: RedisService = Depends(get_redis)
) -> MDMService:
    return MDMService(repo, redis)

def get_attestation(redis: RedisService = Depends(get_redis)) -> AttestationService:
    return AttestationService(redis)


def get_public_base_url(request: Request) -> str:
    base_url = os.getenv("API_URL", f"{request.base_url.scheme}://{request.base_url.netloc}").rstrip("/")
    return base_url[:-4] if base_url.endswith("/api") else base_url


def get_apk_checksum() -> str:
    if not APK_PATH.exists():
        raise HTTPException(status_code=500, detail=f"APK de enrollment nao encontrado: {APK_FILENAME}")

    digest = hashlib.sha256(APK_PATH.read_bytes()).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def normalize_user_preferences(preferences: Optional[Dict]) -> Dict[str, bool]:
    defaults = UserPreferences().model_dump()
    return {
        key: bool((preferences or {}).get(key, value))
        for key, value in defaults.items()
    }


def serialize_user_me(user: User) -> Dict:
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "preferences": normalize_user_preferences(getattr(user, "preferences", None)),
    }


def serialize_audit_log(log) -> Dict:
    action = getattr(log.action, "value", log.action)
    return {
        "id": str(log.id),
        "user_id": log.user_id,
        "user_email": log.user.email if getattr(log, "user", None) else None,
        "action": action,
        "event_type": log.event_type,
        "severity": log.severity,
        "actor_type": log.actor_type,
        "actor_id": log.actor_id,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "device_id": str(log.device_id) if log.device_id else None,
        "details": log.details or {},
        "is_success": log.is_success,
        "error_message": log.error_message,
        "request_id": log.request_id,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "created_at": log.created_at,
    }


# ============= USER PROFILE & PREFERENCES =============

@router.get("/users/me", response_model=UserMeResponse, tags=["Dashboard"])
async def get_current_dashboard_user(
    current_user: User = Depends(get_current_user)
):
    return serialize_user_me(current_user)


@router.patch("/users/me/preferences", response_model=UserMeResponse, tags=["Dashboard"])
async def update_current_user_preferences(
    preferences_update: UserPreferencesUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: MDMService = Depends(get_service),
):
    updates = {
        key: value
        for key, value in preferences_update.model_dump(exclude_unset=True).items()
        if value is not None
    }

    current_preferences = normalize_user_preferences(getattr(current_user, "preferences", None))
    updated_preferences = {**current_preferences, **updates}

    current_user.preferences = updated_preferences
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    if updates:
        await service.repo.log_event(
            event_type="USER_PREFERENCES_UPDATE",
            actor_type="admin" if current_user.is_admin else "user",
            actor_id=current_user.email,
            user_id=current_user.id,
            severity="INFO",
            payload={
                "message": "Configuracoes de notificacao atualizadas",
                "changed_keys": sorted(updates.keys()),
                "preferences": updated_preferences,
            },
            request=request,
        )

    return serialize_user_me(current_user)


# ============= 🛡️ CAMADA 1: CORE (Devices & Profiles) =============

@router.get("/profiles", response_model=List[ProvisioningProfileResponse], tags=["SaaS Admin"])
async def list_profiles(
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Somente administrador pode gerenciar perfis globais.")
    return await service.list_profiles()

@router.post("/profiles", response_model=ProvisioningProfileResponse, tags=["SaaS Admin"])
async def create_profile(
    profile_data: ProvisioningProfileCreate,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    return await service.create_profile(profile_data)

@router.get("/profiles/{profile_id}", response_model=ProvisioningProfileResponse, tags=["SaaS Admin"])
async def get_profile(
    profile_id: uuid.UUID,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    return await service.get_profile(profile_id)

@router.put("/profiles/{profile_id}", response_model=ProvisioningProfileResponse, tags=["SaaS Admin"])
async def update_profile(
    profile_id: uuid.UUID,
    profile_data: ProvisioningProfileUpdate,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    return await service.update_profile(profile_id, profile_data)


# ============= 🛡️ CAMADA 2: ENROLLMENT SEGMENTADO =============

@router.post("/enrollment/generate", tags=["SaaS Admin"], deprecated=True)
@limiter.limit("10/minute")
async def deprecated_legacy_enrollment_token(
    request: Request,
    response: Response,
    profile_id: uuid.UUID,
    mode: str = "single",
    max_devices: int = 1,
    ttl_minutes: int = 15,
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis),
    service: MDMService = Depends(get_service),
):
    """
    Gera um token de enrollment dinâmico com TTL.
    - mode: 'single' (1 device, padrão seguro) ou 'batch' (N devices)
    - TTL: 5-60 minutos
    - Token vinculado ao admin + tenant + profile
    """
    enroll_logger = logging.getLogger("mdm.enrollment")
    response.headers["X-Deprecated"] = "true"
    enroll_logger.warning("DEPRECATED: legacy enrollment endpoint called")
    enroll_logger.error("LEGACY ENROLLMENT FLOW USED - SHOULD NOT HAPPEN")

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Somente administradores podem gerar tokens de enrollment.")

    # Validação de inputs
    if mode not in ("single", "batch"):
        raise HTTPException(status_code=400, detail="Mode deve ser 'single' ou 'batch'.")
    if mode == "batch" and (max_devices < 1 or max_devices > 500):
        raise HTTPException(status_code=400, detail="max_devices deve ser entre 1 e 500.")
    ttl_minutes = max(5, min(60, ttl_minutes))

    # Verifica se o profile existe
    profile = await service.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de provisionamento não encontrado.")

    # Gerar token dinâmico
    enrollment_token = str(uuid.uuid4())
    ttl_seconds = ttl_minutes * 60
    api_url = get_public_base_url(request)
    apk_checksum = get_apk_checksum()

    # Armazenar no Redis com metadados de auditoria
    await redis.store_enrollment_token(
        token=enrollment_token,
        profile_id=str(profile_id),
        tenant_id=str(getattr(current_user, 'tenant_id', 'default')),
        created_by=str(current_user.email),
        mode=mode,
        max_devices=max_devices if mode == "batch" else 1,
        ttl=ttl_seconds,
    )

    # Audit Log
    await service.repo.log_event(
        event_type="ENROLLMENT_TOKEN_GENERATED",
        actor_type="admin",
        actor_id=str(current_user.email),
        user_id=current_user.id,
        severity="INFO",
        payload={
            "token_prefix": enrollment_token[:8],
            "profile_id": str(profile_id),
            "mode": mode,
            "max_devices": max_devices if mode == "batch" else 1,
            "ttl_minutes": ttl_minutes,
            "ip": request.client.host if request.client else "unknown",
        },
        request=request,
    )

    enroll_logger.info(
        f"🎫 Enrollment token gerado por {current_user.email}: "
        f"mode={mode}, profile={profile_id}, ttl={ttl_minutes}min"
    )

    from datetime import timedelta
    expires_at = datetime.datetime.utcnow() + timedelta(minutes=ttl_minutes)

    return {
        "enrollment_token": enrollment_token,
        "profile_id": str(profile_id),
        "api_url": api_url.rstrip('/') + "/api",
        "profile_name": profile.name,
        "mode": mode,
        "max_devices": max_devices if mode == "batch" else 1,
        "ttl_minutes": ttl_minutes,
        "expires_at": expires_at.isoformat() + "Z",
        "admin_component": "com.elion.mdm/com.elion.mdm.AdminReceiver",
        "apk_url": api_url.rstrip('/') + f"/static/elion-mdm.apk?sha={apk_checksum}",
        "apk_checksum": apk_checksum,
    }


@router.post("/enroll", response_model=EnrollmentResponse, tags=["Device Ops"], deprecated=True)
@limiter.limit("5/minute")
async def enroll_device(
    request: Request,
    response: Response,
    req: DeviceEnrollRequest, 
    service: MDMService = Depends(get_service),
    redis: RedisService = Depends(get_redis),
):
    """
    Enrollment com token dinâmico (Enterprise).
    O dispositivo envia o bootstrap_token recebido via QR Code.
    O backend valida contra o Redis (UNUSED→USED) e associa ao profile correto.
    """
    enroll_logger = logging.getLogger("mdm.enrollment")
    response.headers["X-Deprecated"] = "true"
    enroll_logger.warning("DEPRECATED: legacy enrollment endpoint called")
    enroll_logger.error("LEGACY ENROLLMENT FLOW USED - SHOULD NOT HAPPEN")
    try:
        # Validar token dinâmico no Redis
        token_data = await redis.validate_enrollment_token(req.bootstrap_token)
        
        if not token_data:
            enroll_logger.warning(
                f"🚨 Enrollment REJEITADO para {req.device_id}: "
                f"token inválido/expirado (IP: {request.client.host if request.client else 'unknown'})"
            )
            # Audit: tentativa bloqueada
            await service.repo.log_event(
                event_type="ENROLLMENT_REJECTED",
                actor_type="device",
                actor_id=req.device_id,
                severity="WARNING",
                payload={
                    "reason": "invalid_or_expired_token",
                    "ip": request.client.host if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", "unknown"),
                },
                request=request,
            )
            raise HTTPException(status_code=403, detail="Token de enrollment inválido ou expirado.")

        # Usar o profile_id do token (backend decide, não o device)
        profile_id = uuid.UUID(token_data["profile_id"])

        # Realiza o enroll criando a associação com a política inicial
        device, token = await service.enroll_device(
            device_id=req.device_id,
            name=req.name,
            device_type=req.device_type,
            profile_id=profile_id,
            **req.extra_data if req.extra_data else {}
        )

        # Audit: enrollment bem-sucedido
        await service.repo.log_event(
            event_type="DEVICE_ENROLLED",
            actor_type="device",
            actor_id=req.device_id,
            severity="INFO",
            device_id=req.device_id,
            payload={
                "profile_id": str(profile_id),
                "tenant_id": token_data.get("tenant_id", "default"),
                "enrolled_by_admin": token_data.get("created_by", "unknown"),
                "mode": token_data.get("mode", "single"),
                "usage": f"{token_data.get('used_count', 1)}/{token_data.get('max_devices', 1)}",
                "ip": request.client.host if request.client else "unknown",
            },
            request=request,
        )

        enroll_logger.info(
            f"✅ Device {req.device_id} enrolled com sucesso via token dinâmico "
            f"(profile={profile_id}, admin={token_data.get('created_by')})"
        )
        
        return {
            "message": "Handshake de identidade concluído.",
            "device_id": device.device_id,
            "device_token": token,
            "api_url": str(request.base_url),
            "enrollment_status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        enroll_logger.error(f"🔥 [ENROLL CRASH]: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno no processamento do registro.")


@router.get("/devices/{device_id}/bootstrap", response_model=BootstrapResponse, tags=["Device Ops"])
async def get_bootstrap(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """
    Fonte Única de Verdade (SSOT).
    Retorna o estado completo para provisionamento ou recuperação.
    """
    if current_device.device_id != device_id:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    return await service.get_bootstrap_data(device_id)


@router.post("/devices/{device_id}/status", tags=["Device Ops"])
async def report_status(
    device_id: str,
    report: DeviceStatusReport,
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """Report detalhado de saúde e conformidade (Enterprise 3B)."""
    if current_device.device_id != device_id:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    await service.process_status_report(device_id, report.model_dump())
    return {"status": "received"}


@router.get("/devices", response_model=List[DeviceResponse], tags=["Dashboard"])
async def list_devices(
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    return await service.list_devices()

@router.get("/devices/summary", response_model=DeviceSummaryResponse, tags=["Dashboard"])
async def get_devices_summary(
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    return await service.get_device_summary()

@router.get("/devices/{device_id}", response_model=DeviceResponse, tags=["Dashboard"])
async def get_device(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    d = await service.get_device(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")
    return d

@router.get("/devices/{device_id}/telemetry", response_model=List[TelemetryResponse], tags=["Dashboard"])
async def get_device_telemetry(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """Retorna os dados recentes de telemetria do dispositivo."""
    d = await service.get_device(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")
    return await service.get_device_telemetry(device_id)


# ============= 🛡️ CAMADA 3: POLICY HANDSHAKE (Drift Detection) =============

@router.post("/devices/{device_id}/policy/sync", response_model=Optional[DevicePolicyResponse], tags=["Device Ops"])
async def sync_policy(
    device_id: str,
    handshake: PolicySyncHandshake,
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """
    Endpoint de Sincronização Inteligente.
    Se o hash do device bater com o do backend, retorna 204 (No Content).
    Se houver drift ou upgrade, retorna a nova política completa.
    """
    if current_device.device_id != device_id:
        raise HTTPException(status_code=403, detail="Não autorizado para este dispositivo.")
        
    config = await service.sync_policy(device_id, handshake.current_hash, handshake.current_version)
    if not config:
        return None # FastAPI retorna 200 OK com corpo vazio (ou podemos mudar para 204)
    
    return config


# ============= ⚡ CAMADA 4: COMMAND ENGINE (Idempotency) =============

@router.get("/devices/{device_id}/commands", response_model=List[DeviceCommandResponse], tags=["Dashboard"])
async def get_device_commands(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    return await service.get_command_history(device_id)

@router.get("/devices/{device_id}/commands/pending", response_model=List[DeviceCommandResponse], tags=["Device Ops"])
async def get_pending_commands(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    if current_device.device_id != device_id:
        raise HTTPException(status_code=403, detail="Acesso negado.")
        
    return await service.get_pending_commands(device_id)

@router.post("/devices/{device_id}/commands/{command_id}/ack", tags=["Device Ops"])
async def acknowledge_command(
    device_id: str, 
    command_id: int,
    req: CommandStatusUpdate,
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """O dispositivo confirma a execução ou falha de um comando."""
    if current_device.device_id != device_id:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    
    ok = await service.ack_command(
        device_id, 
        command_id, 
        req.status, 
        metadata={"error": req.error_message} if req.error_message else None
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Comando não encontrado ou já processado.")
    
    return {"status": "success", "command_id": str(command_id)}

@router.post("/devices/{device_id}/commands", response_model=DeviceCommandResponse, tags=["Dashboard Admin"])
async def create_command(
    device_id: str,
    req: DeviceCommandCreate,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """Dispara um novo comando remoto (Admin only)."""
    cmd = await service.enqueue_command(
        device_id=device_id,
        command_type=req.command_type,
        actor_id=str(current_user.email),
        payload=req.payload,
        user_id=current_user.id
    )
    return cmd


async def _enqueue_dashboard_command(
    device_id: str,
    command_type: str,
    service: MDMService,
    current_user: User,
    payload: Optional[Dict] = None,
) -> DeviceCommandResponse:
    return await service.enqueue_command(
        device_id=device_id,
        command_type=command_type,
        actor_id=str(current_user.email),
        payload=payload or {},
        user_id=current_user.id,
    )


@router.post("/devices/{device_id}/lock", response_model=DeviceCommandResponse, tags=["Dashboard Admin"])
async def lock_device(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    return await _enqueue_dashboard_command(device_id, "LOCK", service, current_user)


@router.post("/devices/{device_id}/reboot", response_model=DeviceCommandResponse, tags=["Dashboard Admin"])
async def reboot_device(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    return await _enqueue_dashboard_command(device_id, "REBOOT", service, current_user)


@router.post("/devices/{device_id}/wipe", response_model=DeviceCommandResponse, tags=["Dashboard Admin"])
async def wipe_device(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    return await _enqueue_dashboard_command(device_id, "WIPE", service, current_user)
# ============= 🛡️ CAMADA EX: TRUST & INTEGRITY (Play Integrity) =============

@router.get("/devices/nonce", response_model=NonceResponse, tags=["Device Ops"])
async def get_attestation_nonce(
    current_device: Device = Depends(get_current_device),
    attestation: AttestationService = Depends(get_attestation)
):
    """Gera um nonce seguro vinculado ao device_id e tenant_id para atestação."""
    nonce = await attestation.generate_nonce(current_device.device_id, str(current_device.tenant_id))
    return {"nonce": nonce, "expires_in": 300}

@router.post("/devices/attest", tags=["Device Ops"])
async def verify_device_attestation(
    req: AttestationRequest,
    current_device: Device = Depends(get_current_device),
    attestation: AttestationService = Depends(get_attestation),
    service: MDMService = Depends(get_service)
):
    """Valida o token de integridade e atualiza o estado de Trust do dispositivo."""
    result = await attestation.verify_device_integrity(
        current_device.device_id,
        str(current_device.tenant_id),
        req.integrity_token, 
        req.nonce
    )
    
    # Atualiza o status do dispositivo com o novo Trust Score
    await service.process_status_report(current_device.device_id, {
        "health": result["status"],
        "trust_score": result["trust_score"],
        "reason": result.get("reason", "ATTESTATION_SUCCESS")
    })
    
    return result


# ============= 📊 AUDITORIA & TELEMETRIA =============

@router.get("/logs", tags=["SaaS Admin"])
async def get_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    service: MDMService = Depends(get_service),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Somente administradores podem consultar logs.")

    from backend.models.audit_log import AuditLog

    result = await service.repo.db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return [serialize_audit_log(log) for log in result.scalars().all()]

@router.post("/checkin", tags=["Device Ops"])
async def checkin(
    device_id: str,
    payload: Dict,
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    if current_device.device_id != device_id:
        raise HTTPException(status_code=403, detail="Acesso negado.")
        
    await service.process_checkin(device_id, payload)
    return {"status": "ok"}
