from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class DeviceType(str, Enum):
    FAN = "fan"
    LIGHT = "light"
    CAMERA = "camera"
    LOCK = "lock"
    TEMP = "temp_sensor"
    HUMI = "humidity_sensor"
    UNKNOWN = "unknown"

class DeviceBase(BaseModel):
    name: str
    type: DeviceType
    room: Optional[str] = None
    pin: str
    hardwareId: str
    meta_data: Optional[Dict[str, Any]] = None      
    search_keywords: Optional[str] = None           

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    room: Optional[str] = None
    type: Optional[DeviceType] = None
    description: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None     
    search_keywords: Optional[str] = None           

class DeviceRead(DeviceBase):
    id: str
    isOn: bool
    value: int
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