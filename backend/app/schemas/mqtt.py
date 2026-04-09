from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Quy tắc mạch báo danh (Announce)
class MqttAnnounceSchema(BaseModel):
    name: str
    pins: List[str]

# Quy tắc dữ liệu cảm biến báo lên (Sensor)
class MqttSensorSchema(BaseModel):
    # Nhận các cặp như {"temp": 30, "humi": 70}
    data: Dict[str, Any] 

# Quy tắc điều khiển thiết bị (Command)
class MqttCommandSchema(BaseModel):
    pin: str
    isOn: bool 
    # Value đèn nếu ko có mặc định max. Quạt mức 1,2,3. Servo theo góc, nếu ko có mặc định xoay 90o.
    value: int = Field(..., ge=0, le=180) # Chặn giá trị ngoài 0-180

# Quy tắc phản hồi lệnh điều khiển (State)
class MqttStateSchema(BaseModel):
    pin: str
    isOn: bool
    value: int = Field(..., ge=0, le=1023)
    status: Optional[str] = "success"
