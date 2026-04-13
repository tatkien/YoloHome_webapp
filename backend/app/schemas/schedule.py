from datetime import date, datetime, time
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ScheduleActionEnum(str, Enum):
    ON = "on"
    OFF = "off"


class DeviceScheduleCreate(BaseModel):
    times_of_day: list[time]
    action: ScheduleActionEnum
    is_active: bool = True


class DeviceScheduleRead(BaseModel):
    id: int
    device_id: str
    times_of_day: list[str]
    action: str
    is_active: bool
    created_at: datetime
    last_triggered_on: date | None = None

    model_config = ConfigDict(from_attributes=True)
