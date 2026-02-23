from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict
from datetime import datetime


class PolicyBase(BaseModel):
    name: str = "Default Policy"
    type: str = "security"
    policy_data: Dict = {}


class PolicyCreate(PolicyBase):
    pass


class Policy(BaseModel):
    id: str
    name: str
    type: str
    status: Optional[str] = "applied"
    applied_at: Optional[datetime] = Field(None, alias="created_at")
    
    @field_validator('id', mode='before')
    def int_to_str(cls, v):
        return str(v)
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LogResponse(BaseModel):
    id: str
    device_id: Optional[str] = None
    type: str
    message: str
    severity: str
    timestamp: datetime
    
    @field_validator('id', mode='before')
    def int_to_str(cls, v):
        return str(v)
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DeviceBase(BaseModel):
    name: str 
    device_type: str
    is_active: bool = True
    status: str = "offline"
    imei: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    company: Optional[str] = None


class DeviceCreate(DeviceBase):
    device_id: str


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    imei: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    last_checkin: Optional[datetime] = None


class DeviceResponse(DeviceBase):
    id: str = Field(..., alias="device_id")
    device_id: str
    enrollment_date: datetime
    last_checkin: Optional[datetime] = None
    policies: List[Policy] = []
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
