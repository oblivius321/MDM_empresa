"""
Modelos de Permission para controle granular de acesso.

Cada permissão representa uma ação específica que pode ser feita no sistema.
Permissões são atribuídas a Roles, não diretamente a Usuários.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base


class Permission(Base):
    """
    Tabela de Permissões granulares.
    
    Exemplo:
    - manage_users (criar, editar, deletar usuários)
    - manage_roles (criar, editar, deletar roles)
    - manage_devices (listar, editar dispositivos)
    - lock_device (executar lock)
    - wipe_device (executar wipe)
    - view_audit_logs (visualizar logs)
    - delete_audit_logs (deletar logs - apenas SUPER_ADMIN)
    """
    __tablename__ = "permissions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Domínio da permissão (para organizar)
    # Ex: "users", "devices", "audit", "system"
    resource: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="Ex: create, read, update, delete, execute")
    
    # Nível de perigo
    is_critical: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        comment="true = requer confirmação extra (2FA), auditado com logs detalhados"
    )
    requires_mfa: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        comment="true = requer MFA mesmo que habilitado para conta"
    )
    
    # Sistema
    is_system_permission: Mapped[bool] = mapped_column(Boolean, default=True, comment="true = built-in, não pode ser deletado")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    # Auditoria
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )
    
    # Índices
    __table_args__ = (
        Index('idx_permission_resource_action', 'resource', 'action'),
        Index('idx_permission_critical', 'is_critical'),
    )
    
    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}', resource='{self.resource}')>"
    
    @property
    def full_name(self) -> str:
        """Retorna nome completo da permissão: resource:action"""
        return f"{self.resource}:{self.action}"
