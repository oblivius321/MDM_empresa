from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.mdm_service import MDMService
from backend.repositories.device_repo import DeviceRepository
from backend.core.database import get_db
from backend.schemas.device import DeviceCreate, DeviceResponse, PolicyCreate, DeviceUpdate, Policy, LogResponse
import datetime

router = APIRouter()

def get_repo(db: AsyncSession = Depends(get_db)) -> DeviceRepository:
    return DeviceRepository(db)

def get_service(repo: DeviceRepository = Depends(get_repo)) -> MDMService:
    return MDMService(repo)


@router.post("/enroll", response_model=DeviceResponse)
async def enroll(
    req: DeviceCreate, 
    service: MDMService = Depends(get_service)
):
    extra_fields = req.model_dump(exclude={"device_id", "name", "device_type"}, exclude_unset=True)
    device = await service.enroll_device(req.device_id, req.name, req.device_type, **extra_fields)
    return device


@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(
    status: Optional[str] = None,
    search: Optional[str] = None,
    service: MDMService = Depends(get_service)
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
async def get_summary(service: MDMService = Depends(get_service)):
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
    service: MDMService = Depends(get_service)
):
    ok = await service.remove_device(device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "removed"}


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str, 
    service: MDMService = Depends(get_service)
):
    d = await service.get_device(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    return d


@router.post("/devices/{device_id}/lock")
async def lock_device(device_id: str, service: MDMService = Depends(get_service)):
    d = await service.update_device(device_id, {"status": "locked"})
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "locked"}


@router.post("/devices/{device_id}/reboot")
async def reboot_device(device_id: str, service: MDMService = Depends(get_service)):
    # Since we added command queues, let's use it for reboot too
    ok = await service.repo.add_command(device_id, "reboot_device")
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "command_sent", "command": "reboot_device"}

@router.post("/devices/{device_id}/wipe")
async def wipe_device(device_id: str, service: MDMService = Depends(get_service)):
    ok = await service.wipe_device(device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "command_sent", "command": "wipe_device"}


@router.post("/devices/{device_id}/sync")
async def sync_device(device_id: str, service: MDMService = Depends(get_service)):
    await service.update_device(device_id, {"last_checkin": datetime.datetime.utcnow(), "status": "online"})
    
    pending = await service.get_pending_commands(device_id)
    commands_list = [{"id": str(c.id), "command": c.command, "payload": c.payload} for c in pending]
    
    # Also fetch the latest policy constraints to return in heartbeat
    device = await service.get_device(device_id)
    active_policy = {}
    if device and device.policies:
        # Assuming the last added policy is the active one
        last_policy = device.policies[-1]
        active_policy = {
            "camera_disabled": last_policy.camera_disabled,
            "install_unknown_sources": last_policy.install_unknown_sources,
            "factory_reset_disabled": last_policy.factory_reset_disabled,
            "kiosk_mode": last_policy.kiosk_mode
        }
    
    return {
        "status": "synced",
        "commands": commands_list,
        "policy": active_policy
    }


@router.get("/policies", response_model=List[Policy])
async def list_policies(service: MDMService = Depends(get_service)):
    return await service.list_policies()

@router.post("/policies", response_model=Policy)
async def create_global_policy(policy_data: PolicyCreate, service: MDMService = Depends(get_service)):
    policy_dict = policy_data.model_dump()
    # Create the policy as a global template (device_id=None)
    policy = await service.repo.add_policy(None, policy_dict)
    
    # Automatically queue it for all devices since it's a global policy
    devices = await service.list_devices()
    for d in devices:
        await service.repo.add_command(d.device_id, "apply_policy", payload=policy_dict)
        
    return policy

@router.get("/policies/{policy_id}", response_model=Policy)
async def get_policy(policy_id: str, service: MDMService = Depends(get_service)):
    return {"id": policy_id, "name": f"Policy {policy_id}", "type": "security", "status": "active", "created_at": None}


@router.post("/devices/{device_id}/policies")
async def apply_policy_to_device(
    device_id: str, 
    policy_data: PolicyCreate, 
    service: MDMService = Depends(get_service)
):
    # Pass dict to apply_policy
    ok = await service.apply_policy(device_id, policy_data.model_dump())
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "applied"}


@router.get("/logs", response_model=List[LogResponse])
async def get_logs(device_id: Optional[str] = None, page: int = 1, size: int = 50, service: MDMService = Depends(get_service)):
    return [
        {"id": "1", "device_id": device_id or "all", "type": "system", "message": "System logs retrieved", "severity": "info", "timestamp": datetime.datetime.utcnow()}
    ]
