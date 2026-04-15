from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AndroidManagementStatus(BaseModel):
    configured: bool
    project_id: Optional[str] = None
    service_account_email: Optional[str] = None
    service_account_file: Optional[str] = None
    signup_url_name: Optional[str] = None
    signup_url: Optional[str] = None
    enterprise_name: Optional[str] = None
    enterprise_display_name: Optional[str] = None
    policy_name: Optional[str] = None
    last_error: Optional[str] = None


class SignupUrlCreate(BaseModel):
    callback_url: Optional[str] = None


class SignupUrlResponse(BaseModel):
    signup_url_name: str
    signup_url: str
    callback_url: str


class EnrollmentTokenCreate(BaseModel):
    policy_id: str = Field(default="default", min_length=1)
    duration_minutes: int = Field(default=60, ge=1, le=1440)
    one_time_only: bool = True
    additional_data: dict[str, Any] = Field(default_factory=dict)


class EnrollmentTokenResponse(BaseModel):
    id: str
    name: str
    qr_code: str
    expiration: Optional[str] = None
    expiration_timestamp: Optional[str] = None
    policy_name: Optional[str] = None


class AndroidManagementDeviceResponse(BaseModel):
    id: str
    name: str
    model: Optional[str] = None
    android_version: Optional[str] = None
    status: str
    last_checkin: Optional[str] = None
    compliance: str


class AndroidManagementDeviceSyncResponse(BaseModel):
    external_id: str
    name: str
    model: Optional[str] = None
    android_version: Optional[str] = None
    status: str
    last_seen: Optional[datetime] = None
    compliance: str
