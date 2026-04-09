from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from typing import List, Dict, Optional
from backend.api.websockets import manager
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.mdm_service import MDMService
from backend.repositories.device_repo import DeviceRepository
from backend.core.database import get_db
from backend.schemas.device import (
    DeviceCreate, DeviceResponse, DeviceUpdate, DeviceFullResponse, EnrollmentResponse,
    AttestationRequest, NonceResponse
)
from backend.services.attestation_service import AttestationService
from backend.services.redis_service import RedisService
from backend.schemas.policy import (
    ProvisioningProfileCreate, ProvisioningProfileResponse, ProvisioningProfileUpdate,
    DevicePolicyResponse, PolicySyncHandshake, DeviceCommandResponse, CommandStatusUpdate,
    DeviceCommandCreate, BootstrapResponse, DeviceStatusReport
)
from backend.schemas.user import DeviceEnrollRequest
from backend.schemas.telemetry import TelemetryResponse
from backend.api.auth import get_current_user
from backend.api.device_auth import get_current_device
from backend.core.limiter import limiter
from backend.models.device import Device
from backend.models.user import User
import datetime
import os
import uuid
import logging

router = APIRouter()

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

@router.post("/enroll", response_model=EnrollmentResponse, tags=["Device Ops"])
@limiter.limit("5/minute")
async def enroll_device(
    request: Request,
    req: DeviceEnrollRequest, 
    service: MDMService = Depends(get_service)
):
    """
    Novo Enrollment (SaaS Nível):
    O dispositivo informa obrigatóriamente um `profile_id` válido para ser aceito.
    """
    import logging
    try:
        expected_secret = os.getenv("ENROLLMENT_SECRET", "padrao-inseguro-troque-em-prod")
        if req.bootstrap_secret != expected_secret:
            logging.getLogger("error").warning(f"🚨 Tentativa de Enroll bloqueada para {req.device_id} (Secret inválido)")
            raise HTTPException(status_code=403, detail="Autenticação de bootstrap falhou.")

        # Realiza o enroll criando a associação com a política inicial
        device, token = await service.enroll_device(
            device_id=req.device_id,
            name=req.name,
            device_type=req.device_type,
            profile_id=req.profile_id,
            **req.extra_data if req.extra_data else {}
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
        logging.getLogger("error").error(f"🔥 [ENROLL CRASH]: {str(e)}")
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
    command_id: uuid.UUID,
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

@router.get("/audit", tags=["SaaS Admin"])
async def get_audit_logs(
    limit: int = 100,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    from backend.models.audit_log import AuditLog
    from sqlalchemy.future import select
    result = await service.repo.db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return result.scalars().all()

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
