from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DeviceType = Literal["fan", "light", "camera"]


class DeviceCreate(BaseModel):
    name: str
    device_type: DeviceType
    description: str | None = None
    is_active: bool = True


class DeviceRead(BaseModel):
    id: int
    name: str
    slug: str
    device_type: str
    description: str | None = None
    owner_id: int
    is_active: bool
    last_seen_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceWithKey(DeviceRead):
    device_key: str