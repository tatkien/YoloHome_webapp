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

# Device state feedback schema
class MqttStateSchema(BaseModel):
    pin: str
    is_on: bool
    value: float = Field(..., ge=0, le=1023)
    status: str
