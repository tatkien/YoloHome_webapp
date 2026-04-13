from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DeviceType(str, Enum):
    FAN = "fan"
    LIGHT = "light"
    CAMERA = "camera"
    LOCK = "lock"
    TEMP = "temp_sensor"
    HUMI = "humidity_sensor"


class DeviceBase(BaseModel):
    name: str
    type: DeviceType
    room: Optional[str] = None
    pin: str
    hardware_id: str
    meta_data: Optional[Dict[str, Any]] = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    room: Optional[str] = None
    type: Optional[DeviceType] = None
    description: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


class DeviceRead(DeviceBase):
    id: str
    is_on: bool
    value: float
    last_seen_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class DeviceLogRead(BaseModel):
    id: int
    device_id: Optional[str] = None
    device_name: str
    action: str
    actor: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceControlRequest(BaseModel):
    is_on: bool
    value: float = Field(0, ge=0, le=1023)