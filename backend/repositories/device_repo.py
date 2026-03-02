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
        policy = Policy(
            device_id=device_id,
            name=policy_data.get("name", "Default Policy"),
            type=policy_data.get("type", "security"),
            camera_disabled=policy_data.get("camera_disabled", False),
            install_unknown_sources=policy_data.get("install_unknown_sources", False),
            factory_reset_disabled=policy_data.get("factory_reset_disabled", False),
            kiosk_mode=policy_data.get("kiosk_mode", None),
            policy_data=policy_data.get("policy_data", {})
        )
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    async def list_policies(self) -> List[Policy]:
        result = await self.db.execute(select(Policy))
        return result.scalars().all()

    async def add_command(self, device_id: str, command: str, payload: dict = None) -> "CommandQueue":
        from backend.models.policy import CommandQueue
        cmd = CommandQueue(device_id=device_id, command=command, payload=payload or {}, status="pending")
        self.db.add(cmd)
        await self.db.commit()
        await self.db.refresh(cmd)
        return cmd

    async def get_pending_commands(self, device_id: str) -> List["CommandQueue"]:
        from backend.models.policy import CommandQueue
        result = await self.db.execute(
            select(CommandQueue).where(
                CommandQueue.device_id == device_id,
                CommandQueue.status == "pending"
            ).order_by(CommandQueue.created_at.asc())
        )
        commands = result.scalars().all()
        # Mark as delivered
        for c in commands:
            c.status = "delivered"
        if commands:
            await self.db.commit()
        return commands
