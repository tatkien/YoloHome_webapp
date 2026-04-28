from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Union
from app.schemas.device import DeviceRead, DeviceType

class PinConfig(BaseModel):
    pin: str
    type: Union[DeviceType, str]
    model_config = ConfigDict(from_attributes=True)

class HardwareNodeBase(BaseModel):
    id: str  # Chip ID reported by hardware
    name: str
    pins: Optional[List[PinConfig]] = []

class HardwareNodeCreate(HardwareNodeBase):
    pass

class HardwareNodeSummary(HardwareNodeBase):
    model_config = ConfigDict(from_attributes=True)

class HardwareNodeRead(HardwareNodeBase):
    devices: List[DeviceRead] = []

    model_config = ConfigDict(from_attributes=True)