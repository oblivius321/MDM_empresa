from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.schemas.user import (
    UserLogin, UserCreate, Token, UserResponse,
    ForgotPasswordRequest, ForgotPasswordResponse,
    VerifySecurityAnswerRequest, VerifySecurityAnswerResponse,
    ResetPasswordRequest, ResetPasswordResponse,
    PasswordResetToken
)
from backend.models.user import User
from backend.repositories.user_repo import UserRepository
from backend.core.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, decode_token
from backend.core.constants import SecurityQuestion
from datetime import timedelta, datetime
from fastapi.security import OAuth2PasswordBearer
import os
from backend.core.limiter import limiter

# ── DEFINIÇÃO DO ROUTER (SEM PREFIXO LOCAL) ────────────
router = APIRouter(tags=["Autenticação"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Middleware-like function for auth
async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        token = request.cookies.get("access_token")
            
    if not token:
        raise credentials_exception
    
    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    email: str = payload.get("sub")
    token_type = payload.get("type", "access")
    
    if token_type != "access" or email is None:
        raise credentials_exception
    
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )
    
    return user

# ── ENDPOINTS ───────────────────────────────────────────

@router.get("/security-questions")
async def get_security_questions():
    """Retorna a lista de perguntas de segurança disponíveis."""
    return [
        {"id": q.name, "label": q.value}
        for q in SecurityQuestion
    ]

@router.post("/login", response_model=Token)
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
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo. Contate o administrador.",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "is_admin": user.is_admin, "type": "access"},
        expires_delta=access_token_expires
    )
    
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(response: Response):
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(key="access_token", httponly=True, secure=is_production, samesite="lax")
    return {"message": "Sessão encerrada com sucesso."}

@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
async def register(request: Request, new_user: UserCreate, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    admin_user = await repo.get_by_email(new_user.admin_email)
    if not admin_user or not admin_user.is_admin or not verify_password(new_user.admin_password, admin_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Somente administradores válidos podem autorizar.")

    existing_user = await repo.get_by_email(new_user.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este email corporativo já possui acesso.")
    
    hashed_password = get_password_hash(new_user.password)
    hashed_answer = get_password_hash(new_user.security_answer.lower().strip())
    
    db_user = User(
        email=new_user.email,
        hashed_password=hashed_password,
        security_question=new_user.security_question.name,
        security_answer_hash=hashed_answer,
        is_admin=False
    )
    
    return await repo.create(db_user)

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/forgot-password", response_model=dict)
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_email(data.email)
    
    if not user or not user.security_question:
        import asyncio
        await asyncio.sleep(0.5)
        return {"message": "Iniciando processo de recuperação", "success": False}
    
    token_expires = timedelta(minutes=30)
    recovery_token = create_access_token(
        data={"sub": user.email, "type": "password_recover_step1"},
        expires_delta=token_expires
    )
    
    return {
        "message": "Pergunta carregada com sucesso",
        "email": user.email,
        "security_question": SecurityQuestion[user.security_question].value,
        "recovery_token": recovery_token,
        "expires_in_minutes": 30,
        "success": True
    }

@router.post("/verify-security-answer", response_model=VerifySecurityAnswerResponse)
@limiter.limit("3/minute")
async def verify_security_answer(request: Request, data: VerifySecurityAnswerRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.recovery_token)
    if not payload or payload.get("type") != "password_recover_step1":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")
    
    email = payload.get("sub")
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    
    if not user or not verify_password(data.security_answer.lower().strip(), user.security_answer_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Resposta incorreta")
    
    reset_token = create_access_token(
        data={"sub": user.email, "type": "password_reset_authorized"},
        expires_delta=timedelta(minutes=15)
    )
    
    return {"message": "Resposta correta", "reset_token": reset_token, "expires_in_minutes": 15}

@router.post("/reset-password", response_model=ResetPasswordResponse)
@limiter.limit("3/minute")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.reset_token)
    if not payload or payload.get("type") != "password_reset_authorized":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="As senhas não coincidem")
    
    repo = UserRepository(db)
    user = await repo.get_by_email(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    
    user.hashed_password = get_password_hash(data.new_password)
    await repo.update(user)
    
    return {"message": "Senha atualizada com sucesso", "email": user.email, "status": "password_reset_success"}
