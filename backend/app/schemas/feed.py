from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeedCreate(BaseModel):
    device_id: int
    name: str
    key: str | None = None
    description: str | None = None
    data_type: str = "text"


class FeedRead(BaseModel):
    id: int
    device_id: int
    name: str
    key: str
    description: str | None = None
    data_type: str
    last_value: str | None = None
    last_value_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedValueCreate(BaseModel):
    value: str


class FeedValueRead(BaseModel):
    id: int
    feed_id: int
    value: str
    source: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)