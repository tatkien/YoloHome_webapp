from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from .device import DeviceRead

class HardwareNodeBase(BaseModel):
    id: str # Đây chính là chip ID từ mạch gửi lên
    name: str
    pins: List[str] # ["temp", "humi", "servo", "P0"...]

class HardwareNodeRead(HardwareNodeBase):
    devices: List[DeviceRead] = [] # Lấy danh sách thiết bị con nhờ 'relationship'
    
    model_config = ConfigDict(from_attributes=True)