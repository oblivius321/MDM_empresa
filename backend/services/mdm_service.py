from typing import Dict, List, Optional
from backend.repositories.device_repo import DeviceRepository
from backend.models.device import Device
from backend.models.policy import Policy


class MDMService:
    def __init__(self, repo: DeviceRepository):
        self.repo = repo

    async def enroll_device(self, device_id: str, name: str, device_type: str, **kwargs) -> Device:
        device = await self.repo.get(device_id)
        if device:
            # Device exists, update status and other fields
            updates = {"is_active": True, **kwargs}
            updated_device = await self.repo.update_device(device_id, updates)
            if updated_device:
                return updated_device
            return device # Fallback if update fails
        
        # New device
        # Pass kwargs to constructor
        new_device = Device(device_id=device_id, name=name, device_type=device_type, is_active=True, status="online", **kwargs)
        return await self.repo.add(new_device)

    async def update_device(self, device_id: str, updates: Dict) -> Optional[Device]:
        return await self.repo.update_device(device_id, updates)

    async def remove_device(self, device_id: str) -> bool:
        return await self.repo.remove(device_id)

    async def apply_policy(self, device_id: str, policy_data: Dict) -> bool:
        policy = await self.repo.add_policy(device_id, policy_data)
        return policy is not None

    async def list_devices(self) -> List[Device]:
        return await self.repo.list()

    async def get_device(self, device_id: str) -> Optional[Device]:
        return await self.repo.get(device_id)
