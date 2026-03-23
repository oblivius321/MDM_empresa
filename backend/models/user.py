from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    security_question = Column(String, nullable=True)
    security_answer_hash = Column(String, nullable=True)
    
    # ============= CAMPOS DE RBAC =============
    # Campo legado: será descontinuado quando RBAC estiver completo
    # Para compatibilidade, SUPER_ADMIN terá is_admin=True
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Auditoria
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ============= CAMPOS DE SEGURANÇA - PASSWORD RECOVERY =============
    # JTI (JWT ID) do token de reset em vigência (garante one-time token)
    password_reset_jti = Column(String, nullable=True, default=None)
    # Quando o JTI expira
    password_reset_jti_expires = Column(DateTime, nullable=True, default=None)
    # Quando a resposta de segurança foi verificada (para validar janela de tempo)
    password_reset_answer_verified_at = Column(DateTime, nullable=True, default=None)
    
    # ============= RELACIONAMENTOS =============
    # M:N com Roles através de user_roles
    # IMPORTANTE: Especificar foreign_keys para evitar ambiguidade com assigned_by_user_id
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
        foreign_keys="[user_roles.c.user_id, user_roles.c.role_id]",
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
        
        Retorna: Set[str] - Ex: {"devices:read", "devices:lock", "users:manage"}
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
