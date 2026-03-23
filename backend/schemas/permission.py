"""
Schemas Pydantic para Permissions (validação e serialização).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class PermissionCreate(BaseModel):
    """Schema para criar uma permissão (só admin)"""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    resource: str = Field(..., min_length=2, max_length=50)
    action: str = Field(..., min_length=2, max_length=50)
    is_critical: bool = False
    requires_mfa: bool = False


class PermissionUpdate(BaseModel):
    """Schema para atualizar uma permissão"""
    description: Optional[str] = Field(None, max_length=500)
    is_critical: Optional[bool] = None
    requires_mfa: Optional[bool] = None
    is_active: Optional[bool] = None


class PermissionResponse(BaseModel):
    """Schema para resposta de uma permissão (leitura)"""
    id: int
    name: str
    description: Optional[str] = None
    resource: str
    action: str
    is_critical: bool
    requires_mfa: bool
    is_system_permission: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
    @property
    def full_name(self) -> str:
        """Nome completo da permissão"""
        return f"{self.resource}:{self.action}"


class PermissionListResponse(BaseModel):
    """Resposta com lista de permissões"""
    total: int
    permissions: List[PermissionResponse]
