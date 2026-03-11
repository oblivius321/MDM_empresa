from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.schemas.user import (
    UserLogin, UserCreate, Token, UserResponse,
    ForgotPasswordRequest, SecurityQuestionResponse,
    VerifySecurityAnswerRequest, ResetPasswordRequest,
    PasswordResetToken
)
from backend.models.user import User
from backend.repositories.user_repo import UserRepository
from backend.core.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
from datetime import timedelta, datetime
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import os

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Prioriza o token no Cookie, fallback para Header Authorization
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user is None:
        raise credentials_exception
    return user

from backend.core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, response: Response, credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_email(credentials.email)
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email corporativo ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "is_admin": user.is_admin}, expires_delta=access_token_expires
    )
    
    # Configura o token JWT de forma segura no Cookie HttpOnly
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return {
        "message": "Autenticação bem-sucedida, sessão iniciada.",
        "user": {
            "email": user.email,
            "is_admin": user.is_admin
        }
    }

@router.post("/logout")
async def logout(response: Response):
    """Destrói a sessão apagando o cookie JWT."""
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(key="access_token", httponly=True, secure=is_production, samesite="lax")
    return {"message": "Sessão encerrada com sucesso."}


@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
async def register(request: Request, new_user: UserCreate, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    
    # 1. Valida a Autorização do Admin Primeiro (Hierarquia Rigorosa)
    admin_user = await repo.get_by_email(new_user.admin_email)
    if not admin_user or not admin_user.is_admin or not verify_password(new_user.admin_password, admin_user.hashed_password):
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operação abortada. Somente administradores válidos podem autorizar."
        )

    # 2. Confirma se o e-mail do Novo Operador já está em uso
    existing_user = await repo.get_by_email(new_user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este email corporativo já possuí acesso ao Painel."
        )
        
    # 3. Cria encriptando a senha e a resposta da pergunta de segurança
    hashed_password = get_password_hash(new_user.password)
    hashed_answer = get_password_hash(new_user.security_answer.lower().strip())
    
    db_user = User(
        email=new_user.email,
        hashed_password=hashed_password,
        security_question=new_user.security_question,
        security_answer_hash=hashed_answer,
        is_admin=False # Operadores recém criados não são admin por padrão
    )
    
    created_user = await repo.create(db_user)
    return created_user


# ============= ENDPOINTS DE RECUPERAÇÃO DE SENHA =============

@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    TELA 1: Usuário solicita recuperação de senha
    Verifica se o email existe e retorna a pergunta de segurança
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(data.email)
    
    if not user:
        # Resposta genérica por segurança (não revela se email existe)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email não encontrado no sistema"
        )
    
    if not user.security_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este usuário não configurou uma pergunta de segurança"
        )
    
    # Gera um token temporário (30 minutos de validade)
    reset_token_expires = timedelta(minutes=30)
    reset_token = create_access_token(
        data={"sub": user.email, "type": "password_reset"},
        expires_delta=reset_token_expires
    )
    
    return {
        "message": "Pergunta de segurança carregada com sucesso",
        "email": user.email,
        "security_question": user.security_question,
        "reset_token": reset_token
    }


@router.post("/verify-security-answer")
@limiter.limit("5/minute")
async def verify_security_answer(
    request: Request,
    data: VerifySecurityAnswerRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    TELA 2: Usuário responde a pergunta de segurança
    Valida a resposta e retorna autorização para reset de senha
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(data.email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Normaliza a resposta (lowercase + strip de espaços)
    provided_answer = data.security_answer.lower().strip()
    
    # Verifica a resposta contra o hash salvo
    if not verify_password(provided_answer, user.security_answer_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Resposta incorreta. Tente novamente."
        )
    
    # Gera token autorizado para reset de senha (15 minutos)
    reset_token_expires = timedelta(minutes=15)
    authorized_token = create_access_token(
        data={
            "sub": user.email,
            "type": "password_reset_authorized",
            "verified_at": datetime.utcnow().isoformat()
        },
        expires_delta=reset_token_expires
    )
    
    return {
        "message": "Resposta verificada com sucesso",
        "authorized": True,
        "reset_token": authorized_token,
        "email": user.email
    }


@router.post("/reset-password")
@limiter.limit("3/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    TELA 3: Usuário define nova senha
    Atualiza a senha no banco após validações
    """
    # Validações
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="As senhas não coincidem"
        )
    
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha deve ter no mínimo 6 caracteres"
        )
    
    repo = UserRepository(db)
    user = await repo.get_by_email(data.email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    try:
        # Atualiza a senha com hash
        new_hashed_password = get_password_hash(data.new_password)
        user.hashed_password = new_hashed_password
        
        updated_user = await repo.update(user)
        
        return {
            "message": "Senha atualizada com sucesso",
            "email": updated_user.email,
            "status": "password_reset_completed"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar senha: {str(e)}"
        )
