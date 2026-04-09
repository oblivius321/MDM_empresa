from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.role import Role


class Permission(Base):
    """
    Tabela de Permissões granulares para controle de recursos MDM.
    """
    __tablename__ = "permissions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Domínio: "users", "devices", "audit", "system"
    resource: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_mfa: Mapped[bool] = mapped_column(Boolean, default=False)
    
    is_system_permission: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ─── Relationships Mapped ──────────────────────────────────────────────
    
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )
    
    __table_args__ = (
        Index('idx_permission_resource_action', 'resource', 'action'),
        Index('idx_permission_critical', 'is_critical'),
    )
    
    @property
    def full_name(self) -> str:
        return f"{self.resource}:{self.action}"

    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}', resource='{self.resource}')>"
