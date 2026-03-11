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

# ============= Fluxo de Recuperação de Senha =============

class ForgotPasswordRequest(BaseModel):
    """Tela 1: Usuário insere email para iniciar fluxo de recuperação"""
    email: EmailStr

class SecurityQuestionResponse(BaseModel):
    """Resposta do backend: mostra a pergunta de segurança"""
    email: EmailStr
    security_question: str

class VerifySecurityAnswerRequest(BaseModel):
    """Tela 2: Usuário responde a pergunta de segurança"""
    email: EmailStr
    security_answer: str

class ResetPasswordRequest(BaseModel):
    """Tela 3: Usuário define nova senha"""
    email: EmailStr
    new_password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)

class PasswordResetToken(BaseModel):
    """Token temporário para validar fluxo de reset"""
    token: str

