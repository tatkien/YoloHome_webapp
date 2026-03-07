from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeviceBase(BaseModel):
    name: str
    type: str


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    active: Optional[bool] = None


class DeviceResponse(DeviceBase):
    id: int
    status: str
    active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DeviceStatsResponse(BaseModel):
    total_devices: int
    active_devices: int
    temperature: str
    humidity: str
