from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DashboardCreate(BaseModel):
    name: str
    description: str | None = None


class DashboardRead(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardWidgetCreate(BaseModel):
    feed_id: int | None = None
    title: str
    widget_type: str
    position_x: int = 0
    position_y: int = 0
    width: int = 4
    height: int = 3
    config: dict[str, Any] | None = None


class DashboardWidgetRead(BaseModel):
    id: int
    dashboard_id: int
    feed_id: int | None = None
    title: str
    widget_type: str
    position_x: int
    position_y: int
    width: int
    height: int
    config: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardDetail(DashboardRead):
    widgets: list[DashboardWidgetRead] = Field(default_factory=list)