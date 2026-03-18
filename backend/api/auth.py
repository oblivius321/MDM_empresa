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
        
        # Validar tipo de token e email
        if token_type != "access" or email is None:
            raise credentials_exception
            
    except JWTError:
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

from backend.core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, response: Response, credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login endpoint com tratamento seguro de exceções."""
    try:
        print(f"🔐 Login attempt received")
        print(f"  Content-Type: {request.headers.get('content-type')}")
        print(f"  Credentials parsed: email={credentials.email}, password_length={len(credentials.password)}")
        
        # Buscar usuário no banco
        repo = UserRepository(db)
        user = await repo.get_by_email(credentials.email)
        
        if not user:
            print(f"❌ Usuário não encontrado: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email corporativo ou senha inválidos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verificar se senha está correta
        password_match = verify_password(credentials.password, user.hashed_password)
        print(f"🔑 Senha verificada para {credentials.email}: {password_match}")
        
        if not password_match:
            print(f"❌ Senha incorreta para: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email corporativo ou senha inválidos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verificar se usuário está ativo
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário inativo. Contate o administrador.",
            )
        
        # Criar token JWT
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user.email,
                "is_admin": user.is_admin,
                "type": "access"
            },
            expires_delta=access_token_expires
        )
        
        # Configurar cookie seguro
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
                "is_admin": user.is_admin,
                "id": user.id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor."
        )


@router.post("/logout")
async def logout(response: Response):
    """Destrói a sessão apagando o cookie JWT."""
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(key="access_token", httponly=True, secure=is_production, samesite="lax")
    return {"message": "Sessão encerrada com sucesso."}


@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
async def register(request: Request, new_user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Registra novo usuário (requer autorização de admin)."""
    repo = UserRepository(db)
    
    try:
        # Valida a Autorização do Admin
        admin_user = await repo.get_by_email(new_user.admin_email)
        if not admin_user or not admin_user.is_admin or not verify_password(new_user.admin_password, admin_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operação abortada. Somente administradores válidos podem autorizar."
            )

        # Confirma se o e-mail do Novo Operador já está em uso
        existing_user = await repo.get_by_email(new_user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este email corporativo já possuí acesso ao Painel."
            )
        
        # Cria encriptando a senha e a resposta da pergunta de segurança
        hashed_password = get_password_hash(new_user.password)
        hashed_answer = get_password_hash(new_user.security_answer.lower().strip())
        
        db_user = User(
            email=new_user.email,
            hashed_password=hashed_password,
            security_question=new_user.security_question,
            security_answer_hash=hashed_answer,
            is_admin=False
        )
        
        created_user = await repo.create(db_user)
        return created_user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Registration error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar novo usuário."
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Retorna o perfil do usuário logado."""
    return current_user


@router.post("/forgot-password", response_model=dict)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Solicita recuperação de senha."""
    repo = UserRepository(db)
    user = await repo.get_by_email(data.email)
    
    generic_success_msg = "Se o endereço de e-mail estiver cadastrado, uma etapa de recuperação será iniciada."
    
    if not user or not user.security_question:
        import asyncio
        await asyncio.sleep(0.5)
        return {
            "message": generic_success_msg,
            "success": False
        }
    
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
