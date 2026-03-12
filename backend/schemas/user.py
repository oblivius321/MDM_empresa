from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    security_question: str = Field(..., min_length=5, max_length=255)
    security_answer: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

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
    security_question: str
    recovery_token: str  # Token com type="password_recover_step1" e JTI
    expires_in_minutes: int = 30

class VerifySecurityAnswerRequest(BaseModel):
    """Tela 2: Usuário responde a pergunta de segurança"""
    recovery_token: str  # Token da etapa anterior
    security_answer: str

class VerifySecurityAnswerResponse(BaseModel):
    """Resposta da backend: autorização para reset (nova etapa)"""
    message: str
    reset_token: str  # Token com type="password_reset_authorized" e novo JTI
    expires_in_minutes: int = 15

class ResetPasswordRequest(BaseModel):
    """Tela 3: Usuário define nova senha com token de autorização"""
    reset_token: str  # Token da etapa anterior com type="password_reset_authorized"
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

