from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Hardware announce schema
class MqttAnnounceSchema(BaseModel):
    name: str
    pins: List[str]

# Sensor payload schema
class MqttSensorSchema(BaseModel):
    # Accept pairs such as {"temp": 30, "humi": 70}
    data: Dict[str, Any] 

# Device command schema
class MqttCommandSchema(BaseModel):
    pin: str
    isOn: bool 
    # Light/fan/servo value in range 0..1023.
    value: int = Field(0, ge=0, le=1023)

# Device state feedback schema
class MqttStateSchema(BaseModel):
    pin: str
    isOn: bool
    value: int = Field(..., ge=0, le=1023)
    status: Optional[str] = "success"
