from datetime import datetime

from pydantic import BaseModel

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    username: str
    password: str


class RegistrationRequest(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    registration_code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class InvitationKeyUpdate(BaseModel):
    invitation_key: str


class InvitationKeyResponse(BaseModel):
    updated_at: datetime
    updated_by_id: int | None = None
