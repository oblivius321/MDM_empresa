from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict
from datetime import datetime
from backend.schemas.policy import DevicePolicyResponse, DeviceCommandResponse


class DeviceBase(BaseModel):
    name: str 
    device_type: str
    is_active: bool = True
    status: str = "offline"
    imei: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    company: Optional[str] = None
    last_apps_json: Optional[List[str]] = None
    
    # Telemetria em tempo real (Cacheada na tabela Device)
    battery_level: Optional[int] = None
    free_disk_space_mb: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class DeviceCreate(DeviceBase):
    device_id: str


class DeviceUpdate(BaseModel):
    """Campos permitidos para atualização via API de checkin ou painel."""
    name: Optional[str] = None
    status: Optional[str] = None
    imei: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    last_checkin: Optional[datetime] = None
    metadata_json: Optional[Dict] = None


class DeviceResponse(DeviceBase):
    """Resposta padrão de dispositivo para listagem e dashboard."""
    id: str = Field(..., alias="device_id")
    device_id: str
    external_id: Optional[str] = None
    enrollment_date: datetime
    last_checkin: Optional[datetime] = None
    
    # Vínculo com a política materializada (SaaS Architecture)
    device_policy: Optional[DevicePolicyResponse] = None
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DeviceSummaryResponse(BaseModel):
    total: int = 0
    online: int = 0
    offline: int = 0
    locked: int = 0
    last_global_checkin: Optional[datetime] = None


class DeviceFullResponse(DeviceResponse):
    """Resposta detalhada incluindo fila de comandos (Admin/Debug)."""
    commands: List[DeviceCommandResponse] = []
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EnrollmentResponse(BaseModel):
    """Resposta do handshake inicial de enrollment — Foco em Identidade."""
    message: str
    device_id: str
    device_token: str
    api_url: str
    enrollment_status: str = "success"
    # O device deve chamar /bootstrap logo após receber este OK

# ============= 🛡️ CAMADA EX: TRUST & ATTESTATION (Fase 4) =============

class NonceResponse(BaseModel):
    nonce: str
    expires_in: int = 300

class AttestationRequest(BaseModel):
    integrity_token: str
    nonce: str
