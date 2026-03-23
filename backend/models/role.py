"""
Modelos de Role (Função/Permissão) para RBAC Enterprise.

Hierarquia:
- SUPER_ADMIN: Controle total, sem restrições
- ADMIN: Controle operacional com restrições (não pode criar super admin)
- OPERATOR: Ações limitadas (dispositivos, algumas mudanças)
- VIEWER: Somente leitura (dashboard, logs)
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Table, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from backend.core.database import Base


class RoleEnum(str, enum.Enum):
    """Enum de roles predefinidas"""
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class Role(Base):
    """
    Tabela de Roles/Funções para controle de acesso baseado em papéis.
    
    Um role representa um conjunto de permissões que podem ser
    atribuídas a múltiplos usuários.
    """
    __tablename__ = "roles"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Enum para facilitar queries
    role_type: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False, index=True)
    
    # Controle
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=True, comment="true = built-in, não pode ser deletado")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="Hierarquia: SUPER_ADMIN=1000 > ADMIN=100 > OPERATOR=10 > VIEWER=1")
    
    # Auditoria
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relacionamentos
    permissions = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles"
    )
    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        foreign_keys="[user_roles.c.user_id, user_roles.c.role_id]"
    )
    
    # Índices
    __table_args__ = (
        Index('idx_role_type_active', 'role_type', 'is_active'),
        Index('idx_role_priority', 'priority'),
    )
    
    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}', type={self.role_type})>"


# ============================================================================
# Tabela de Associação M:N entre Roles e Permissions
# ============================================================================

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True, index=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True, index=True),
    Column('created_at', DateTime, default=datetime.utcnow),
    Index('idx_role_permissions_compound', 'role_id', 'permission_id'),
)


# ============================================================================
# Tabela de Associação M:N entre Users e Roles
# ============================================================================

user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True, index=True),
    Column('assigned_at', DateTime, default=datetime.utcnow),
    Column('assigned_by_user_id', Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    Index('idx_user_roles_compound', 'user_id', 'role_id'),
    Index('idx_user_roles_user', 'user_id'),
)
