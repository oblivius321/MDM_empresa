from sqlalchemy import String, Integer, JSON, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"), nullable=True)
    name: Mapped[str] = mapped_column(String, default="Default Policy")
    type: Mapped[str] = mapped_column(String, default="security")
    status: Mapped[str] = mapped_column(String, default="applied")
    
    # Specific Android Enterprise fields
    camera_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    install_unknown_sources: Mapped[bool] = mapped_column(Boolean, default=False)
    factory_reset_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    kiosk_mode: Mapped[str] = mapped_column(String, nullable=True) # Package Name
    
    policy_data: Mapped[dict] = mapped_column(JSON, default=dict) # Fallback for old/extra data
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="policies")


class CommandQueue(Base):
    """
    Fila de comandos para dispositivos com suporte a acknowledgment
    Estados: pending → sent → acked → completed
    """
    __tablename__ = "command_queue"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"))
    command: Mapped[str] = mapped_column(String) # e.g. "wipe_device", "apply_policy"
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending") # pending, sent, acked, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Campos para acknowledgment e retry
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    acked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=5)
    
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    
    # Índices para performante queries de status
    __table_args__ = (
        Index('idx_device_status', 'device_id', 'status'),
        Index('idx_status_created', 'status', 'created_at'),
    )
    
    def __repr__(self):
        return f"<CommandQueue(id={self.id}, device_id={self.device_id}, command={self.command}, status={self.status})>"


class Log(Base):
    __tablename__ = "logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="info")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
