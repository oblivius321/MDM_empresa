"""
Schemas Pydantic para Audit Logs (validação e serialização).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from backend.models.audit_log import AuditActionEnum


class AuditLogCreate(BaseModel):
    """Schema para criar um log de auditoria (uso interno)"""
    user_id: Optional[int] = None
    action: AuditActionEnum
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: Optional[str] = Field(None, max_length=255)
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_success: bool = True
    error_message: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Schema para resposta de um log de auditoria"""
    id: int
    user_id: Optional[int] = None
    action: AuditActionEnum
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    is_success: bool
    error_message: Optional[str] = None
    created_at: datetime
    
    # Usuario que fez a ação (preenchido se necessário)
    user_email: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogDetailedResponse(AuditLogResponse):
    """Resposta detalhada de auditoria (para admin)"""
    user_agent: Optional[str] = None


class AuditLogListResponse(BaseModel):
    """Resposta com lista de logs"""
    total: int
    page: int
    page_size: int
    logs: List[AuditLogResponse]


class AuditLogFilterRequest(BaseModel):
    """Schema para filtrar logs de auditoria"""
    user_id: Optional[int] = None
    action: Optional[AuditActionEnum] = None
    resource_type: Optional[str] = None
    is_success: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)
