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
        """Adiciona um novo registro com rollback automático em caso de erro."""
        try:
            self.db.add(device)
            await self.db.commit()
            await self.db.refresh(device)
            return device
        except Exception as e:
            await self.db.rollback()
            raise e

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

    async def update_device_command_status(
        self,
        command_id: int,
        status: str,
        sent_at=None,
        acked_at=None,
    ):
        """
        Atualiza status de um comando com timestamps opcionais.
        Usado pelo dispatcher para pending→sent e pelo receiver para sent→acked.
        """
        from backend.models.policy import CommandQueue
        result = await self.db.execute(select(CommandQueue).where(CommandQueue.id == command_id))
        cmd = result.scalars().first()
        if cmd:
            cmd.status = status
            if sent_at is not None:
                cmd.sent_at = sent_at
            if acked_at is not None:
                cmd.acked_at = acked_at
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

    # ============= COMMAND OPERATIONS COM VALIDAÇÃO DE PROPRIEDADE (P1.1) =============
    async def acknowledge_command_secure(self, device_id: str, command_id: int) -> bool:
        """
        ✅ SEGURO: Valida que o comando pertence ao device antes de reconhecer.
        Previne device A de reconhecer comando de device B.
        """
        from backend.models.policy import CommandQueue
        from datetime import datetime
        
        # Buscar comando e validar que pertence a este device
        result = await self.db.execute(
            select(CommandQueue).where(
                CommandQueue.id == command_id,
                CommandQueue.device_id == device_id
            )
        )
        cmd = result.scalars().first()
        
        if not cmd:
            # Log para detecção de ataque
            import logging
            logger = logging.getLogger("security")
            logger.warning(f"⚠️ COMMAND ISOLATION VIOLATION: device_id={device_id} tentou acessar command_id={command_id}")
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

    # ✅ SEGURO: Valida propriedade de device
    async def complete_command_secure(self, device_id: str, command_id: int, error_msg: Optional[str] = None) -> bool:
        """
        ✅ SEGURO: Valida que o comando pertence ao device antes de marcar como completado.
        Previne device A de completar comando de device B.
        """
        from backend.models.policy import CommandQueue
        from datetime import datetime
        
        result = await self.db.execute(
            select(CommandQueue).where(
                CommandQueue.id == command_id,
                CommandQueue.device_id == device_id
            )
        )
        cmd = result.scalars().first()
        
        if not cmd:
            # Log para detecção de ataque
            import logging
            logger = logging.getLogger("security")
            logger.warning(f"⚠️ COMMAND ISOLATION VIOLATION: device_id={device_id} tentou atualizar status de command_id={command_id}")
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

    # ✅ SEGURO: Valida propriedade de device
    async def fail_command_secure(self, device_id: str, command_id: int, error_msg: str) -> bool:
        """
        ✅ SEGURO: Valida propriedade de device antes de marcar como falhado.
        """
        from backend.models.policy import CommandQueue
        from datetime import datetime
        
        result = await self.db.execute(
            select(CommandQueue).where(
                CommandQueue.id == command_id,
                CommandQueue.device_id == device_id
            )
        )
        cmd = result.scalars().first()
        
        if not cmd:
            # Log para detecção de ataque
            import logging
            logger = logging.getLogger("security")
            logger.warning(f"⚠️ COMMAND ISOLATION VIOLATION: device_id={device_id} tentou falhar command_id={command_id}")
            return False
        
        cmd.retry_count += 1
        
        if cmd.retry_count >= cmd.max_retries:
            cmd.status = "failed"
            cmd.error_message = f"{error_msg} (max retries exceeded)"
        else:
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

    # ✅ SEGURO: Valida propriedade de device
    async def get_command_status_secure(self, device_id: str, command_id: int) -> Optional[dict]:
        """
        ✅ SEGURO: Retorna status apenas se o comando pertence ao device.
        Previne device A de ver status de comando de device B.
        """
        from backend.models.policy import CommandQueue
        
        result = await self.db.execute(
            select(CommandQueue).where(
                CommandQueue.id == command_id,
                CommandQueue.device_id == device_id
            )
        )
        cmd = result.scalars().first()
        
        if not cmd:
            # Log para detecção de ataque
            import logging
            logger = logging.getLogger("security")
            logger.warning(f"⚠️ COMMAND ISOLATION VIOLATION: device_id={device_id} tentou visualizar comando_id={command_id}")
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

    async def get_commands_audit(
        self,
        device_id: Optional[str] = None,
        status: Optional[str] = None,
        action: Optional[str] = None,
        issued_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """
        Retorna histórico de comandos para auditoria com filtros flexíveis.
        """
        from backend.models.policy import CommandQueue
        query = select(CommandQueue)
        
        if device_id:
            query = query.where(CommandQueue.device_id == device_id)
        if status:
            query = query.where(CommandQueue.status == status)
        if action:
            query = query.where(CommandQueue.command == action)
        if issued_by:
            query = query.where(CommandQueue.issued_by == issued_by)
            
        query = query.order_by(CommandQueue.created_at.desc()).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        cmds = result.scalars().all()
        
        return [
            {
                "id": c.id,
                "device_id": c.device_id,
                "command": c.command,
                "status": c.status,
                "error_code": c.error_code,
                "error_message": c.error_message,
                "issued_by": c.issued_by,
                "created_at": c.created_at,
                "sent_at": c.sent_at,
                "acked_at": c.acked_at,
                "completed_at": c.completed_at,
                "attempts": c.attempts,
            }
            for c in cmds
        ]
