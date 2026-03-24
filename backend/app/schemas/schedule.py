from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DeviceScheduleCreate(BaseModel):
    time_of_day: time
    action: Literal["on", "off"]
    is_active: bool = True


class DeviceScheduleRead(BaseModel):
    id: int
    device_id: str
    time_of_day: time
    action: str
    is_active: bool
    created_by_id: int | None = None
    created_at: datetime
    last_triggered_on: date | None = None

    model_config = ConfigDict(from_attributes=True)
