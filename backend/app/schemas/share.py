# Tạo file mới: schemas/share.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DeviceShareCreate(BaseModel):
    user_id: int
    role: str = "user" # 'user',  'admin'

class DeviceShareRead(BaseModel):
    id: int
    device_id: str
    user_id: int
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)