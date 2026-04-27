from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, List, Optional
from datetime import datetime
import uuid

# ═══════════════════════════════════════════════════════════════════════════════
# PROVISIONING PROFILE SCHEMAS (Template mestre)
# ═══════════════════════════════════════════════════════════════════════════════

class ProvisioningProfileBase(BaseModel):
    name: str = Field(..., example="Perfil Coletor Logística")
    kiosk_enabled: bool = True
    allowed_apps: List[str] = Field(default_factory=list, example=["com.elion.app", "com.android.settings"])
    blocked_features: Dict = Field(default_factory=dict, example={"camera": True, "usb_debug": True})
    config: Dict = Field(default_factory=dict, example={"wifi_ssid": "Elion_Corp", "auto_update": True})
    policy_ids: List[int] = Field(default_factory=list, description="Lista de IDs de Políticas Enterprise associadas")


class ProvisioningProfileCreate(ProvisioningProfileBase):
    """Schema para criação de um novo template de provisionamento."""
    pass

class ProvisioningProfileUpdate(BaseModel):
    """Schema para atualização de template (marcará devices vinculados como outdated)."""
    name: Optional[str] = None
    kiosk_enabled: Optional[bool] = None
    allowed_apps: Optional[List[str]] = None
    blocked_features: Optional[Dict] = None
    config: Optional[Dict] = None
    policy_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class ProvisioningProfileResponse(ProvisioningProfileBase):
    """Resposta detalhada do template mestre."""
    id: uuid.UUID
    version: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE POLICY SCHEMAS (Estado materializado por device)
# ═══════════════════════════════════════════════════════════════════════════════

class DevicePolicyBase(BaseModel):
    kiosk_enabled: bool
    allowed_apps: List[str]
    blocked_features: Dict
    config: Dict
    policy_version: int
    policy_hash: str
    policy_outdated: bool

class DevicePolicyResponse(DevicePolicyBase):
    """Representação do estado atual do device no backend."""
    id: uuid.UUID
    device_id: str
    profile_id: uuid.UUID
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PolicySyncHandshake(BaseModel):
    """Payload de handshake enviado pelo agente Android para checar drift."""
    current_hash: str
    current_version: int


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE COMMAND SCHEMAS (Fila de ações remota)
# ═══════════════════════════════════════════════════════════════════════════════

class DeviceCommandCreate(BaseModel):
    """Schema para disparar um comando via dashboard."""
    command_type: str # INSTALL_APP, LOCK, REBOOT, EXIT_KIOSK, WIPE
    payload: Optional[Dict] = None

class DeviceCommandResponse(BaseModel):
    """Status detalhado de um comando na fila."""
    id: int
    device_id: str
    command_type: str
    payload: Optional[Dict] = None
    status: str # PENDING, DISPATCHED, EXECUTED, FAILED, ACKED
    dedupe_key: str
    created_at: datetime
    dispatched_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    execution_latency: Optional[float] = None  # seconds between dispatch and execution
    acked_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    operation_id: Optional[str] = None  # Google AMAPI operation resource name

    model_config = ConfigDict(from_attributes=True)

class CommandStatusUpdate(BaseModel):
    """Payload enviado pelo device para atualizar progresso do comando."""
    status: str # EXECUTED, FAILED
    error_message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# ENTERPRISE POLICY SCHEMAS (Fase 3)
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    config: Dict
    priority: int = 0
    scope: str = "global"


class PolicyConfigUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict] = None
    priority: Optional[int] = None
    scope: Optional[str] = None
    is_active: Optional[bool] = None

class PolicyConfigResponse(BaseModel):
    id: int
    name: str
    config: Dict
    priority: int
    scope: str
    version: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class DevicePolicyAssign(BaseModel):
    policy_id: int


class DevicePolicyAssignmentResponse(BaseModel):
    id: int
    device_id: str
    policy_id: int
    issued_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ComplianceStatusResponse(BaseModel):
    device_id: str
    status: str
    compliant: bool
    blocked: bool = False
    effective_hash: Optional[str] = None
    subcommands_dispatched: Optional[int] = None
    drift_summary: Optional[Dict] = None

class DeviceStateReport(BaseModel):
    state_hash: str
    kiosk_enabled: Optional[bool] = None
    allowed_apps: Optional[List[str]] = None
    blocked_features: Optional[Dict] = None
    config: Optional[Dict] = None

# ═══════════════════════════════════════════════════════════════════════════════
# ENTERPRISE COMPLIANCE SCHEMAS (Fase 3B)
# ═══════════════════════════════════════════════════════════════════════════════
from enum import Enum

class DeviceHealth(str, Enum):
    COMPLIANT = "COMPLIANT"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"

class DeviceStatusReport(BaseModel):
    """Report detalhado de saúde e conformidade para auditoria real."""
    health: DeviceHealth
    reason_code: Optional[str] = Field(None, example="APP_INSTALL_FAILED")
    policy_hash: str
    last_applied_hash: Optional[str] = None
    applied_policies: List[str] = Field(default_factory=list)
    failed_policies: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class BootstrapResponse(BaseModel):
    """JSON mestre de provisionamento (Source of Truth)."""
    device_id: str
    policy_version: int
    policy_hash: str
    config: Dict
    kiosk_enabled: bool
    allowed_apps: List[str]
    blocked_features: Dict
    pending_commands: List[DeviceCommandResponse] = []
    
    model_config = ConfigDict(from_attributes=True)
