import uuid
import hashlib
import json
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict
from backend.core import utcnow, CommandStatus
from backend.models.device import Device
from backend.models.policy import ProvisioningProfile, DevicePolicy, DeviceCommand
from backend.models.audit_log import AuditLog
from backend.models.telemetry import DeviceTelemetry

logger = logging.getLogger("mdm.repo")

class DeviceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Device Operations ─────────────────────────────────────────────────────

    async def add(self, device: Device) -> Device:
        """Adiciona um novo registro de dispositivo."""
        try:
            self.db.add(device)
            await self.db.commit()
            await self.db.refresh(device)
            return device
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erro ao adicionar dispositivo: {e}")
            raise e

    async def get(self, device_id: str) -> Optional[Device]:
        """Busca dispositivo com sua política ativa e comandos vinculados."""
        result = await self.db.execute(
            select(Device)
            .options(
                selectinload(Device.device_policy),
                selectinload(Device.commands)
            )
            .where(Device.device_id == device_id)
        )
        return result.scalars().first()

    async def list(self) -> List[Device]:
        """Lista todos os dispositivos com política rasa."""
        result = await self.db.execute(
            select(Device).options(selectinload(Device.device_policy))
        )
        return result.scalars().all()

    async def update_device(self, device_id: str, updates: Dict) -> Optional[Device]:
        """Atualiza campos do dispositivo."""
        device = await self.get(device_id)
        if not device:
            return None
        
        for key, value in updates.items():
            if hasattr(device, key) and value is not None:
                setattr(device, key, value)
        
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def remove(self, device_id: str) -> bool:
        """Remove dispositivo e todos os dados vinculados (Cascade)."""
        device = await self.get(device_id)
        if device:
            await self.db.delete(device)
            await self.db.commit()
            return True
        return False

    # ─── Profile Operations (SaaS Templates) ──────────────────────────────────

    async def get_profile(self, profile_id: uuid.UUID) -> Optional[ProvisioningProfile]:
        """Busca perfil de provisionamento ativo."""
        result = await self.db.execute(
            select(ProvisioningProfile).where(
                ProvisioningProfile.id == profile_id, 
                ProvisioningProfile.is_active == True
            )
        )
        return result.scalars().first()

    async def create_profile(self, profile: ProvisioningProfile) -> ProvisioningProfile:
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def list_profiles(self) -> List[ProvisioningProfile]:
        result = await self.db.execute(
            select(ProvisioningProfile).where(ProvisioningProfile.is_active == True)
        )
        return result.scalars().all()

    # ─── Policy Operations (Materialized State) ──────────────────────────────

    def generate_policy_hash(self, config: dict, apps: list) -> str:
        """Gera um hash determinístico para detecção de drift de configuração."""
        content = json.dumps({"c": config, "a": apps}, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_device_policy(self, device_id: str) -> Optional[DevicePolicy]:
        result = await self.db.execute(
            select(DevicePolicy).where(DevicePolicy.device_id == device_id)
        )
        return result.scalars().first()

    # ─── Command Operations (Idempotent Queue) ───────────────────────────────

    async def transition_status(self, command: DeviceCommand, new_status: str, metadata: dict = None):
        """
        Realiza a transição de status de forma segura e auditável.
        Segue o pipeline: PENDING -> DISPATCHED -> EXECUTED -> ACKED
        """
        old_status = command.status
        if old_status == new_status:
            return

        valid_transitions = {
            CommandStatus.PENDING: [CommandStatus.DISPATCHED, CommandStatus.FAILED],
            CommandStatus.DISPATCHED: [CommandStatus.EXECUTED, CommandStatus.FAILED],
            CommandStatus.EXECUTED: [CommandStatus.ACKED, CommandStatus.FAILED],
        }

        # Permitimos transição para FAILED de qualquer estado não terminal
        if new_status != CommandStatus.FAILED and new_status not in valid_transitions.get(old_status, []):
            logger.warning(f"⚠️ Transição inválida negada: {old_status} -> {new_status} (cmd_id={command.id})")
            raise ValueError(f"Transição de status inválida: {old_status} -> {new_status}")

        command.status = new_status
        
        # Timestamps automáticos
        now = utcnow()
        if new_status == CommandStatus.DISPATCHED:
            command.sent_at = now
        elif new_status == CommandStatus.EXECUTED:
            command.executed_at = now
        elif new_status == CommandStatus.ACKED:
            command.acked_at = now
        elif new_status == CommandStatus.FAILED or new_status == CommandStatus.ACKED:
            command.completed_at = now

        # Persistência atômica do estado antes da auditoria
        self.db.add(command)
        await self.db.flush()

        # Auditoria Enterprise
        severity = "INFO" if new_status != CommandStatus.FAILED else "WARNING"
        await self.log_event(
            event_type="COMMAND_STATUS_CHANGED",
            actor_type="system",
            actor_id="command_engine",
            severity=severity,
            device_id=command.device_id,
            payload={
                "command_id": str(command.id),
                "action": command.command_type,
                "from": old_status,
                "to": new_status,
                "attempts": getattr(command, 'attempts', 0),
                "metadata": metadata or {}
            }
        )

    async def add_command(self, device_id: str, command_type: str, payload: dict = None, dedupe_key: str = None) -> DeviceCommand:
        """
        Adiciona comando à fila com tratamento de duplicidade via IntegrityError.
        """
        if not dedupe_key:
            # Canonical Hash para deduplicação
            payload_json = json.dumps(payload or {}, sort_keys=True, separators=(',', ':'))
            raw = f"{device_id}:{command_type}:{payload_json}"
            dedupe_key = hashlib.sha256(raw.encode()).hexdigest()[:32]
        
        cmd = DeviceCommand(
            device_id=device_id,
            command_type=command_type,
            payload=payload or {},
            status=CommandStatus.PENDING,
            dedupe_key=dedupe_key
        )
        
        try:
            self.db.add(cmd)
            await self.db.commit()
            await self.db.refresh(cmd)
            return cmd
        except IntegrityError as e:
            await self.db.rollback()
            if "dedupe" in str(e).lower() or "unique" in str(e).lower():
                # Retorna o comando existente em caso de duplicata
                result = await self.db.execute(
                    select(DeviceCommand).where(DeviceCommand.dedupe_key == dedupe_key)
                )
                return result.scalars().first()
            raise e

    async def get_pending_commands(self, device_id: str) -> List[DeviceCommand]:
        """Busca comandos PENDING para entrega imediata."""
        result = await self.db.execute(
            select(DeviceCommand)
            .where(
                DeviceCommand.device_id == device_id, 
                DeviceCommand.status == CommandStatus.PENDING
            )
            .order_by(DeviceCommand.created_at.asc())
        )
        return result.scalars().all()

    async def update_command_status(self, device_id: str, command_id: uuid.UUID, status: str, metadata: dict = None) -> bool:
        """Wrapper seguro para transição de status."""
        result = await self.db.execute(
            select(DeviceCommand).where(
                DeviceCommand.id == command_id,
                DeviceCommand.device_id == device_id
            )
        )
        cmd = result.scalars().first()
        if not cmd:
            return False
            
        try:
            await self.transition_status(cmd, status, metadata=metadata)
            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao transicionar comando {command_id}: {e}")
            await self.db.rollback()
            return False

    async def update_device_command_status(self, command_id: uuid.UUID, status: str, sent_at: datetime = None) -> bool:
        """Alias de compatibilidade com transição segura."""
        result = await self.db.execute(
            select(DeviceCommand).where(DeviceCommand.id == command_id)
        )
        cmd = result.scalars().first()
        if not cmd:
            return False
        
        try:
            await self.transition_status(cmd, status)
            if sent_at:
                cmd.sent_at = sent_at
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            return False

    async def complete_command_secure(self, device_id: str, command_id: uuid.UUID) -> bool:
        """Marca comando como completo/sucesso de forma segura."""
        return await self.update_command_status(device_id, command_id, "completed")

    async def fail_command_secure(self, device_id: str, command_id: uuid.UUID, error_msg: str) -> bool:
        """Marca comando como falha com mensagem de erro."""
        result = await self.db.execute(
            select(DeviceCommand).where(
                DeviceCommand.id == command_id,
                DeviceCommand.device_id == device_id
            )
        )
        cmd = result.scalars().first()
        if not cmd:
            return False
            
        cmd.status = "failed"
        cmd.error_message = error_msg
        cmd.completed_at = datetime.utcnow()
        
        await self.db.commit()
        return True

    # ─── Audit Log Centralized ───────────────────────────────────────────────

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

    async def log_event(self, event_type: str, actor_id: str, actor_type: str = "system", severity: str = "INFO", device_id: uuid.UUID = None, payload: dict = None, request = None, user_id: int = None):
        """Helper para registrar auditoria com contexto HTTP opcional."""
        from backend.models.audit_log import AuditLog, AuditActionEnum
        
        # Mapeamento de compatibilidade para o Enum de Auditoria
        action_mapping = {
            "ENROLLMENT_TOKEN_GENERATED": AuditActionEnum.ENROLLMENT_GENERATE,
            "DEVICE_ENROLLED": AuditActionEnum.ENROLLMENT_COMPLETE,
            "COMMAND_CREATED": AuditActionEnum.COMMAND_CREATE,
            "COMMAND_ACKED": AuditActionEnum.COMMAND_UPDATE,
            "COMMAND_EXECUTED": AuditActionEnum.COMMAND_UPDATE,
            "COMMAND_FAILED": AuditActionEnum.COMMAND_UPDATE,
            "COMMAND_VERIFIED": AuditActionEnum.COMMAND_UPDATE,
            "COMMAND_VERIFICATION_FAILED": AuditActionEnum.COMMAND_UPDATE,
            "COMPLIANCE_REPORT": AuditActionEnum.COMPLIANCE_CHECK,
            "DEVICE_WIPE": AuditActionEnum.DEVICE_WIPE,
            "DEVICE_LOCK": AuditActionEnum.DEVICE_LOCK,
        }
        
        # Tenta mapear ou usa um fallback seguro
        action = action_mapping.get(event_type, AuditActionEnum.COMMAND_UPDATE)
        
        log = AuditLog(
            action=action,
            event_type=event_type,
            resource_type="device" if device_id else "system",
            severity=severity,
            actor_type=actor_type,
            actor_id=actor_id,
            device_id=device_id,
            details=payload or {},
            user_id=user_id
        )
        
        if request:
            log.ip_address = request.client.host
            log.user_agent = request.headers.get("user-agent")
            log.request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        
        self.db.add(log)
        await self.db.commit()
        return log

    async def get_device_telemetry(self, device_id: str, limit: int = 50) -> List[DeviceTelemetry]:
        """Obtém os relatórios de telemetria mais recentes do dispositivo."""
        result = await self.db.execute(
            select(DeviceTelemetry)
            .where(DeviceTelemetry.device_id == device_id)
            .order_by(DeviceTelemetry.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()
