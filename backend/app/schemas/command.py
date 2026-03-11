from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CommandCreate(BaseModel):
    feed_id: int | None = None
    payload: dict[str, Any]


class CommandAcknowledge(BaseModel):
    result: dict[str, Any] | None = None


class CommandRead(BaseModel):
    id: int
    device_id: int
    feed_id: int | None = None
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    status: str
    delivered_at: datetime | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)