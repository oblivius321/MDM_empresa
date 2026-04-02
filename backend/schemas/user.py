from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
from backend.core.constants import SecurityQuestion

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    security_question: SecurityQuestion
    security_answer: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str

class UserResponse(BaseModel):
    """Resposta básica de usuário (sem roles)"""
    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleSimplified(BaseModel):
    """Role simplificada para responses de usuário"""
    id: int
    name: str
    role_type: str  # Enum string


class UserResponseWithRoles(UserResponse):
    """Resposta de usuário com seus roles e permissões"""
    roles: List[RoleSimplified] = []
    permissions: List[str] = []  # Lista de nomes de permissões
    
    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    """Schema para atualizar um usuário (admin only)"""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

class Token(BaseModel):
    access_token: str
    token_type: str

# ============= Fluxo de Recuperação de Senha (SEGURO) =============

class ForgotPasswordRequest(BaseModel):
    """Tela 1: Usuário insere email para iniciar fluxo de recuperação"""
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    """Resposta do backend: confirmação e pergunta de segurança"""
    message: str
    email: EmailStr
    security_question: str  # Retorna o label amigável ao usuário
    recovery_token: str  # Token com type="password_recover_step1"
    expires_in_minutes: int = 30

class VerifySecurityAnswerRequest(BaseModel):
    """Tela 2: Usuário responde a pergunta de segurança"""
    recovery_token: str  # Token da etapa anterior (step1)
    security_answer: str

class VerifySecurityAnswerResponse(BaseModel):
    """Resposta da backend: autorização para reset (nova etapa)"""
    message: str
    reset_token: str  # Token com type="password_reset_authorized" e novo JTI
    expires_in_minutes: int = 15

class ResetPasswordRequest(BaseModel):
    """Tela 3: Usuário define nova senha com token de autorização"""
    reset_token: str  # Token da etapa anterior (step2)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

class ResetPasswordResponse(BaseModel):
    """Resposta do backend: senha atualizada com sucesso"""
    message: str
    email: EmailStr
    status: str = "password_reset_success"

class PasswordResetToken(BaseModel):
    """Token temporário para validar fluxo de reset"""
    token: str

# ============= Enroll Seguro (com Bootstrap Secret) =============

class DeviceEnrollRequest(BaseModel):
    """Request para enroll seguro de dispositivo"""
    device_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    device_type: str = Field(..., min_length=1, max_length=50)
    bootstrap_secret: str  # Secret compartilhado para validar enroll
    extra_data: Optional[dict] = None

class DeviceEnrollResponse(BaseModel):
    """Resposta do backend: dispositivo enrolled com token"""
    message: str
    device_id: str
    device_token: str  # Token para comunicação futura do device
    api_url: str
    enrollment_status: str = "success"

