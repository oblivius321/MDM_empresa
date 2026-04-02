"""
Pydantic schemas para Policy CRUD e Compliance (Fase 3).
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, List, Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyConfigCreate(BaseModel):
    """Schema para criação de policy enterprise (JSON config)."""
    name: str = "Default Policy"
    config: Dict = {}
    priority: int = 0
    scope: str = "global"  # global | group | device


class PolicyConfigUpdate(BaseModel):
    """Schema para atualização de policy (incrementa version automaticamente)."""
    name: Optional[str] = None
    config: Optional[Dict] = None
    priority: Optional[int] = None
    scope: Optional[str] = None
    is_active: Optional[bool] = None


class PolicyConfigResponse(BaseModel):
    """Schema de resposta de policy enterprise."""
    id: int
    name: str
    config: Dict = {}
    priority: int
    scope: str
    version: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('id', mode='before')
    def ensure_int(cls, v):
        return int(v) if v else v

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE POLICY ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

class DevicePolicyAssign(BaseModel):
    """Schema para atribuir uma policy a um device."""
    policy_id: int


class DevicePolicyResponse(BaseModel):
    """Schema de resposta de vínculo device↔policy."""
    id: int
    device_id: str
    policy_id: int
    issued_by: Optional[str] = None
    assigned_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE / STATE
# ═══════════════════════════════════════════════════════════════════════════════

class ComplianceStatusResponse(BaseModel):
    """Resposta de avaliação de compliance."""
    device_id: str
    status: str
    compliant: bool
    effective_hash: Optional[str] = None
    subcommands_dispatched: Optional[int] = None
    drift_summary: Optional[Dict] = None
    blocked: Optional[bool] = None


class DeviceStateReport(BaseModel):
    """Payload enviado pelo device com seu estado atual."""
    restrictions: Optional[Dict] = None
    kiosk_mode: Optional[str] = None
    allowed_apps: Optional[List[str]] = None
    blocked_apps: Optional[List[str]] = None
    password_requirements: Optional[Dict] = None
    installed_apps: Optional[List[str]] = None
    wifi_config: Optional[Dict] = None
