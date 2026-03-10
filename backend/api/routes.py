from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Optional
from backend.api.websockets import manager
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.mdm_service import MDMService
from backend.repositories.device_repo import DeviceRepository
from backend.core.database import get_db
from backend.schemas.device import DeviceCreate, DeviceResponse, PolicyCreate, DeviceUpdate, Policy, LogResponse, CommandResponse, EnrollmentResponse
from backend.api.auth import get_current_user
from backend.api.device_auth import get_current_device
from backend.models.device import Device
from backend.models.user import User
import datetime

router = APIRouter()

def get_repo(db: AsyncSession = Depends(get_db)) -> DeviceRepository:
    return DeviceRepository(db)

def get_service(repo: DeviceRepository = Depends(get_repo)) -> MDMService:
    return MDMService(repo)


@router.post("/enroll", response_model=EnrollmentResponse, tags=["Dispositivos"])
async def enroll(
    req: DeviceCreate, 
    service: MDMService = Depends(get_service)
):
    """Endpoint público para enroll de dispositivos (chamado pelo app Android)"""
    extra_fields = req.model_dump(exclude={"device_id", "name", "device_type"}, exclude_unset=True)
    device, device_token = await service.enroll_device(req.device_id, req.name, req.device_type, **extra_fields)
    
    # Notifica os dashboards de um novo dispositivo na frota
    await manager.broadcast_to_dashboards({
        "type": "DEVICE_ENROLLED",
        "device_id": device.device_id,
        "name": device.name,
        "status": device.status
    })
    
    # Adicionamos manualmente o token ao payload de resposta convertido
    response_data = device.__dict__.copy()
    response_data["device_token"] = device_token
    return response_data


@router.get("/devices", response_model=List[DeviceResponse])
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


@router.get("/devices/{device_id}", response_model=DeviceResponse)
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


@router.post("/devices/{device_id}/lock")
async def lock_device(device_id: str, service: MDMService = Depends(get_service), current_user: User = Depends(get_current_user)):
    d = await service.update_device(device_id, {"status": "locked"})
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
        
    await manager.send_command_to_device(device_id, {"command": "lock_device"})
    return {"status": "locked"}


@router.post("/devices/{device_id}/reboot")
async def reboot_device(device_id: str, service: MDMService = Depends(get_service), current_user: User = Depends(get_current_user)):
    # Since we added command queues, let's use it for reboot too
    ok = await service.repo.add_command(device_id, "reboot_device")
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    
    await manager.send_command_to_device(device_id, {"command": "reboot_device"})
    return {"status": "command_sent", "command": "reboot_device"}

@router.post("/devices/{device_id}/wipe")
async def wipe_device(device_id: str, service: MDMService = Depends(get_service), current_user: User = Depends(get_current_user)):
    ok = await service.wipe_device(device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
        
    await manager.send_command_to_device(device_id, {"command": "wipe_device"})
    return {"status": "command_sent", "command": "wipe_device"}


@router.post("/devices/{device_id}/checkin", tags=["Dispositivos"])
async def checkin_device(
    device_id: str, 
    payload: Dict, 
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """Endpoint restrito para check-in de dispositivos (chamado pelo app Android)"""
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
    pending = await service.get_pending_commands(device_id)
    return [{"id": str(c.id), "command": c.command, "payload": c.payload} for c in pending]

@router.post("/devices/{device_id}/commands/{command_id}/ack", tags=["Dispositivos"])
async def acknowledge_command(
    device_id: str, 
    command_id: int, 
    service: MDMService = Depends(get_service),
    current_device: Device = Depends(get_current_device)
):
    """Dispositivo reconhece que recebeu o comando"""
    ok = await service.repo.acknowledge_command(command_id)
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
    """Dispositivo reporta status final de execução do comando"""
    status = payload.get("status", "completed")
    error_msg = payload.get("error_message")
    
    if status == "completed":
        ok = await service.repo.complete_command(command_id, error_msg)
    elif status == "failed":
        ok = await service.repo.fail_command(command_id, error_msg or "Unknown error")
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
    # Permite tanto device quanto user acessarem (no mínimo um deles deve estar logado)
    # Aqui, para manter a checagem dupla limpa, vamos focar no uso pelo device:
    current_device: Device = Depends(get_current_device)
):
    """Dispositivo ou admin consulta status de um comando"""
    status = await service.repo.get_command_status(command_id)
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
