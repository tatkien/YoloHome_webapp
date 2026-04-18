from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    is_on: Optional[bool] = None
    value: Optional[float] = Field(None, ge=0, le=1023)
    
    @model_validator(mode="after")
    def validate_control(self) -> "DeviceControlRequest":
        if self.is_on is None and self.value is None:
            raise ValueError("At least one of 'is_on' or 'value' must be provided")
        return self