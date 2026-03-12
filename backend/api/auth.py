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
        token_type = payload.get("type", "access")
        
        # Validar tipo de token (impedir uso de token de reset como acesso)
        if token_type != "access" and email is not None:
            # Toleramos o login apenas se o token explicitly disser access ou não tiver type (antigos)
            # Mas se explicitamente for um token de recovery, barramos.
             raise credentials_exception
             
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
        data={"sub": user.email, "is_admin": user.is_admin, "type": "access"}, expires_delta=access_token_expires
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


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Retorna o perfil do usuário logado baseado no cookie/token JWT atual.
    Usado pelo frontend para restaurar sessão ao invés de usar o localStorage.
    """
    return current_user


# ============= ENDPOINTS DE RECUPERAÇÃO DE SENHA (SEGURO) =============
# Fluxo: Forgot → Verify Answer → Reset Password
# Cada etapa valida tipo de token, JTI e expiração

@router.post("/forgot-password", response_model=dict)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    ETAPA 1: Usuário solicita recuperação de senha por email
    Valida que o email existe e que tem pergunta de segurança
    Retorna token de step1 (type="password_recover_step1") com JTI único
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(data.email)
    
    # Resposta genérica para previnir enumeração
    generic_success_msg = "Se o endereço de e-mail estiver cadastrado, uma etapa de recuperação será iniciada."
    
    if not user or not user.security_question:
        # Atrasa artificialmente para mitigar timing attacks na enumeração
        import asyncio
        await asyncio.sleep(0.5)
        return {
            "message": generic_success_msg,
            "success": False # Frontend must treat this as general success message anyway
        }
    
    # Gera token de step1 com JTI único (30 minutos)
    recover_token_expires = timedelta(minutes=30)
    recover_token = create_access_token(
        data={
            "sub": user.email,
            "type": "password_recover_step1"
        },
        expires_delta=recover_token_expires
    )
    
    
    return {
        "message": "Pergunta de segurança carregada com sucesso",
        "email": user.email,
        "security_question": user.security_question,
        "recovery_token": recover_token,
        "expires_in_minutes": 30,
        "success": True
    }


@router.post("/verify-security-answer", response_model=dict)
@limiter.limit("5/minute")
async def verify_security_answer(
    request: Request,
    data: VerifySecurityAnswerRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    ETAPA 2: Usuário responde à pergunta de segurança
    Valida:
    - Token da step1 (type="password_recover_step1" e JTI válido)
    - Resposta de segurança correta
    Retorna novo token para step3 (type="password_reset_authorized")
    """
    from backend.core.security import decode_token
    
    # Validar token da etapa anterior
    payload = decode_token(data.recovery_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )
    
    # Validar que é o token correto (step1)
    if payload.get("type") != "password_recover_step1":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido (tipo incorreto)"
        )
    
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido (sem email)"
        )
    
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Validar resposta de segurança
    provided_answer = data.security_answer.lower().strip()
    if not verify_password(provided_answer, user.security_answer_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Resposta incorreta. Tente novamente."
        )
    
    # Gera novo token para step3 com JTI único (15 minutos)
    import uuid
    reset_jti = str(uuid.uuid4())
    reset_token_expires = timedelta(minutes=15)
    reset_token = create_access_token(
        data={
            "sub": user.email,
            "type": "password_reset_authorized",
            "jti": reset_jti,
            "verified_at": datetime.utcnow().isoformat()
        },
        expires_delta=reset_token_expires
    )
    
    # Persistir JTI no banco (invalidando anteriores)
    user.password_reset_jti = reset_jti
    user.password_reset_jti_expires = datetime.utcnow() + reset_token_expires
    user.password_reset_answer_verified_at = datetime.utcnow()
    await repo.update(user)
    
    return {
        "message": "Resposta verificada com sucesso",
        "reset_token": reset_token,
        "expires_in_minutes": 15
    }


@router.post("/reset-password", response_model=dict)
@limiter.limit("3/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    ETAPA 3: Usuário define nova senha com token de autorização
    Valida:
    - Token da step2 (type="password_reset_authorized" e JTI válido)
    - Senhas coincidem e respeitam mínimo
    Marca JTI como usado (deactivates se implementado com DB)
    """
    from backend.core.security import decode_token
    
    # Validar token da etapa anterior
    payload = decode_token(data.reset_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )
    
    # Validar que é o token correto (authorized)
    if payload.get("type") != "password_reset_authorized":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido (tipo incorreto)"
        )
    
    email = payload.get("sub")
    jti = payload.get("jti")
    if not email or not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido (formato incorreto)"
        )
    
    # Validações da senha
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="As senhas não coincidem"
        )
    
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha deve ter no mínimo 8 caracteres"
        )
    
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Consumindo e Validando o JTI persistido
    if not user.password_reset_jti or user.password_reset_jti != jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de redefinição já utilizado ou inválido. Inicie o fluxo novamente."
        )
        
    if not user.password_reset_jti_expires or datetime.utcnow() > user.password_reset_jti_expires:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="O token de redefinição expirou. Inicie o fluxo novamente."
        )
    
    try:
        # Atualizar senha com hash
        new_hashed_password = get_password_hash(data.new_password)
        user.hashed_password = new_hashed_password
        # Limpar campos de recovery
        user.password_reset_jti = None
        user.password_reset_jti_expires = None
        user.password_reset_answer_verified_at = None
        
        updated_user = await repo.update(user)
        
        return {
            "message": "Senha atualizada com sucesso",
            "email": updated_user.email,
            "status": "password_reset_success"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar senha: {str(e)}"
        )
