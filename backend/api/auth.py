from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.schemas.user import UserLogin, UserCreate, Token, UserResponse
from backend.models.user import User
from backend.repositories.user_repo import UserRepository
from backend.core.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
from datetime import timedelta
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
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

router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
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
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse)
async def register(new_user: UserCreate, db: AsyncSession = Depends(get_db)):
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
        
    # 3. Cria encriptando a senha
    hashed_password = get_password_hash(new_user.password)
    db_user = User(
        email=new_user.email,
        hashed_password=hashed_password,
        is_admin=False # Operadores recém criados não são admin por padrão
    )
    
    created_user = await repo.create(db_user)
    return created_user
