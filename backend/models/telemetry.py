from sqlalchemy import String, Float, Integer, JSON, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.core.database import Base

class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id", ondelete="CASCADE"), index=True)
    
    battery_level: Mapped[float] = mapped_column(Float, nullable=True)
    is_charging: Mapped[bool] = mapped_column(Boolean, nullable=True)
    free_disk_space_mb: Mapped[int] = mapped_column(Integer, nullable=True)
    installed_apps: Mapped[list] = mapped_column(JSON, nullable=True)
    
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    foreground_app: Mapped[str] = mapped_column(String, nullable=True)
    daily_usage_stats: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    device: Mapped["Device"] = relationship("Device", back_populates="telemetry")
    
    # Índices compostos para otimizar queries comuns
    __table_args__ = (
        Index('idx_device_timestamp', 'device_id', 'timestamp', postgresql_using='btree'),
        Index('idx_timestamp_desc', 'timestamp', postgresql_using='btree'),
    )

    def __repr__(self):
        return f"<DeviceTelemetry(device_id={self.device_id}, timestamp={self.timestamp})>"
