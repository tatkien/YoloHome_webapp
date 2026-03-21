from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from app.schemas.device import DeviceRead

class HardwareNodeBase(BaseModel):
    id: str # Chip ID từ mạch gửi lên
    name: str
    pins: List[str] # ["temp", "humi", "servo", "P0", "P1", "P2"]

class HardwareNodeRead(HardwareNodeBase):
    devices: List[DeviceRead] = [] # Lấy danh sách thiết bị con nhờ 'relationship'
    
    model_config = ConfigDict(from_attributes=True)