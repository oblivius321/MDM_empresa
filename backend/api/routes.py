from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from typing import List, Dict, Optional
from backend.api.websockets import manager
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.mdm_service import MDMService
from backend.repositories.device_repo import DeviceRepository
from backend.core.database import get_db
from backend.schemas.device import DeviceCreate, DeviceResponse, PolicyCreate, DeviceUpdate, Policy, LogResponse, CommandResponse, EnrollmentResponse
from backend.schemas.user import DeviceEnrollRequest
from backend.api.auth import get_current_user
from backend.api.device_auth import get_current_device
from backend.core.limiter import limiter
from backend.models.device import Device
from backend.models.user import User
import datetime
import os

router = APIRouter()

def get_repo(db: AsyncSession = Depends(get_db)) -> DeviceRepository:
    return DeviceRepository(db)

def get_service(repo: DeviceRepository = Depends(get_repo)) -> MDMService:
    return MDMService(repo)


# ============= ENROLL SEGURO COM BOOTSTRAP_SECRET =============
@router.post("/enroll", response_model=dict, tags=["Dispositivos"])
@limiter.limit("10/hour")
async def enroll(
    request: Request,
    req: DeviceEnrollRequest, 
    service: MDMService = Depends(get_service)
):
    """
    Enroll SEGURO de dispositivo Android.
    """
    from backend.core.config import BOOTSTRAP_SECRET
    import logging
    
    logger_error = logging.getLogger("error")
    logger_security = logging.getLogger("security")
    
    # 🔍 1. Validação de Segurança Crítica (Bootstrap Secret)
    if not req.bootstrap_secret or req.bootstrap_secret != BOOTSTRAP_SECRET:
        logger_security.warning(
            f"❌ [Security Denial] Tentativa de enroll com SECRET INVÁLIDO | "
            f"device_id: {req.device_id}, ip: {request.client.host}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de segurança bootstrapping inválido."
        )
    
    # 🔍 2. Validação de Formato de Dados
    if not req.device_id or len(req.device_id) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O device_id deve ter pelo menos 3 caracteres."
        )

    try:
        # ⚙️ 3. Processamento de Enroll no Service (possui lógica de UPSERT/Filtro)
        device, device_token = await service.enroll_device(
            req.device_id, 
            req.name, 
            req.device_type,
            **(req.extra_data or {})
        )
        
        # 📡 4. Notificação via WebSocket para o Painel
        try:
            await manager.broadcast_to_dashboards({
                "type": "DEVICE_ENROLLED",
                "device_id": device.device_id,
                "name": device.name,
                "status": device.status
            })
        except Exception as ws_err:
            logger_error.error(f"⚠️ Erro ao notificar dashboards (non-critical): {str(ws_err)}")
        
        return {
            "message": "Dispositivo registrado com sucesso e autorizado.",
            "device_id": device.device_id,
            "device_token": device_token,
            "api_url": os.getenv("API_URL", "http://localhost:8000"),
            "enrollment_status": "success"
        }

    except HTTPException as http_ex:
        # Repassa exceções controladas da camada de service (ex: 403, 400)
        raise http_ex

    except Exception as e:
        # 🛑 5. Tratamento de Erros Inesperados (Rollback já foi feito no Repo se necessário)
        error_type = type(e).__name__
        logger_error.error(
            f"🔥 [ENROLL CRASH] Erro crítico inesperado: {error_type} | "
            f"MSG: {str(e)} | device_id: {req.device_id}"
        )
        
        # Em produção, ocultamos detalhes sensíveis do erro no retorno JSON
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocorreu um erro interno ao processar seu registro. Tente novamente em instantes."
        )


