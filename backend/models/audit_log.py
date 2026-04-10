from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Index, Uuid, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from backend.core.database import Base
from backend.core.time import utcnow

if TYPE_CHECKING:
    from backend.models.user import User

class AuditActionEnum(str, enum.Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    FAILED_LOGIN = "FAILED_LOGIN"
    ROLE_CREATE = "ROLE_CREATE"
    ROLE_UPDATE = "ROLE_UPDATE"
    ROLE_DELETE = "ROLE_DELETE"
    ROLE_ASSIGN = "ROLE_ASSIGN"
    ROLE_REVOKE = "ROLE_REVOKE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PRIVILEGE_ESCALATION_ATTEMPT = "PRIVILEGE_ESCALATION_ATTEMPT"
    DEVICE_WIPE = "DEVICE_WIPE"
    DEVICE_LOCK = "DEVICE_LOCK"
    AUDIT_LOG_DELETE = "AUDIT_LOG_DELETE"
    USER_DELETE = "USER_DELETE"
    ENROLLMENT_GENERATE = "ENROLLMENT_GENERATE"
    ENROLLMENT_COMPLETE = "ENROLLMENT_COMPLETE"
    COMMAND_CREATE = "COMMAND_CREATE"
    COMMAND_UPDATE = "COMMAND_UPDATE"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"


class AuditLog(Base):
    """
    Tabela de logs de auditoria consolidada (Enterprise Ready).
    
    Registra TODAS as ações críticas do sistema para rastreamento,
    investigação de segurança e compliance.
    """
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    
    # Usuário que realizou a ação (se aplicável ao backend)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Ação realizada (Enum estrito para segurança)
    action: Mapped[AuditActionEnum] = mapped_column(SQLEnum(AuditActionEnum), nullable=False, index=True)
    
    # Tipo de evento (Para compatibilidade/diagnóstico extra)
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Gravidade: INFO, WARNING, CRITICAL, SECURITY
    severity: Mapped[str] = mapped_column(String(20), default="INFO", index=True)
    
    # Quem realizou a ação: actor_type (admin / system / device)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="admin")
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True, default="unknown")
    
    # Recurso afetado
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    
    # Contexto opcional: ID do dispositivo se aplicável
    device_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True)
    
    # Detalhes da ação
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Status da operação
    is_success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Tracking de Rede e Request (Diagnóstico)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Relacionamentos
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    
    # Índices para relatórios rápidos
    __table_args__ = (
        Index('idx_audit_actor_event', 'actor_type', 'action'),
        Index('idx_audit_device_event', 'device_id', 'action'),
        Index('idx_audit_severity_timestamp', 'severity', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, actor={self.actor_type}:{self.actor_id}, action={self.action}, severity={self.severity})>"
