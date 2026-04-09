from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, List
from datetime import datetime

class TelemetryResponse(BaseModel):
    id: int
    device_id: str
    battery_level: Optional[float] = None
    is_charging: Optional[bool] = None
    free_disk_space_mb: Optional[int] = None
    installed_apps: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    foreground_app: Optional[str] = None
    daily_usage_stats: Optional[Dict] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
