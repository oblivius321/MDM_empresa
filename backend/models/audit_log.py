"""
Modelos de Auditoria para rastreamento de todas as ações críticas.

Todo acesso a recursos críticos é registrado com:
- user_id
- ação realizada
- recurso afetado
- detalhes em JSON (IDs, valores antigos/novos)
- IP do cliente
- timestamp
- resultado (sucesso/falha)
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Index, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base
import enum


class AuditActionEnum(str, enum.Enum):
    """Tipos de ações auditadas"""
    # Autenticação
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    
    # Gestão de Usuários
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_DELETE = "USER_DELETE"
    USER_DEACTIVATE = "USER_DEACTIVATE"
    
    # Gestão de Roles
    ROLE_ASSIGN = "ROLE_ASSIGN"
    ROLE_REVOKE = "ROLE_REVOKE"
    ROLE_CREATE = "ROLE_CREATE"
    ROLE_UPDATE = "ROLE_UPDATE"
    
    # Gestão de Dispositivos
    DEVICE_ENROLL = "DEVICE_ENROLL"
    DEVICE_UNENROLL = "DEVICE_UNENROLL"
    DEVICE_LOCK = "DEVICE_LOCK"
    DEVICE_UNLOCK = "DEVICE_UNLOCK"
    DEVICE_WIPE = "DEVICE_WIPE"
    DEVICE_POLICY_APPLY = "DEVICE_POLICY_APPLY"
    DEVICE_APP_INSTALL = "DEVICE_APP_INSTALL"
    DEVICE_APP_REMOVE = "DEVICE_APP_REMOVE"
    
    # Auditoria
    AUDIT_LOG_DELETE = "AUDIT_LOG_DELETE"  # CRÍTICO: apenas SUPER_ADMIN
    AUDIT_LOG_EXPORT = "AUDIT_LOG_EXPORT"
    
    # Sistema
    CONFIG_CHANGE = "CONFIG_CHANGE"
    FAILED_LOGIN = "FAILED_LOGIN"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PRIVILEGE_ESCALATION_ATTEMPT = "PRIVILEGE_ESCALATION_ATTEMPT"


class AuditLog(Base):
    """
    Tabela de logs de auditoria.
    
    Registra TODAS as ações críticas do sistema para rastreamento
    e investigação de segurança.
    """
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # User que realizou a ação
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Pode ser NULL se usuário foi deletado
        index=True
    )
    
    # Ação realizada
    action: Mapped[AuditActionEnum] = mapped_column(Enum(AuditActionEnum), nullable=False, index=True)
    
    # Recurso afetado (ex: "User:123", "Device:device_id_xyz")
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    
    # Detalhes da ação (JSON)
    details: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON com detalhes: ex: {old_role: 'VIEWER', new_role: 'OPERATOR', reason: 'promotion'}"
    )
    
    # IP do cliente
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # Resultado da ação
    is_success: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relacionamentos
    user = relationship(
        "User",
        foreign_keys=[user_id],
        uselist=False,
        doc="Usuário que realizou a ação"
    )
    
    # Índices
    __table_args__ = (
        Index('idx_audit_user_action', 'user_id', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_timestamp', 'created_at'),
        Index('idx_audit_action_timestamp', 'action', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, user={self.user_id}, action={self.action}, resource={self.resource_type}:{self.resource_id})>"