@router.get("/devices", response_model=List[DeviceResponse], response_model_by_alias=True)
async def list_devices(
    status: Optional[str] = None,
    search: Optional[str] = None,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    devices = await service.list_devices()
    
    if status:
        if status == 'online':
             devices = [d for d in devices if d.is_active or d.status == 'online']
        elif status == 'offline':
             devices = [d for d in devices if not d.is_active or d.status == 'offline']
        else:
             devices = [d for d in devices if d.status == status]
             
    if search:
        search_lower = search.lower()
        devices = [d for d in devices if search_lower in d.name.lower() or search_lower in d.device_id.lower()]
        
    return devices


@router.get("/devices/summary")
async def get_summary(
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    devices = await service.list_devices()
    total = len(devices)
    online = sum(1 for d in devices if d.status == 'online' or d.is_active)
    offline = sum(1 for d in devices if d.status == 'offline' or (not d.is_active and d.status != 'online'))
    locked = sum(1 for d in devices if d.status == 'locked')
    
    return {
        "total": total,
        "online": online,
        "offline": offline,
        "locked": locked,
        "last_global_checkin": None
    }


@router.delete("/devices/{device_id}")
async def remove_device(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    ok = await service.remove_device(device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "removed"}


@router.get("/devices/{device_id}", response_model=DeviceResponse, response_model_by_alias=True)
async def get_device(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    d = await service.get_device(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    return d

@router.get("/devices/{device_id}/telemetry")
async def get_device_telemetry(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    telemetry = await service.repo.get_telemetry(device_id)
    if not telemetry:
        return {} # Return empty object instead of 404 to gracefully handle devices with no telemetry yet
    return {
        "battery_level": telemetry.battery_level,
        "is_charging": telemetry.is_charging,
        "free_disk_space_mb": telemetry.free_disk_space_mb,
        "installed_apps": telemetry.installed_apps,
        "location": {
            "latitude": telemetry.latitude,
            "longitude": telemetry.longitude
        } if telemetry.latitude and telemetry.longitude else None,
        "foreground_app": telemetry.foreground_app,
        "timestamp": telemetry.timestamp
    }


@router.post("/devices/{device_id}/lock", tags=["Comandos"])
async def lock_device(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    """
    Envia comando de bloqueio de tela para o device.

    Fluxo:
      1. Persiste na CommandQueue (status=pending)
      2. Tenta entrega imediata via WebSocket → status=sent
      3. Se offline → mantém pending para entrega no reconnect
    """
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    from backend.api.command_dispatcher import dispatch_command
    try:
        result = await dispatch_command(
            service, manager, device_id, "lock_device",
            issued_by=current_user.email,
        )
    except OverflowError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return result


@router.post("/devices/{device_id}/reboot", tags=["Comandos"])
async def reboot_device(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    """
    Envia comando de reinicialização para o device.
    """
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    from backend.api.command_dispatcher import dispatch_command
    try:
        result = await dispatch_command(
            service, manager, device_id, "reboot_device",
            issued_by=current_user.email,
        )
    except OverflowError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return result


@router.post("/devices/{device_id}/wipe", tags=["Comandos"])
async def wipe_device(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user),
):
    """
    Envia comando de wipe (reset de fábrica) para o device.
    Comando irreversível — confirmar no frontend antes de chamar.
    """
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    from backend.api.command_dispatcher import dispatch_command
    try:
        result = await dispatch_command(
            service, manager, device_id, "wipe_device",
            issued_by=current_user.email,
        )
    except OverflowError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return result


@router.post("/devices/{device_id}/checkin", tags=["Dispositivos"])
@limiter.limit("30/minute")
async def checkin_device(
    request: Request,
    device_id: str, 
    payload: Dict, 
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """Endpoint restrito para check-in de dispositivos (chamado pelo app Android)"""
    # ✅ SEGURANÇA (P1.1): Valida que device_id da URL corresponde ao device do token
    if current_device.device_id != device_id:
        import logging
        logger = logging.getLogger("security")
        logger.error(f"⚠️ DEVICE MISMATCH (checkin): token={current_device.device_id}, url={device_id}")
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Unauthorized device")
        
    await service.process_checkin(device_id, payload)
    
    # Notifica dashboards que o device piscou o radar
    await manager.broadcast_to_dashboards({
        "type": "DEVICE_CHECKIN",
        "device_id": device_id,
        "status": "online"
    })
    
    return {"status": "checked_in"}

@router.get("/devices/{device_id}/commands/pending", response_model=List[CommandResponse], tags=["Dispositivos"])
async def get_pending_commands(
    device_id: str, 
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """Endpoint restrito para dispositivos buscarem comandos pendentes"""
    # ✅ SEGURANÇA (P1.1): Valida que device_id da URL corresponde ao device do token
    if current_device.device_id != device_id:
        import logging
        logger = logging.getLogger("security")
        logger.error(f"⚠️ DEVICE MISMATCH (pending_commands): token={current_device.device_id}, url={device_id}")
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Unauthorized device")
        
    pending = await service.get_pending_commands(device_id)
    return [{"id": str(c.id), "command": c.command, "payload": c.payload} for c in pending]

@router.post("/devices/{device_id}/commands/{command_id}/ack", tags=["Dispositivos"])
async def acknowledge_command(
    device_id: str, 
    command_id: int, 
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """
    Dispositivo reconhece que recebeu o comando.
    
    ✅ SEGURO (P1.1): Valida que device_id da URL corresponde ao device do token.
    Previne device A de reconhecer comando de device B.
    """
    # Validar que current_device pertence a este device_id
    if current_device.device_id != device_id:
        import logging
        logger = logging.getLogger("security")
        logger.error(f"⚠️ DEVICE MISMATCH: token={current_device.device_id}, url={device_id}")
        raise HTTPException(status_code=403, detail="Unauthorized device")
    
    # Usar método seguro que valida propriedade
    ok = await service.repo.acknowledge_command_secure(device_id, command_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"status": "acknowledged", "command_id": command_id}

@router.post("/devices/{device_id}/commands/{command_id}/status", tags=["Dispositivos"])
async def update_command_status(
    device_id: str, 
    command_id: int, 
    payload: Dict, 
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """
    Dispositivo reporta status final de execução do comando.
    
    ✅ SEGURO (P1.1): Valida ownership do comando antes de atualizar.
    Previne device A de modificar status de comando de device B.
    """
    # Validar que current_device pertence a este device_id
    if current_device.device_id != device_id:
        import logging
        logger = logging.getLogger("security")
        logger.error(f"⚠️ DEVICE MISMATCH: token={current_device.device_id}, url={device_id}")
        raise HTTPException(status_code=403, detail="Unauthorized device")
    
    status = payload.get("status", "completed")
    error_msg = payload.get("error_message")
    
    # Usar métodos seguros que validam propriedade
    if status == "completed":
        ok = await service.repo.complete_command_secure(device_id, command_id, error_msg)
    elif status == "failed":
        ok = await service.repo.fail_command_secure(device_id, command_id, error_msg or "Unknown error")
    else:
        ok = False
    
    if not ok:
        raise HTTPException(status_code=404, detail="Command not found")
    
    return {"status": "updated", "command_id": command_id, "new_status": status}

@router.get("/devices/{device_id}/commands/{command_id}/status", tags=["Dispositivos"])
async def get_command_status(
    device_id: str,
    command_id: int,
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """
    Dispositivo consulta status de um comando.
    
    ✅ SEGURO (P1.1): Valida ownership do comando antes de retornar status.
    Previne device A de consultar status de comando de device B.
    """
    # Validar que current_device pertence a este device_id
    if current_device.device_id != device_id:
        import logging
        logger = logging.getLogger("security")
        logger.error(f"⚠️ DEVICE MISMATCH: token={current_device.device_id}, url={device_id}")
        raise HTTPException(status_code=403, detail="Unauthorized device")
    
    # Usar método seguro que valida propriedade
    status = await service.repo.get_command_status_secure(device_id, command_id)
    if not status:
        raise HTTPException(status_code=404, detail="Command not found")
    return status

@router.get("/devices/{device_id}/commands/failed", response_model=List[CommandResponse], tags=["Dispositivos"])
async def get_failed_commands(
    device_id: str,
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """Retorna comandos que falharam para quem tentar reexecutar"""
    failed = await service.repo.get_failed_commands(device_id)
    return [{"id": str(c.id), "command": c.command, "payload": c.payload, "error": c.error_message} for c in failed]



@router.get("/commands", tags=["Auditoria"])
async def get_commands_audit(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    action: Optional[str] = None,
    issued_by: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Lista histórico de comandos para auditoria enterprise.
    (Somente admins autenticados via JWT).
    """
    cmds = await service.repo.get_commands_audit(
        device_id=device_id,
        status=status,
        action=action,
        issued_by=issued_by,
        limit=limit,
        offset=offset
    )
    return cmds


@router.get("/policies", response_model=List[Policy])
async def list_policies(service: MDMService = Depends(get_service), current_user: User = Depends(get_current_user)):
    return await service.list_policies()

@router.post("/policies", response_model=Policy)
async def create_global_policy(policy_data: PolicyCreate, service: MDMService = Depends(get_service), current_user: User = Depends(get_current_user)):
    policy_dict = policy_data.model_dump()
    # Create the policy as a global template (device_id=None)
    policy = await service.repo.add_policy(None, policy_dict)
    
    # Automatically queue it for all devices since it's a global policy
    devices = await service.list_devices()
    for d in devices:
        await service.repo.add_command(d.device_id, "apply_policy", payload=policy_dict)
        await manager.send_command_to_device(d.device_id, {"command": "apply_policy", "payload": policy_dict})
        
    return policy

@router.get("/policies/{policy_id}", response_model=Policy)
async def get_policy(policy_id: str, service: MDMService = Depends(get_service), current_user: User = Depends(get_current_user)):
    return {"id": policy_id, "name": f"Policy {policy_id}", "type": "security", "status": "active", "created_at": None}


@router.post("/devices/{device_id}/policies")
async def apply_policy_to_device(
    device_id: str, 
    policy_data: PolicyCreate, 
    service: MDMService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    # Pass dict to apply_policy
    ok = await service.apply_policy(device_id, policy_data.model_dump())
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
        
    await manager.send_command_to_device(device_id, {
        "command": "apply_policy", 
        "payload": policy_data.model_dump()
    })
    return {"status": "applied"}


@router.get("/logs", response_model=List[LogResponse])
async def get_logs(device_id: Optional[str] = None, page: int = 1, size: int = 50, service: MDMService = Depends(get_service), current_user: User = Depends(get_current_user)):
    return [
        {"id": "1", "device_id": device_id or "all", "type": "system", "message": "System logs retrieved", "severity": "info", "timestamp": datetime.datetime.utcnow()}
    ]
