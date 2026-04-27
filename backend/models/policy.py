from sqlalchemy import String, Integer, JSON, Boolean, DateTime, ForeignKey, Index, Uuid, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
import uuid
from typing import TYPE_CHECKING, List, Optional
from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.device import Device


class ProvisioningProfile(Base):
    """
    Template mestre de provisionamento usado no QR Code.
    Define as configurações iniciais de um grupo de dispositivos.
    """
    __tablename__ = "provisioning_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, index=True)
    
    # Config inicial (Fallback)
    kiosk_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_apps: Mapped[dict] = mapped_column(JSON, default=list) # ["pkg1", "pkg2"]
    blocked_features: Mapped[dict] = mapped_column(JSON, default=dict)
    
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Versionamento e Soft Delete
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True) 

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    devices: Mapped[List["DevicePolicy"]] = relationship("DevicePolicy", back_populates="profile")
    policies: Mapped[List["ProvisioningProfilePolicy"]] = relationship(
        "ProvisioningProfilePolicy", back_populates="profile", cascade="all, delete-orphan"
    )

    @property
    def policy_ids(self) -> List[int]:
        return [
            assoc.policy_id
            for assoc in sorted(self.policies, key=lambda assoc: assoc.priority)
        ]

    def __repr__(self):
        return f"<ProvisioningProfile(name='{self.name}', v={self.version})>"


class ProvisioningProfilePolicy(Base):
    """
    Tabela de junção M:N entre Profiles e Policies Enterprise.
    Suporta priorização explícita (Maior número = Maior prioridade).
    """
    __tablename__ = "provisioning_profile_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("provisioning_profiles.id"), index=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policies_v2.id"), index=True)
    
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    profile: Mapped["ProvisioningProfile"] = relationship("ProvisioningProfile", back_populates="policies")
    policy: Mapped["Policy"] = relationship("Policy")



class DevicePolicy(Base):
    """
    Estado materializado real de um dispositivo específico.
    Derivado de um ProvisioningProfile, mas versionado independentemente.
    """
    __tablename__ = "device_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"), unique=True, index=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("provisioning_profiles.id"))

    # Estado atual aplicado (Materializado no DB para sync rápido)
    kiosk_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_apps: Mapped[dict] = mapped_column(JSON, default=list)
    blocked_features: Mapped[dict] = mapped_column(JSON, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Versionamento e Drift Control
    policy_version: Mapped[int] = mapped_column(Integer, default=1)
    policy_hash: Mapped[str] = mapped_column(String, index=True) # Hash SHA256 do config/apps
    policy_outdated: Mapped[bool] = mapped_column(Boolean, default=False) # Marcado como true se o Profile mudar

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    profile: Mapped["ProvisioningProfile"] = relationship("ProvisioningProfile", back_populates="devices")
    device: Mapped["Device"] = relationship("Device", back_populates="device_policy")

    def __repr__(self):
        return f"<DevicePolicy(device={self.device_id}, v={self.policy_version}, outdated={self.policy_outdated})>"


from backend.core import utcnow, CommandStatus

class DeviceCommand(Base):
    """
    Fila de comandos idempotentes para disparar ações no agente Android.
    
    Unificado sob a tabela 'command_queue' como única fonte de verdade.
    """
    __tablename__ = "command_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"), index=True)

    # Tipos: INSTALL_APP, LOCK, REBOOT, EXIT_KIOSK, WIPE, UNLOCK
    command: Mapped[str] = mapped_column(String, nullable=False)
    
    @hybrid_property
    def command_type(self):
        return self.command
    
    @command_type.setter
    def command_type(self, value):
        self.command = value

    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)

    # Status: PENDING, DISPATCHED, EXECUTED, ACKED, FAILED
    status: Mapped[str] = mapped_column(String, default=CommandStatus.PENDING, index=True)
    
    # Idempotência: impede re-execução do mesmo comando
    dedupe_key: Mapped[str] = mapped_column(String, unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    @hybrid_property
    def dispatched_at(self):
        return self.sent_at
    
    @dispatched_at.setter
    def dispatched_at(self, value):
        self.sent_at = value
    
    acked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Controle de Retries e Erros (Enterprise)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AMAPI Operation Tracking (Google long-running operation)
    operation_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    @property
    def execution_latency(self) -> Optional[float]:
        """Returns the latency in seconds between dispatch and execution."""
        if self.executed_at and self.sent_at:
            return (self.executed_at - self.sent_at).total_seconds()
        return None

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="commands")

    def __repr__(self):
        return f"<DeviceCommand(id={self.id}, action={self.command}, status={self.status}, device={self.device_id})>"

# Alias de compatibilidade para sistemas que esperam 'CommandQueue'
CommandQueue = DeviceCommand


# ═══════════════════════════════════════════════════════════════════════════════
# ENTERPRISE POLICY MODELS (Fase 3)
# ═══════════════════════════════════════════════════════════════════════════════

class Policy(Base):
    """
    Nova arquitetura de Policy Enterprise.
    Suporta N policies por device com merge priorizado por scope.
    """
    __tablename__ = "policies_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[dict] = mapped_column(JSON, default=list) # ["security", "apps"]
    
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    scope: Mapped[str] = mapped_column(String(50), default="global", index=True) # global, group, device
    
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)


class PolicyState(Base):
    """
    Controlador de Drift e Compliance por device.
    Cache do último estado reportado e status de enforcement.
    """
    __tablename__ = "policy_states"

    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"), primary_key=True, index=True)
    
    last_compliance_status: Mapped[str] = mapped_column(String(50), default="unknown") # compliant, non_compliant, enforcing, failed_loop
    last_reported_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    state_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    effective_policy_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    last_enforced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    enforcement_count: Mapped[int] = mapped_column(Integer, default=0)
    drift_score: Mapped[int] = mapped_column(Integer, default=0)
    failed_subcommands: Mapped[list] = mapped_column(JSON, default=list) # Lista de actions que falharam

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DevicePolicyAssignment(Base):
    """
    Rastreia atribuicoes diretas de policies enterprise a dispositivos.
    """
    __tablename__ = "device_policy_assignments"
    __table_args__ = (
        UniqueConstraint("device_id", "policy_id", name="uq_device_policy_assignments_device_policy"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"), index=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policies_v2.id"), index=True)
    issued_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    device: Mapped["Device"] = relationship("Device")
    policy: Mapped["Policy"] = relationship("Policy")

    def __repr__(self):
        return (
            f"<DevicePolicyAssignment(device={self.device_id}, policy={self.policy_id}, "
            f"issued_by={self.issued_by})>"
        )
