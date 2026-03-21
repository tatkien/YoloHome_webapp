from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
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
    hardwareId: str

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    isOn: Optional[bool] = None
    value: Optional[int] = Field(None, ge=0, le=1023)
    name: Optional[str] = None

class DeviceRead(DeviceBase):
    id: str
    isOn: bool
    value: int
    last_seen_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)