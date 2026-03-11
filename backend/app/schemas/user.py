from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = "user"
    is_active: bool = True


class UserRead(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)