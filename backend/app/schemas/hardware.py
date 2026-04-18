from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from app.schemas.device import DeviceRead


class HardwareNodeBase(BaseModel):
    id: str  # Chip ID reported by hardware
    name: str
    pins: List[str]  # ["temp", "humi", "servo", "P0", "P1", "P2"]
    owner_id: Optional[int] = None


class HardwareNodeRead(HardwareNodeBase):
    devices: List[DeviceRead] = []

    model_config = ConfigDict(from_attributes=True)