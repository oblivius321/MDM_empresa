from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.role import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    security_question: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    security_answer_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # ============= CAMPOS DE RBAC =============
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    # Auditoria
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ============= CAMPOS DE SEGURANÇA - PASSWORD RECOVERY =============
    password_reset_jti: Mapped[Optional[str]] = mapped_column(String, nullable=True, default=None)
    password_reset_jti_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    password_reset_answer_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    
    # ============= RELACIONAMENTOS =============
    # M:N com Roles através de user_roles
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
        primaryjoin="User.id == user_roles.c.user_id",
        secondaryjoin="Role.id == user_roles.c.role_id",
        doc="Roles atribuídas ao usuário"
    )
    
    # Índices
    __table_args__ = (
        Index('idx_user_email_active', 'email', 'is_active'),
        Index('idx_user_created', 'created_at'),
    )
    
    @property
    def all_permissions(self) -> set:
        """
        Propriedade computed que retorna um set de todas as permissões
        do usuário, agregadas de todos os seus roles.
        """
        permissions = set()
        if self.roles:
            for role in self.roles:
                if role.is_active and role.permissions:
                    for permission in role.permissions:
                        if permission.is_active:
                            permissions.add(permission.name)
        return permissions
    
    @property
    def highest_role_priority(self) -> int:
        """Retorna a prioridade do role mais alto (maior valor = mais poderoso)"""
        if not self.roles:
            return 0
        return max((role.priority for role in self.roles if role.is_active), default=0)
    
    def has_permission(self, permission_name: str) -> bool:
        """Verifica se o usuário tem a permissão especificada"""
        return permission_name in self.all_permissions
    
    def has_any_permission(self, *permission_names) -> bool:
        """Verifica se tem ANY das permissões listadas"""
        return any(perm in self.all_permissions for perm in permission_names)
    
    def has_all_permissions(self, *permission_names) -> bool:
        """Verifica se tem TODAS as permissões listadas"""
        return all(perm in self.all_permissions for perm in permission_names)

    def __repr__(self):
        return f"<User(email='{self.email}', is_admin={self.is_admin})>"
