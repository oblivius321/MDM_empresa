from sqlalchemy import String, Boolean, DateTime, Column, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base
from typing import List, Optional


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    device_type: Mapped[str] = mapped_column(String)
    # New fields for frontend compatibility
    imei: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    android_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="offline")
    last_checkin: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    enrollment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    policies: Mapped[List["Policy"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    telemetry: Mapped[List["DeviceTelemetry"]] = relationship("DeviceTelemetry", back_populates="device", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Device(id={self.id}, device_id='{self.device_id}', name='{self.name}')>"
