from sqlalchemy import String, Integer, JSON, Boolean, DateTime, ForeignKey
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
    __tablename__ = "command_queue"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"))
    command: Mapped[str] = mapped_column(String) # e.g. "wipe_device", "apply_policy"
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending") # pending, delivered, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Log(Base):
    __tablename__ = "logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="info")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
