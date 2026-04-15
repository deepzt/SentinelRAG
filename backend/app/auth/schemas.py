import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserInToken(BaseModel):
    """Claims embedded in the JWT payload."""

    sub: str  # username
    user_id: str  # UUID as string
    role: str
    department: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str
    department: str
    created_at: datetime
