"""
Schemas Pydantic para Roles (validação e serialização).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from backend.models.role import RoleEnum


class PermissionBase(BaseModel):
    """Permissão básica para responses"""
    id: int
    name: str
    description: Optional[str] = None
    resource: str
    action: str
    is_critical: bool
    
    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    """Schema para criar um novo role"""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    role_type: RoleEnum


class RoleUpdate(BaseModel):
    """Schema para atualizar um role"""
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class RolePermissionAdd(BaseModel):
    """Schema para adicionar uma permissão a um role"""
    permission_id: int


class RolePermissionRemove(BaseModel):
    """Schema para remover uma permissão de um role"""
    permission_id: int


class RoleResponse(BaseModel):
    """Schema para resposta de um role (leitura)"""
    id: int
    name: str
    description: Optional[str] = None
    role_type: RoleEnum
    is_active: bool
    priority: int
    is_system_role: bool
    created_at: datetime
    updated_at: datetime
    permissions: List[PermissionBase] = []
    
    model_config = ConfigDict(from_attributes=True)


class RoleDetailedResponse(RoleResponse):
    """Resposta detalhada incluindo quem criou"""
    created_by_user_id: Optional[int] = None


class UserRoleAssign(BaseModel):
    """Schema para atribuir um role a um usuário"""
    role_id: int


class UserRoleRevoke(BaseModel):
    """Schema para remover um role de um usuário"""
    role_id: int


class UserRoleResponse(BaseModel):
    """Resposta sobre um role de um usuário"""
    role_id: int
    role_name: str
    role_type: RoleEnum
    assigned_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
