from sqlalchemy import String, Boolean, DateTime, Column, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.policy import DevicePolicy, DeviceCommand
    from backend.models.telemetry import DeviceTelemetry


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    device_type: Mapped[str] = mapped_column(String)
    
    # Informações de hardware e sistema
    imei: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    android_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Status de conectividade
    status: Mapped[str] = mapped_column(String, default="offline")
    last_checkin: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    enrollment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Armazenar campos EXTRAS que não têm coluna própria (android-specific)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Controle de Sincronização
    policy_outdated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # ─── Relationships SaaS Architecture ──────────────────────────────────────

    
    # Cada dispositivo tem uma política materializada ativa (1:1)
    device_policy: Mapped[Optional["DevicePolicy"]] = relationship(
        "DevicePolicy", back_populates="device", uselist=False, cascade="all, delete-orphan"
    )
    
    # Fila de comandos pendentes e históricos (1:N)
    commands: Mapped[List["DeviceCommand"]] = relationship(
        "DeviceCommand", back_populates="device", cascade="all, delete-orphan"
    )
    
    # Métrica de telemetria histórica (1:N)
    telemetry: Mapped[List["DeviceTelemetry"]] = relationship(
        "DeviceTelemetry", back_populates="device", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Device(id={self.id}, device_id='{self.device_id}', name='{self.name}')>"
