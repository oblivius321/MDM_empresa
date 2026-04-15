from datetime import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


class AndroidManagementConfig(Base):
    __tablename__ = "android_management_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    project_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    service_account_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    signup_url_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    signup_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enterprise_name: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    enterprise_display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    policy_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AndroidManagementEnrollmentToken(Base):
    __tablename__ = "android_management_enrollment_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, index=True)
    value_prefix: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    policy_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    qr_code: Mapped[str] = mapped_column(Text)
    additional_data: Mapped[dict] = mapped_column(JSON, default=dict)
    expiration_timestamp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
