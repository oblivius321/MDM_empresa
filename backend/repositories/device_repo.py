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
    
    async def update_command_status(self, command_id: int, status: str):
        from backend.models.policy import CommandQueue
        result = await self.db.execute(select(CommandQueue).where(CommandQueue.id == command_id))
        cmd = result.scalars().first()
        if cmd:
            cmd.status = status
            await self.db.commit()
            return cmd
        return None

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

    async def add_telemetry(self, device_id: str, payload_data: dict):
        from backend.models.telemetry import DeviceTelemetry
        telemetry = DeviceTelemetry(
            device_id=device_id,
            battery_level=payload_data.get("battery_level"),
            is_charging=payload_data.get("is_charging"),
            free_disk_space_mb=payload_data.get("free_disk_space_mb"),
            installed_apps=payload_data.get("installed_apps", []),
            latitude=payload_data.get("latitude"),
            longitude=payload_data.get("longitude"),
            foreground_app=payload_data.get("foreground_app"),
            daily_usage_stats=payload_data.get("daily_usage_stats", {})
        )
        self.db.add(telemetry)
        await self.db.commit()
        return telemetry

    async def get_telemetry(self, device_id: str):
        from backend.models.telemetry import DeviceTelemetry
        result = await self.db.execute(
            select(DeviceTelemetry).where(DeviceTelemetry.device_id == device_id).order_by(DeviceTelemetry.timestamp.desc()).limit(1)
        )
        return result.scalars().first()

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
        from datetime import datetime
        
        result = await self.db.execute(
            select(CommandQueue).where(
                CommandQueue.device_id == device_id,
                CommandQueue.status.in_(["pending", "sent"])
            ).order_by(CommandQueue.created_at.asc())
        )
        commands = result.scalars().all()
        
        # Mark as sent quando for entregue ao dispositivo
        for c in commands:
            if c.status == "pending":
                c.status = "sent"
                c.sent_at = datetime.utcnow()
        
        if commands:
            await self.db.commit()
        return commands

    async def acknowledge_command(self, command_id: int) -> bool:
        """Marca um comando como reconhecido pelo dispositivo"""
        from backend.models.policy import CommandQueue
        from datetime import datetime
        
        result = await self.db.execute(
            select(CommandQueue).where(CommandQueue.id == command_id)
        )
        cmd = result.scalars().first()
        
        if not cmd:
            return False
        
        cmd.status = "acked"
        cmd.acked_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def complete_command(self, command_id: int, error_msg: Optional[str] = None) -> bool:
        """Marca um comando como completado pelo dispositivo"""
        from backend.models.policy import CommandQueue
        from datetime import datetime
        
        result = await self.db.execute(
            select(CommandQueue).where(CommandQueue.id == command_id)
        )
        cmd = result.scalars().first()
        
        if not cmd:
            return False
        
        cmd.status = "completed" if not error_msg else "failed"
        cmd.completed_at = datetime.utcnow()
        cmd.error_message = error_msg
        await self.db.commit()
        return True

    async def fail_command(self, command_id: int, error_msg: str) -> bool:
        """Marca comando como falhado e incrementa retry count"""
        from backend.models.policy import CommandQueue
        from datetime import datetime
        
        result = await self.db.execute(
            select(CommandQueue).where(CommandQueue.id == command_id)
        )
        cmd = result.scalars().first()
        
        if not cmd:
            return False
        
        cmd.retry_count += 1
        
        if cmd.retry_count >= cmd.max_retries:
            cmd.status = "failed"
            cmd.error_message = f"{error_msg} (max retries exceeded)"
        else:
            # Reset to pending para retry
            cmd.status = "pending"
            cmd.sent_at = None
        
        cmd.completed_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def get_command_status(self, command_id: int) -> Optional[dict]:
        """Retorna o status completo de um comando"""
        from backend.models.policy import CommandQueue
        
        result = await self.db.execute(
            select(CommandQueue).where(CommandQueue.id == command_id)
        )
        cmd = result.scalars().first()
        
        if not cmd:
            return None
        
        return {
            "id": cmd.id,
            "device_id": cmd.device_id,
            "command": cmd.command,
            "status": cmd.status,
            "retry_count": cmd.retry_count,
            "max_retries": cmd.max_retries,
            "created_at": cmd.created_at,
            "sent_at": cmd.sent_at,
            "acked_at": cmd.acked_at,
            "completed_at": cmd.completed_at,
            "error_message": cmd.error_message
        }

    async def get_failed_commands(self, device_id: Optional[str] = None) -> List["CommandQueue"]:
        """Retorna comandos que falharam"""
        from backend.models.policy import CommandQueue
        
        query = select(CommandQueue).where(
            CommandQueue.status == "failed"
        )
        
        if device_id:
            query = query.where(CommandQueue.device_id == device_id)
        
        query = query.order_by(CommandQueue.created_at.desc()).limit(100)
        
        result = await self.db.execute(query)
        return result.scalars().all()
