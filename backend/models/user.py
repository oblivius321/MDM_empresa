from sqlalchemy import Column, String, Integer, Boolean, DateTime
from datetime import datetime
from backend.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    security_question = Column(String, nullable=True)
    security_answer_hash = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # ============= CAMPOS DE SEGURANÇA - PASSWORD RECOVERY =============
    # JTI (JWT ID) do token de reset em vigência (garante one-time token)
    password_reset_jti = Column(String, nullable=True, default=None)
    # Quando o JTI expira
    password_reset_jti_expires = Column(DateTime, nullable=True, default=None)
    # Quando a resposta de segurança foi verificada (para validar janela de tempo)
    password_reset_answer_verified_at = Column(DateTime, nullable=True, default=None)
