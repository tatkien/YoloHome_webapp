from datetime import date, datetime, time
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ScheduleActionEnum(str, Enum):
    ON = "on"
    OFF = "off"


class DeviceScheduleCreate(BaseModel):
    time_of_day: time
    action: ScheduleActionEnum
    is_active: bool = True

class DeviceScheduleUpdate(BaseModel):
    time_of_day: time

class DeviceScheduleRead(BaseModel):
    id: str
    device_id: str
    time_of_day: time
    action: str
    is_active: bool
    created_at: datetime
    last_triggered_on: date | None = None

    model_config = ConfigDict(from_attributes=True)
