from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict
from backend.models.device import Device
from backend.models.policy import Policy


class DeviceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, device: Device) -> Device:
        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)
        return device # Return refreshed instance

    async def get(self, device_id: str) -> Optional[Device]:
        result = await self.db.execute(
            select(Device).options(selectinload(Device.policies)).where(Device.device_id == device_id)
        )
        return result.scalars().first()
    
    async def update_device(self, device_id: str, updates: Dict) -> Optional[Device]:
        device = await self.get(device_id)
        if not device:
            return None
        
        for key, value in updates.items():
            if hasattr(device, key) and value is not None:
                setattr(device, key, value)
        
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def exists(self, device_id: str) -> bool:
        result = await self.db.execute(select(Device).where(Device.device_id == device_id))
        return result.scalars().first() is not None

    async def remove(self, device_id: str) -> bool:
        device = await self.get(device_id)
        if device:
            await self.db.delete(device)
            await self.db.commit()
            return True
        return False

    async def list(self) -> List[Device]:
        result = await self.db.execute(select(Device).options(selectinload(Device.policies)))
        return result.scalars().all()

    async def set_active(self, device_id: str, active: bool) -> bool:
        device = await self.get(device_id)
        if not device:
            return False
        device.is_active = active
        await self.db.commit()
        return True

    async def add_policy(self, device_id: str, policy_data: dict) -> Optional[Policy]:
        # We need the local device_id (string) to find user, but Policy stores string FK?
        # Device model has device_id (string) as unique index.
        # Policy model uses device_id (string) as FK.
        # This is correct.
        
        policy = Policy(device_id=device_id, policy_data=policy_data)
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        return policy
